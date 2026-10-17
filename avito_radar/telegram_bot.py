"""Interactive Telegram Bot service for Avito Radar.

Allows users to manage searches, start monitoring, select city and product,
and receive Excel spreadsheets directly through Telegram buttons and commands.
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import html
import http.server
import io
import json
import logging
import os
import re
import secrets
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

from avito_radar import billing
from avito_radar.analysis.classifier import classify_item, extract_broad_group, extract_goods_group, is_likely_fake_or_junk
from avito_radar.analysis.market import annotate_market_prices, collect_price_groups, format_money, is_overpriced
from avito_radar.analysis.market_db import apply_market_cascade, get_variant_stats, update_market_db
from avito_radar.analysis.seller_score import score_seller
from avito_radar.config import AppSettings, load_settings, save_settings
from avito_radar.core.client import AvitoClient
from avito_radar.core.geocoding import format_distance, geocode_address, lot_distance_km, suggest_addresses
from avito_radar.engine import create_search_from_url, scan_search
from avito_radar.exporters.excel import export_to_excel
from avito_radar.notifications.telegram import (
    TG_EMOJI_ANALYTICS,
    TG_EMOJI_BACK,
    TG_EMOJI_BROADCAST,
    TG_EMOJI_CHART,
    TG_EMOJI_CHECK,
    TG_EMOJI_CLOCK,
    TG_EMOJI_COG,
    TG_EMOJI_CROSS,
    TG_EMOJI_CROWN,
    TG_EMOJI_DOC,
    TG_EMOJI_EYE_OFF,
    TG_EMOJI_GAMEPAD,
    TG_EMOJI_GEAR,
    TG_EMOJI_GLOBE,
    TG_EMOJI_HOURGLASS,
    TG_EMOJI_KEYBOARD,
    TG_EMOJI_LIGHTNING,
    TG_EMOJI_LINK,
    TG_EMOJI_LIST,
    TG_EMOJI_NAV,
    TG_EMOJI_PENCIL,
    TG_EMOJI_PHONE,
    TG_EMOJI_PIN,
    TG_EMOJI_PLUS,
    TG_EMOJI_PRICE_TAG,
    TG_EMOJI_PROFILE,
    TG_EMOJI_RADAR,
    TG_EMOJI_REPEAT,
    TG_EMOJI_SEARCH,
    TG_EMOJI_SHIELD,
    TG_EMOJI_SPARKLE,
    TG_EMOJI_STAR,
    TG_EMOJI_TAG,
    TG_EMOJI_TARGET,
    TG_EMOJI_TIMER,
    TG_EMOJI_TRASH,
    TG_EMOJI_WARN,
    TelegramConfig,
    format_ad_message,
    load_telegram_config,
    tg_e,
)
from avito_radar.parsers.item_parser import ParsedItem, inspect_item_views, parse_catalog_item
from avito_radar.parsers.url_resolver import transliterate
from avito_radar.storage.db import (
    DATA_DIR,
    SearchRecord,
    append_alert,
    delete_search,
    is_valid_search_name,
    list_searches,
    load_listings,
    load_locations_cache,
    load_search,
    load_seen,
    save_listings,
    save_search,
    save_seen,
)
from avito_radar.storage import dedup, price_history, users as users_store

logger = logging.getLogger(__name__)

_LOCK_FILE_HANDLE = None

PENDING_ALERTS_DIR = DATA_DIR / "pending_alerts"
FREE_ALERT_DELAY_SEC = users_store.PLANS_LIMITS["free"]["notify_delay_min"] * 60

_BOT_USERNAME_CACHE: dict[str, str] = {}


def verify_init_data(init_data: str, bot_token: str) -> str | None:
    """Проверка HMAC подписи Telegram WebApp initData. Возвращает user_id или None."""
    if not init_data or not bot_token:
        return None
    try:
        pairs = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
    except Exception:
        return None
    data = dict(pairs)
    recv_hash = data.pop("hash", "")
    if not recv_hash:
        return None
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc_hash, recv_hash):
        return None
    try:
        user_obj = json.loads(data.get("user", "{}"))
        return str(user_obj.get("id") or "").strip() or None
    except Exception:
        return None


def get_bot_username(bot_token: str | None = None) -> str:
    token = (bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")).strip()
    if not token:
        return ""
    if token in _BOT_USERNAME_CACHE:
        return _BOT_USERNAME_CACHE[token]
    try:
        resp = requests.post(f"https://api.telegram.org/bot{token}/getMe", timeout=15)
        data = resp.json()
        if data.get("ok"):
            username = str(data["result"].get("username") or "")
            _BOT_USERNAME_CACHE[token] = username
            return username
    except Exception as exc:
        logger.debug("getMe failed: %s", exc)
    _BOT_USERNAME_CACHE[token] = ""
    return ""


def build_referral_url(user_id: str | int) -> str:
    username = get_bot_username()
    if username:
        return f"https://t.me/{username}?start=ref_{user_id}"
    return f"https://t.me/?start=ref_{user_id}"


def build_user_block(user_id: str | int) -> dict[str, Any]:
    profile = users_store.public_profile(user_id)
    profile["referral_url"] = build_referral_url(user_id)
    profile["stars_price_month"] = billing.PLANS["pro_month"]["stars"]
    profile["stars_price_year"] = billing.PLANS["pro_year"]["stars"]
    return profile


def analyze_market_for(query: str = "", search_name: str = "", user_id: str | int | None = None) -> dict[str, Any] | None:
    """Оценка рынка по имени радара или запросу: медиана, выкуп, лучшие лоты."""
    s_rec = None
    if search_name:
        s_rec = load_search(search_name)
    if not s_rec and query:
        for s in list_searches(user_id=user_id):
            if s.title.strip().lower() == query.strip().lower():
                s_rec = s
                break
    if not s_rec:
        return None
    raws = load_listings(s_rec)
    if not raws:
        return None
    items = [parse_catalog_item(r) for r in raws.values()]
    for it in items:
        classify_item(it, category_type=s_rec.category_type, search_query=s_rec.title)
    items = [it for it in items if not getattr(it, "is_mismatched_model", False)]
    annotate_market_prices(items)
    valid = [it for it in items if getattr(it, "market_median", None)]
    if not valid:
        return None
    median = int(round(sum(it.market_median for it in valid) / len(valid)))
    best = sorted(
        [it for it in valid if getattr(it, "profit_pct", None) is not None],
        key=lambda it: it.profit_pct,
    )[:5]
    return {
        "search_name": s_rec.name,
        "title": s_rec.title,
        "count": len(valid),
        "market_median": median,
        "recommended_buy": max(0, round(median * 0.88 / 100) * 100),
        "best_deals": [
            {
                "id": str(it.id),
                "title": it.title,
                "price": it.price,
                "url": it.url,
                "market_median": it.market_median,
                "profit_abs": it.profit_abs,
                "profit_pct": it.profit_pct,
                "deal_badge": it.deal_badge,
            }
            for it in best
        ],
    }


def queue_pending_alert(user_id: str | int, item: dict[str, Any]) -> None:
    """Отложенное уведомление для free-юзера: jsonl-очередь + метка времени."""
    PENDING_ALERTS_DIR.mkdir(parents=True, exist_ok=True)
    uid = str(user_id)
    path = PENDING_ALERTS_DIR / f"{uid}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
    meta_path = PENDING_ALERTS_DIR / f"{uid}.meta.json"
    if not meta_path.exists():
        meta_path.write_text(json.dumps({"last_flush": time.time()}), encoding="utf-8")


def load_pending_alerts(uid: str) -> list[dict[str, Any]]:
    path = PENDING_ALERTS_DIR / f"{uid}.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def clear_pending_alerts(uid: str) -> None:
    path = PENDING_ALERTS_DIR / f"{uid}.jsonl"
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def read_flush_meta(uid: str) -> dict[str, Any]:
    meta_path = PENDING_ALERTS_DIR / f"{uid}.meta.json"
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_flush_meta(uid: str, last_flush: float) -> None:
    PENDING_ALERTS_DIR.mkdir(parents=True, exist_ok=True)
    (PENDING_ALERTS_DIR / f"{uid}.meta.json").write_text(
        json.dumps({"last_flush": last_flush}), encoding="utf-8"
    )


def item_to_pending_dict(item: Any, search_title: str) -> dict[str, Any]:
    return {
        "search_title": search_title,
        "id": item.id,
        "title": item.title,
        "price": item.price,
        "price_formatted": item.price_formatted,
        "url": item.url,
        "address": item.address,
        "metro": item.metro,
        "city": item.city,
        "published_text": item.published_text,
        "seller_name": item.seller_name,
        "seller_type": item.seller_type,
        "seller_rating": item.seller_rating,
        "closed_listings": item.closed_listings,
        "badges": list(item.badges),
        "images": list(item.images[:4]),
        "description": item.description,
        "tags": list(item.tags),
        "market_price": item.market_price,
        "market_diff_percent": item.market_diff_percent,
        "market_median": getattr(item, "market_median", None),
        "recommended_buy": getattr(item, "recommended_buy", None),
        "profit_abs": getattr(item, "profit_abs", None),
        "profit_pct": getattr(item, "profit_pct", None),
        "deal_badge": getattr(item, "deal_badge", None),
        "geo_lat": getattr(item, "geo_lat", None),
        "geo_lon": getattr(item, "geo_lon", None),
        "market_samples": getattr(item, "market_samples", None),
        "market_min_price": getattr(item, "market_min_price", None),
    }


def pending_dict_to_item(d: dict[str, Any]) -> ParsedItem:
    it = ParsedItem(
        id=int(d.get("id") or 0),
        title=str(d.get("title") or ""),
        price=d.get("price"),
        price_formatted=str(d.get("price_formatted") or ""),
        url=str(d.get("url") or ""),
        address=str(d.get("address") or ""),
        metro=str(d.get("metro") or ""),
        city=str(d.get("city") or ""),
        published_text=str(d.get("published_text") or ""),
        sort_timestamp=None,
        seller_name=str(d.get("seller_name") or ""),
        seller_type=str(d.get("seller_type") or ""),
        seller_rating=d.get("seller_rating"),
        closed_listings=d.get("closed_listings"),
        badges=tuple(d.get("badges") or ()),
        images=list(d.get("images") or []),
        description=str(d.get("description") or ""),
        phone_available=True,
    )
    it.market_price = d.get("market_price")
    it.market_diff_percent = d.get("market_diff_percent")
    it.market_median = d.get("market_median")
    it.recommended_buy = d.get("recommended_buy")
    it.profit_abs = d.get("profit_abs")
    it.profit_pct = d.get("profit_pct")
    it.deal_badge = d.get("deal_badge")
    it.geo_lat = d.get("geo_lat")
    it.geo_lon = d.get("geo_lon")
    it.market_samples = d.get("market_samples")
    it.market_min_price = d.get("market_min_price")
    it.tags = list(d.get("tags") or [])
    return it



def _build_alert_caption(user: dict[str, Any] | None, item: Any, search_title: str) -> str:
    """Compact HTML caption for a new-lot push (Telegram limit: 1024 chars)."""
    title = html.escape(str(getattr(item, "title", "") or ""))
    if len(title) > 80:
        title = title[:77] + "..."
    deal_badge = getattr(item, "deal_badge", None)
    if deal_badge:
        header = f"{tg_e(TG_EMOJI_LIGHTNING, '⚡')} <b>Выгодная находка</b> · {html.escape(str(search_title))}"
    else:
        header = f"{tg_e(TG_EMOJI_RADAR, '👁')} <b>Новый лот по радару</b> · {html.escape(str(search_title))}"

    price_str = getattr(item, "price_formatted", "") or ""
    if not price_str and getattr(item, "price", None):
        price_str = format_money(int(item.price)) + " ₽"
    price_line = f"💰 <b>{html.escape(str(price_str))}</b>" if price_str else ""
    market_median = getattr(item, "market_median", None)
    if market_median:
        price_line += f" · рынок {format_money(int(market_median))} ₽"
    profit_abs = getattr(item, "profit_abs", None)
    profit_pct = getattr(item, "profit_pct", None)
    if profit_abs:
        gain = f"+{format_money(int(profit_abs))} ₽"
        if profit_pct:
            gain += f" (-{int(profit_pct)}%)"
        price_line += f" · <b>{gain}</b>"

    meta: list[str] = []
    dist = None
    if user and user.get("home_lat") is not None and user.get("home_lon") is not None:
        dist = lot_distance_km(user, getattr(item, "geo_lat", None), getattr(item, "geo_lon", None))
    place_parts = []
    if dist is not None:
        place_parts.append(format_distance(dist))
    city = str(getattr(item, "city", "") or "").strip()
    if city:
        place_parts.append(html.escape(city))
    if place_parts:
        meta.append(f"{tg_e(TG_EMOJI_PIN, '📍')} " + " · ".join(place_parts))
    address = str(getattr(item, "address", "") or "").strip()
    address_line = ""
    if address:
        address_line = f"<i>{html.escape(address[:60])}</i>"

    seller = score_seller(item)
    seller_parts = [f"{tg_e(TG_EMOJI_PROFILE, '👤')} {html.escape(seller['label'])}"]
    rating = getattr(item, "seller_rating", None)
    if rating:
        seller_parts.append(f"{tg_e(TG_EMOJI_STAR, '⭐️')} {rating}")
    meta.append(" ".join(seller_parts))

    drop = price_history.price_drop(item.id, getattr(item, "price", None))
    if drop:
        meta.append(
            f"📉 Снижение цены: {format_money(drop['amount'])} ₽ за {drop['days']:.1f} дн."
        )

    samples = getattr(item, "market_samples", None)
    min_price = getattr(item, "market_min_price", None)
    if samples and int(samples) >= 3 and min_price:
        meta.append(
            f"{tg_e(TG_EMOJI_CHART, '📊')} Аналогов на рынке: {int(samples)}, от {format_money(int(min_price))} ₽"
        )

    recommended_buy = getattr(item, "recommended_buy", None)
    bargain = ""
    if deal_badge and recommended_buy:
        bargain_price = f"{recommended_buy:,} ₽".replace(",", " ")
        bargain = (
            f"{tg_e(TG_EMOJI_PRICE_TAG, '🏷')} <b>Выкуп: {bargain_price}</b>\n"
            "<i>«Здравствуйте! Готов забрать сегодня, предложу "
            f"{bargain_price} - возможен торг?»</i>"
        )

    blocks = [header, f"<b>{title}</b>"]
    if price_line:
        blocks.append(price_line)
    if address_line:
        meta.insert(0, address_line)
    blocks.append("\n".join(meta))
    if bargain:
        blocks.append(f"<blockquote>{bargain}</blockquote>")

    def _join(parts: list[str]) -> str:
        return "\n".join([p for p in parts if p])

    caption = _join(blocks)
    if len(caption) > 1024:
        stripped = [b for b in blocks if b != bargain]
        caption = _join(stripped)
    if len(caption) > 1024 and address_line in meta:
        meta.remove(address_line)
        blocks[3] = "\n".join(meta)
        caption = _join(blocks)
    if len(caption) > 1024:
        while len(caption) > 1024:
            cut = max(1, len(caption) - 1000)
            caption = caption[:cut]
    return caption.strip()


def acquire_bot_lock() -> bool:
    """Ensure only one bot polling process runs at a time using OS-level locking."""
    global _LOCK_FILE_HANDLE
    lock_file = DATA_DIR / "bot.lock"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        f = open(lock_file, "a+b")
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _LOCK_FILE_HANDLE = f
        return True
    except (IOError, OSError):
        return False


# Format: (label, query, category_path, default_pmin, icon_custom_emoji_id)
POPULAR_PRODUCTS = [
    ("DDR5 32GB 6000MHz", "DDR5 32GB 6000MHz", "tovary_dlya_kompyutera/komplektuyuschie/operativnaya_pamyat", 7000, TG_EMOJI_LIGHTNING),
    ("RTX 4070 Super", "RTX 4070 Super", "tovary_dlya_kompyutera/komplektuyuschie/videokarty", 50000, TG_EMOJI_GAMEPAD),
    ("iPhone 16 Pro Max", "iPhone 16 Pro Max", "telefony/mobilnye_telefony/apple", 90000, TG_EMOJI_PHONE),
    ("iPhone 15 128GB", "iPhone 15", "telefony/mobilnye_telefony/apple", 45000, TG_EMOJI_PHONE),
    ("PlayStation 5 Slim", "PlayStation 5 Slim", "igry_pristavki_i_programmy/igrovye_pristavki", 38000, TG_EMOJI_GAMEPAD),
    ("Ryzen 7 7800X3D", "Ryzen 7 7800X3D", "tovary_dlya_kompyutera/komplektuyuschie/processory", 28000, TG_EMOJI_COG),
    ("MacBook Air M2 / M3", "MacBook Air M2", "noutbuki/apple", 65000, TG_EMOJI_KEYBOARD),
    ("Steam Deck OLED", "Steam Deck OLED", "igry_pristavki_i_programmy/igrovye_pristavki", 45000, TG_EMOJI_GAMEPAD),
    ("Lada Vesta SW Cross", "Lada Vesta SW Cross", "avtomobili", 700000, TG_EMOJI_NAV),
    ("Daewoo Matiz 0.8", "Daewoo Matiz", "avtomobili", 80000, TG_EMOJI_NAV),
    ("BMW 320d (G20)", "BMW 320d M Sport", "avtomobili", 2500000, TG_EMOJI_NAV),
    ("Toyota Camry 2.5", "Toyota Camry 2.5", "avtomobili", 2000000, TG_EMOJI_NAV),
]

POPULAR_CITIES = [
    ("Челябинск", "chelyabinsk"),
    ("Москва", "moskva"),
    ("Санкт-Петербург", "sankt-peterburg"),
    ("Екатеринбург", "ekaterinburg"),
    ("Казань", "kazan"),
    ("Новосибирск", "novosibirsk"),
    ("Уфа", "ufa"),
    ("Вся Россия", "rossiya"),
]

SORT_BY_DATE = {"s": "104"}

# In-memory TTL cache for Nominatim address suggestions
ADDRESS_SUGGEST_CACHE: dict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = {}
ADDRESS_SUGGEST_TTL_SEC = 300.0
ADDRESS_SUGGEST_CACHE_MAX = 200


def get_address_suggestions_cached(query: str, city: str | None = None) -> list[dict[str, Any]]:
    q = (query or "").strip()
    if len(q) < 3:
        return []
    cache_key = (q.lower(), (city or "").strip().lower())
    now = time.time()
    hit = ADDRESS_SUGGEST_CACHE.get(cache_key)
    if hit and now - hit[0] < ADDRESS_SUGGEST_TTL_SEC:
        return hit[1]
    result = suggest_addresses(q, city=city)
    if len(ADDRESS_SUGGEST_CACHE) >= ADDRESS_SUGGEST_CACHE_MAX:
        oldest = sorted(ADDRESS_SUGGEST_CACHE.items(), key=lambda kv: kv[1][0])[: ADDRESS_SUGGEST_CACHE_MAX // 2]
        for k, _ in oldest:
            ADDRESS_SUGGEST_CACHE.pop(k, None)
    ADDRESS_SUGGEST_CACHE[cache_key] = (now, result)
    return result


@dataclass
class UserSession:
    state: str = "IDLE"  # IDLE, WAIT_CUSTOM_QUERY, WAIT_CUSTOM_CITY, WAIT_URL, WAIT_PMIN_*
    temp_query: str = ""
    temp_city_slug: str = ""
    temp_city_name: str = ""
    temp_category_path: str = ""
    temp_pmin: int = 0
    temp_search_name: str = ""
    last_menu_message_id: int | None = None


class AvitoTelegramBot:
    def __init__(self, config: TelegramConfig) -> None:
        self.config = config
        self.api_url = f"https://api.telegram.org/bot{config.token}"
        self.sessions: dict[int, UserSession] = {}
        self.is_running = False
        self.monitoring_active = True
        self.primed_searches: set[str] = set()
        self.settings: AppSettings = load_settings()
        self.start_time = time.time()
        self.setup_menu_button()

    def setup_menu_button(self) -> None:
        """Configure Telegram bottom-left Menu Button to open Mini App on iOS & Android."""
        miniapp_url = os.environ.get("MINI_APP_URL", "https://avito-radar.onrender.com/")
        try:
            self.call_api("setChatMenuButton", {
                "menu_button": {
                    "type": "web_app",
                    "text": "Терминал Радара",
                    "web_app": {"url": miniapp_url},
                }
            })
        except Exception as exc:
            logger.debug("Could not set chat menu button: %s", exc)

    def get_session(self, chat_id: int) -> UserSession:
        return self.sessions.setdefault(chat_id, UserSession())

    # --- Telegram API calls ---

    def call_api(self, method: str, data: dict[str, Any] | None = None, files: Any = None) -> dict[str, Any]:
        url = f"{self.api_url}/{method}"
        try:
            if files:
                resp = requests.post(url, data=data, files=files, timeout=40)
            else:
                resp = requests.post(url, json=data, timeout=25)
            return resp.json()
        except Exception as exc:
            logger.error("API call %s failed: %s", method, exc)
            return {"ok": False, "description": str(exc)}

    def send_message(self, chat_id: int, text: str, reply_markup: dict[str, Any] | None = None) -> int | None:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        res = self.call_api("sendMessage", payload)
        if res.get("ok"):
            return res.get("result", {}).get("message_id")
        return None

    def edit_message(self, chat_id: int, message_id: int, text: str, reply_markup: dict[str, Any] | None = None) -> bool:
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        res = self.call_api("editMessageText", payload)
        return bool(res.get("ok"))

    def delete_message(self, chat_id: int, message_id: int) -> bool:
        try:
            res = self.call_api("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
            return bool(res.get("ok"))
        except Exception:
            return False

    def render_menu(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
        message_id: int | None = None,
    ) -> int:
        """Edit menu in place to keep the chat history completely clean."""
        session = self.get_session(chat_id)
        target_msg_id = message_id or session.last_menu_message_id

        if target_msg_id:
            if self.edit_message(chat_id, target_msg_id, text, reply_markup):
                session.last_menu_message_id = target_msg_id
                return target_msg_id

        # If edit failed or no previous menu exists, send a fresh menu
        new_id = self.send_message(chat_id, text, reply_markup)
        if new_id:
            if target_msg_id and target_msg_id != new_id:
                self.delete_message(chat_id, target_msg_id)
            session.last_menu_message_id = new_id
            return new_id
        return 0

    def answer_callback(self, callback_query_id: str, text: str = "") -> None:
        self.call_api("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})

    def send_document(self, chat_id: int, file_path: Path, caption: str = "") -> None:
        try:
            with file_path.open("rb") as f:
                self.call_api(
                    "sendDocument",
                    data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
                    files={"document": (file_path.name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                )
        except Exception as exc:
            logger.error("Failed to send document: %s", exc)

    def send_photo_alert(self, chat_id: int, item: ParsedItem, search_title: str) -> None:
        try:
            user = users_store.get_user(chat_id)
        except Exception:
            user = None
        caption = _build_alert_caption(user, item, search_title)
        base_url = os.environ.get("MINI_APP_URL", "https://avito-radar.onrender.com/").rstrip("/")
        miniapp_url = f"{base_url}/?user_id={chat_id}"
        kb = {
            "inline_keyboard": [
                [
                    {
                        "text": "⚡ Открыть на Авито",
                        "url": item.url,
                        "icon_custom_emoji_id": TG_EMOJI_LIGHTNING,
                    }
                ],
                [
                    {
                        "text": "💬 Шаблон торга",
                        "callback_data": f"bargain_{item.id}",
                        "icon_custom_emoji_id": TG_EMOJI_PROFILE,
                    },
                    {
                        "text": "🎯 Терминал",
                        "web_app": {"url": miniapp_url},
                        "icon_custom_emoji_id": TG_EMOJI_TARGET,
                    },
                ],
                [
                    {
                        "text": "🙈 Скрыть лот",
                        "callback_data": f"vanish_{item.id}",
                        "icon_custom_emoji_id": TG_EMOJI_EYE_OFF,
                    }
                ]
            ]
        }
        if item.images:
            try:
                res = self.call_api("sendPhoto", {
                    "chat_id": chat_id,
                    "photo": item.images[0],
                    "caption": caption,
                    "parse_mode": "HTML",
                    "reply_markup": kb,
                })
                if res.get("ok"):
                    return
            except Exception:
                pass
        self.send_message(chat_id, caption, reply_markup=kb)

    # --- Menus and Keyboards ---

    def main_menu_keyboard(self, chat_id: int | None = None) -> dict[str, Any]:
        base_url = os.environ.get("MINI_APP_URL", "https://avito-radar.onrender.com/").rstrip("/")
        miniapp_url = f"{base_url}/?user_id={chat_id}" if chat_id else f"{base_url}/"
        return {
            "inline_keyboard": [
                [
                    {
                        "text": "Терминал радара (Mini App)",
                        "web_app": {"url": miniapp_url},
                        "icon_custom_emoji_id": TG_EMOJI_LIGHTNING,
                    }
                ],
                [
                    {
                        "text": "Создать новый радар",
                        "callback_data": "menu_add",
                        "icon_custom_emoji_id": TG_EMOJI_PLUS,
                    }
                ],
                [
                    {
                        "text": "Мои радары и выгрузка",
                        "callback_data": "menu_list",
                        "icon_custom_emoji_id": TG_EMOJI_LIST,
                    }
                ],
                [
                    {
                        "text": "PRO Sniper и тарифы",
                        "callback_data": "menu_pro",
                        "icon_custom_emoji_id": TG_EMOJI_CROWN,
                    }
                ],
                [
                    {
                        "text": "Настройки мониторинга 24/7",
                        "callback_data": "menu_settings",
                        "icon_custom_emoji_id": TG_EMOJI_GEAR,
                    }
                ],
            ]
        }
        if self._is_owner(chat_id):
            rows = kb["inline_keyboard"]
            rows.insert(
                -1,
                [{
                    "text": "Админка",
                    "callback_data": "menu_admin",
                    "icon_custom_emoji_id": TG_EMOJI_SHIELD,
                }],
            )
        return kb

    def _is_owner(self, chat_id: int | None) -> bool:
        owner = str(os.environ.get("TELEGRAM_CHAT_ID", "")).strip()
        return bool(owner and chat_id is not None and str(chat_id) == owner)

    def send_admin_menu(self, chat_id: int, message_id: int | None = None) -> None:
        text = (
            f"{tg_e(TG_EMOJI_SHIELD, '🛡')} <b>Админка владельца</b>\n\n"
            f"{tg_e(TG_EMOJI_PLUS, '➕')} <code>/grant user_id 30</code> - выдать PRO на 30 дней\n"
            f"{tg_e(TG_EMOJI_PLUS, '➕')} <code>/grant user_id forever</code> - выдать PRO навсегда\n"
            f"{tg_e(TG_EMOJI_CROSS, '❌')} <code>/revoke user_id</code> - снять PRO\n"
            f"{tg_e(TG_EMOJI_LIST, '🗂')} <code>/users</code> - статистика пользователей"
        )
        kb = {
            "inline_keyboard": [
                [{"text": "В главное меню", "callback_data": "menu_main", "icon_custom_emoji_id": TG_EMOJI_BACK}]
            ]
        }
        self.render_menu(chat_id, text, kb, message_id=message_id)

    def handle_admin_command(self, chat_id: int, text: str) -> None:
        parts = text.split()
        cmd = parts[0].split("@")[0].lower()
        if cmd == "/grant":
            if len(parts) < 2:
                self.send_message(chat_id, f"{tg_e(TG_EMOJI_WARN, '❗️')} Формат: <code>/grant user_id [days|forever]</code>")
                return
            uid = parts[1]
            arg = parts[2] if len(parts) > 2 else "30"
            if arg.lower() == "forever":
                user = users_store.grant_pro_forever(uid)
                self.send_message(
                    chat_id,
                    f"{tg_e(TG_EMOJI_CHECK, '✅')} PRO навсегда выдан пользователю <code>{html.escape(uid)}</code>"
                    f" ({html.escape(str(user.get('username') or 'без username'))})",
                )
            elif arg.isdigit() and int(arg) > 0:
                user = users_store.grant_pro(uid, int(arg))
                exp = user.get("pro_expires_at") or ""
                self.send_message(
                    chat_id,
                    f"{tg_e(TG_EMOJI_CHECK, '✅')} PRO на {int(arg)} дн. выдан пользователю <code>{html.escape(uid)}</code>\n"
                    f"Действует до: <code>{html.escape(exp)}</code>",
                )
            else:
                self.send_message(
                    chat_id,
                    f"{tg_e(TG_EMOJI_WARN, '❗️')} Неверный срок. Укажите число дней или <code>forever</code>:\n"
                    "<code>/grant 123456789 30</code>",
                )
        elif cmd == "/revoke":
            if len(parts) < 2:
                self.send_message(chat_id, f"{tg_e(TG_EMOJI_WARN, '❗️')} Формат: <code>/revoke user_id</code>")
                return
            uid = parts[1]
            users_store.revoke_pro(uid)
            self.send_message(
                chat_id,
                f"{tg_e(TG_EMOJI_CHECK, '✅')} PRO снят у пользователя <code>{html.escape(uid)}</code>",
            )
        elif cmd == "/users":
            all_u = users_store.all_users()
            pro_users = [u for u in all_u if u.get("plan") == "pro"]
            free_users = [u for u in all_u if u.get("plan") != "pro"]
            lines = [
                f"{tg_e(TG_EMOJI_ANALYTICS, '📈')} <b>Статистика пользователей</b>\n",
                f"Всего: <b>{len(all_u)}</b> · PRO: <b>{len(pro_users)}</b> · Free: <b>{len(free_users)}</b>",
            ]
            shown = sorted(all_u, key=lambda u: 0 if u.get("plan") == "pro" else 1)[:20]
            if shown:
                lines.append("")
                for u in shown:
                    name = html.escape(str(u.get("username") or u.get("user_id") or "?"))
                    plan = "PRO" if u.get("plan") == "pro" else "free"
                    exp = u.get("pro_expires_at")
                    if u.get("plan") == "pro" and exp:
                        plan += f" до {html.escape(str(exp))}"
                    lines.append(f"• <code>{name}</code> · {plan}")
            self.send_message(chat_id, "\n".join(lines))

    def send_main_menu(self, chat_id: int, message_id: int | None = None) -> None:
        session = self.get_session(chat_id)
        session.state = "IDLE"
        status_emoji = TG_EMOJI_CHECK if self.monitoring_active else TG_EMOJI_EYE_OFF
        watch_status = "24/7 активен" if self.monitoring_active else "остановлен"
        searches = list_searches(user_id=chat_id)
        text = (
            f"{tg_e(TG_EMOJI_CROWN, '👑')} <b>AVITO RADAR // TERMINAL</b>\n"
            f"<i>Премиальный мониторинг выгодных предложений</i>\n\n"
            f"{tg_e(status_emoji, '✅')} <b>Статус:</b> <code>{watch_status}</code> · интервал 15 мин\n"
            f"{tg_e(TG_EMOJI_TARGET, '🎯')} <b>Отслеживаемых радаров:</b> <code>{len(searches)}</code>\n\n"
            f"{tg_e(TG_EMOJI_SPARKLE, '✨')} <b>Все функции - в едином терминале</b>\n"
            f"• {tg_e(TG_EMOJI_SEARCH, '🔎')} Мгновенный поиск товаров и авто с автодополнением\n"
            f"• {tg_e(TG_EMOJI_CHART, '📊')} Рыночные цены по комплектациям и оценка выгоды\n"
            f"• {tg_e(TG_EMOJI_SHIELD, '🛡')} Защита от байт-цен (100 ₽), дефектов и мусора\n"
            f"• {tg_e(TG_EMOJI_ANALYTICS, '📈')} Интерактивная таблица прямо в Telegram\n\n"
            f"<i>Уведомления о лотах ниже рынка приходят мгновенно.</i>"
        )
        self.render_menu(chat_id, text, self.main_menu_keyboard(chat_id), message_id=message_id)

    def send_add_menu(self, chat_id: int, message_id: int | None = None) -> None:
        text = (
            f"{tg_e(TG_EMOJI_BROADCAST, '🛜')} <b>Настройка нового радара</b>\n\n"
            "Выберите способ настройки отслеживания:"
        )
        kb = {
            "inline_keyboard": [
                [{"text": "Выбрать товар и город (каталог)", "callback_data": "add_wizard_product", "icon_custom_emoji_id": TG_EMOJI_SEARCH}],
                [{"text": "Вставить ссылку с Авито", "callback_data": "add_by_url", "icon_custom_emoji_id": TG_EMOJI_LINK}],
                [{"text": "Назад в главное меню", "callback_data": "menu_main", "icon_custom_emoji_id": TG_EMOJI_BACK}],
            ]
        }
        self.render_menu(chat_id, text, kb, message_id=message_id)

    def send_product_selection(self, chat_id: int, message_id: int | None = None) -> None:
        text = (
            f"{tg_e(TG_EMOJI_BROADCAST, '🛜')} <b>Шаг 1 из 2 - что отслеживать?</b>\n\n"
            "Выберите популярный запрос или введите свой:"
        )
        buttons = []
        for idx, (label, _q, _cat, _pmin, icon_id) in enumerate(POPULAR_PRODUCTS):
            buttons.append([{"text": label, "callback_data": f"pick_prod_{idx}", "icon_custom_emoji_id": icon_id}])
        buttons.append([{"text": "Ввести другое название вручную", "callback_data": "pick_prod_custom", "icon_custom_emoji_id": TG_EMOJI_PENCIL}])
        buttons.append([{"text": "Назад в меню", "callback_data": "menu_add", "icon_custom_emoji_id": TG_EMOJI_BACK}])
        kb = {"inline_keyboard": buttons}
        self.render_menu(chat_id, text, kb, message_id=message_id)

    def send_city_selection(self, chat_id: int, message_id: int | None = None) -> None:
        session = self.get_session(chat_id)
        text = (
            f"{tg_e(TG_EMOJI_PIN, '📍')} <b>Шаг 2 из 2 - выбор региона</b>\n\n"
            f"Товар: <b>{html.escape(session.temp_query)}</b>\n\n"
            f"Выберите город или отслеживание по всей стране:"
        )
        buttons = []
        for label, slug in POPULAR_CITIES:
            icon_id = TG_EMOJI_GLOBE if slug == "rossiya" else TG_EMOJI_PIN
            buttons.append([{"text": label, "callback_data": f"pick_city_{slug}_{label}", "icon_custom_emoji_id": icon_id}])
        buttons.append([{"text": "Ввести другой город вручную", "callback_data": "pick_city_custom", "icon_custom_emoji_id": TG_EMOJI_PENCIL}])
        buttons.append([{"text": "Назад к товарам", "callback_data": "add_wizard_product", "icon_custom_emoji_id": TG_EMOJI_BACK}])
        kb = {"inline_keyboard": buttons}
        self.render_menu(chat_id, text, kb, message_id=message_id)

    def send_searches_list(self, chat_id: int, message_id: int | None = None) -> None:
        searches = list_searches(user_id=chat_id)
        if not searches:
            text = (
                f"{tg_e(TG_EMOJI_LIST, '🗂')} <b>Мои радары</b>\n\n"
                "Сохранённых поисков пока нет.\n"
                "Нажмите кнопку ниже, чтобы запустить первый радар."
            )
            kb = {
                "inline_keyboard": [
                    [{"text": "Добавить новый радар", "callback_data": "menu_add", "icon_custom_emoji_id": TG_EMOJI_PLUS}],
                    [{"text": "В главное меню", "callback_data": "menu_main", "icon_custom_emoji_id": TG_EMOJI_BACK}],
                ]
            }
            self.render_menu(chat_id, text, kb, message_id=message_id)
            return

        text = f"{tg_e(TG_EMOJI_LIST, '🗂')} <b>Мои радары</b> · <code>{len(searches)}</code>\n\n"
        buttons = []
        for idx, s in enumerate(searches, start=1):
            listings = load_listings(s)
            pmin_fmt = f"{s.min_price:,} ₽".replace(",", " ") if s.min_price else "нет"
            acc_on = bool(getattr(s, "exclude_accessories", True))
            acc_status = "вкл ✅" if acc_on else "выкл ❌"
            text += f"<b>{idx}. {html.escape(s.title)}</b>\n"
            text += (
                f"    {tg_e(TG_EMOJI_PIN, '📍')} {html.escape(s.city)} · "
                f"в базе <code>{len(listings)}</code> лотов · порог {pmin_fmt} · без аксов: {acc_status}\n\n"
            )
            buttons.append([
                {"text": f"Без аксов: {'вкл' if acc_on else 'выкл'}", "callback_data": f"toggle_acc_{s.name}", "icon_custom_emoji_id": TG_EMOJI_SHIELD},
                {"text": f"Порог: {pmin_fmt}", "callback_data": f"set_pmin_{s.name}", "icon_custom_emoji_id": TG_EMOJI_PRICE_TAG},
            ])
            buttons.append([
                {"text": "Скачать Excel", "callback_data": f"action_scan_{s.name}", "icon_custom_emoji_id": TG_EMOJI_CHART},
                {"text": "Удалить радар", "callback_data": f"action_del_{s.name}", "icon_custom_emoji_id": TG_EMOJI_TRASH},
            ])

        buttons.append([{"text": "Создать ещё радар", "callback_data": "menu_add", "icon_custom_emoji_id": TG_EMOJI_PLUS}])
        buttons.append([{"text": "В главное меню", "callback_data": "menu_main", "icon_custom_emoji_id": TG_EMOJI_BACK}])

        kb = {"inline_keyboard": buttons}
        self.render_menu(chat_id, text, kb, message_id=message_id)

    def send_settings_menu(self, chat_id: int, message_id: int | None = None) -> None:
        self.settings = load_settings()
        priv_on = bool(self.settings.alert_private_only)
        junk_on = bool(self.settings.alert_filter_junk)
        acc_on = bool(getattr(self.settings, "alert_filter_accessories", True))
        interval = int(self.settings.watch_interval)

        def _mark(sec: int) -> str:
            return " ✅" if interval == sec else ""

        text = (
            f"{tg_e(TG_EMOJI_GEAR, '⚙')} <b>Настройки мониторинга 24/7</b>\n\n"
            f"{tg_e(TG_EMOJI_TIMER, '⏲️')} Интервал проверки: <b>{interval} сек</b>\n"
            f"{tg_e(TG_EMOJI_PROFILE, '👤')} Продавцы: <b>{'только частные' if priv_on else 'все (с магазинами)'}</b>\n"
            f"{tg_e(TG_EMOJI_SHIELD, '🛡')} Анти-мусор и байт-цены: <b>{'вкл ✅' if junk_on else 'выкл ❌'}</b>\n"
            f"{tg_e(TG_EMOJI_SHIELD, '🛡')} Фильтр аксессуаров: <b>{'вкл ✅' if acc_on else 'выкл ❌'}</b>\n"
            f"{tg_e(TG_EMOJI_REPEAT, '🔁')} Игнорировать дубликаты: <b>{'да' if self.settings.alert_no_republished else 'нет'}</b>\n\n"
            "Нажмите кнопку, чтобы переключить параметр:"
        )
        kb = {
            "inline_keyboard": [
                [{"text": f"Продавцы: {'только частные' if priv_on else 'все'}", "callback_data": "set_toggle_private", "icon_custom_emoji_id": TG_EMOJI_PROFILE}],
                [{"text": f"Анти-мусор: {'вкл' if junk_on else 'выкл'}", "callback_data": "set_toggle_junk", "icon_custom_emoji_id": TG_EMOJI_SHIELD}],
                [{"text": f"Аксессуары: {'скрывать' if acc_on else 'показывать'}", "callback_data": "set_toggle_accessories", "icon_custom_emoji_id": TG_EMOJI_SHIELD}],
                [{"text": f"Интервал: 1 мин{_mark(60)}", "callback_data": "set_interval_60", "icon_custom_emoji_id": TG_EMOJI_CLOCK}],
                [{"text": f"Интервал: 2 мин{_mark(120)}", "callback_data": "set_interval_120", "icon_custom_emoji_id": TG_EMOJI_CLOCK}],
                [{"text": f"Интервал: 5 мин{_mark(300)}", "callback_data": "set_interval_300", "icon_custom_emoji_id": TG_EMOJI_CLOCK}],
                [{"text": "В главное меню", "callback_data": "menu_main", "icon_custom_emoji_id": TG_EMOJI_BACK}],
            ]
        }
        self.render_menu(chat_id, text, kb, message_id=message_id)

    def send_pro_menu(self, chat_id: int, message_id: int | None = None) -> None:
        profile = users_store.public_profile(chat_id)
        is_pro_now = profile["plan"] == "pro"
        base_url = os.environ.get("MINI_APP_URL", "https://avito-radar.onrender.com/").rstrip("/")
        miniapp_url = f"{base_url}/?user_id={chat_id}"
        if is_pro_now:
            text = (
                f"{tg_e(TG_EMOJI_CROWN, '👑')} <b>PRO Sniper активен</b>\n\n"
                f"Действует до: <code>{profile.get('pro_expires_at') or '-'}</code>\n\n"
                f"⚡ 15 радаров · мгновенные уведомления · безлимитная аналитика"
            )
            kb = {"inline_keyboard": [[{"text": "В главное меню", "callback_data": "menu_main", "icon_custom_emoji_id": TG_EMOJI_BACK}]]}
            self.render_menu(chat_id, text, kb, message_id=message_id)
            return

        trial_available = bool(profile.get("trial_available"))
        text = (
            f"{tg_e(TG_EMOJI_CROWN, '👑')} <b>PRO Sniper - тарифы</b>\n\n"
            f"Бесплатно: 1 радар, 3 анализа рынка в сутки, уведомления с задержкой 15 мин.\n"
            f"PRO: 15 радаров, безлимитная аналитика, мгновенные уведомления, шаблоны торга.\n\n"
            f"{tg_e(TG_EMOJI_SPARKLE, '✨')} <b>PRO Sniper - 30 дней</b> · 299 Stars\n"
            f"{tg_e(TG_EMOJI_SPARKLE, '✨')} <b>PRO Sniper - 12 месяцев</b> · 1999 Stars\n"
        )
        if trial_available:
            text += "\nПробный PRO на 24 часа доступен бесплатно - один раз."
        buttons: list[list[dict[str, Any]]] = []
        if trial_available:
            buttons.append([{"text": "Пробный PRO на 24ч", "callback_data": "pro_trial", "icon_custom_emoji_id": TG_EMOJI_SPARKLE}])
        buttons.append([{"text": "Оплатить 30 дней (299 Stars)", "callback_data": "pro_buy_pro_month", "icon_custom_emoji_id": TG_EMOJI_CROWN}])
        buttons.append([{"text": "Оплатить 12 месяцев (1999 Stars)", "callback_data": "pro_buy_pro_year", "icon_custom_emoji_id": TG_EMOJI_CROWN}])
        buttons.append([{"text": "Оформить PRO (Mini App)", "web_app": {"url": miniapp_url}, "icon_custom_emoji_id": TG_EMOJI_LIGHTNING}])
        buttons.append([{"text": "В главное меню", "callback_data": "menu_main", "icon_custom_emoji_id": TG_EMOJI_BACK}])
        self.render_menu(chat_id, text, {"inline_keyboard": buttons}, message_id=message_id)

    def send_stars_invoice(self, chat_id: int, plan_id: str) -> None:
        plan = billing.get_plan(plan_id)
        if not plan:
            return
        payload = f"pro:{plan_id}:{chat_id}:{secrets.token_hex(8)}"
        res = self.call_api("sendInvoice", {
            "chat_id": chat_id,
            "title": plan["title"],
            "description": "PRO Sniper: 15 радаров, мгновенные уведомления, безлимитная аналитика рынка.",
            "payload": payload,
            "provider_token": "",
            "currency": "XTR",
            "prices": [{"label": plan["title"], "amount": plan["stars"]}],
        })
        if not res.get("ok"):
            logger.warning("sendInvoice failed: %s", res.get("description"))

    def send_trial_result(self, chat_id: int) -> None:
        result = users_store.grant_trial(chat_id)
        if result["ok"]:
            user = result["user"]
            self.send_message(
                chat_id,
                f"{tg_e(TG_EMOJI_SPARKLE, '✨')} <b>Пробный PRO активирован на 24 часа!</b>\n"
                f"Действует до: <code>{user.get('pro_expires_at')}</code>\n\n"
                f"⚡ Уведомления теперь мгновенные, аналитика без лимитов.",
            )
        else:
            self.send_message(
                chat_id,
                f"{tg_e(TG_EMOJI_WARN, '❗️')} Пробный PRO уже был использован ранее.\n"
                f"Оформите PRO по кнопке в меню тарифов: команда /pro",
            )

    # --- Search Creation Logic ---

    def process_create_search(self, chat_id: int, url: str, custom_name: str | None = None, message_id: int | None = None) -> None:
        # Freemium limit: free users can keep only 1 active radar
        existing = list_searches(user_id=chat_id)
        limit = users_store.get_limits(chat_id)["max_searches"]
        already = bool(custom_name and load_search(custom_name))
        if not already and len(existing) >= limit:
            text = (
                f"{tg_e(TG_EMOJI_WARN, '❗️')} <b>Достигнут лимит бесплатного тарифа</b>\n\n"
                f"На FREE доступен <b>1 радар</b>. PRO Sniper снимает лимит: до 15 радаров, "
                f"мгновенные уведомления и безлимитная аналитика рынка."
            )
            kb = {"inline_keyboard": [
                [{"text": "Оформить PRO", "callback_data": "menu_pro", "icon_custom_emoji_id": TG_EMOJI_CROWN}],
                [{"text": "В главное меню", "callback_data": "menu_main", "icon_custom_emoji_id": TG_EMOJI_BACK}],
            ]}
            self.render_menu(chat_id, text, kb, message_id=message_id)
            return
        self.render_menu(
            chat_id,
            f"{tg_e(TG_EMOJI_HOURGLASS, '⌛️')} <b>Анализирую параметры и фильтры на Авито...</b>\nПодождите пару секунд.",
            message_id=message_id,
        )
        client = AvitoClient(delay=1.0)
        try:
            resolved_name = custom_name
            if resolved_name:
                base = resolved_name
                counter = 2
                while True:
                    existing = load_search(resolved_name)
                    if not existing or existing.catalog_url == url:
                        break
                    resolved_name = f"{base}_{counter}"
                    counter += 1

            rec = create_search_from_url(client, url, custom_name=resolved_name, user_id=chat_id)
            pmin_str = f"\n{tg_e(TG_EMOJI_PRICE_TAG, '🏷')} Минимальная цена: {rec.min_price:,} ₽" if rec.min_price else ""
            text = (
                f"{tg_e(TG_EMOJI_CHECK, '✅')} <b>Радар настроен и сохранён</b>\n\n"
                f"{tg_e(TG_EMOJI_PIN, '📍')} <b>{html.escape(rec.title)}</b>\n"
                f"{tg_e(TG_EMOJI_GLOBE, '🌐')} Город: {html.escape(rec.city)}{pmin_str}\n"
                f"{tg_e(TG_EMOJI_TAG, '🏷')} Категория: {html.escape(rec.category_type)}\n"
                f"{tg_e(TG_EMOJI_DOC, '📄')} Имя: <code>{rec.name}</code>\n\n"
                f"Что сделать прямо сейчас?"
            )
            kb = {
                "inline_keyboard": [
                    [{"text": "Скачать Excel", "callback_data": f"action_scan_{rec.name}", "icon_custom_emoji_id": TG_EMOJI_CHART}],
                    [{"text": f"Мин. цена ({rec.min_price or 'нет'})", "callback_data": f"set_pmin_{rec.name}", "icon_custom_emoji_id": TG_EMOJI_PRICE_TAG}],
                    [{"text": "Перейти к моим поискам", "callback_data": "menu_list", "icon_custom_emoji_id": TG_EMOJI_LIST}],
                    [{"text": "В главное меню", "callback_data": "menu_main", "icon_custom_emoji_id": TG_EMOJI_BACK}],
                ]
            }
            self.render_menu(chat_id, text, kb, message_id=message_id)
        except Exception as exc:
            self.render_menu(
                chat_id,
                f"{tg_e(TG_EMOJI_CROSS, '❌')} <b>Не удалось добавить поиск:</b> {html.escape(str(exc))}\nПопробуйте ещё раз или скопируйте другую ссылку.",
                {"inline_keyboard": [[{"text": "В главное меню", "callback_data": "menu_main", "icon_custom_emoji_id": TG_EMOJI_BACK}]]},
                message_id=message_id,
            )

    def send_status_message(self, chat_id: int) -> None:
        uptime_sec = int(time.time() - getattr(self, "start_time", time.time()))
        days = uptime_sec // 86400
        hours = (uptime_sec % 86400) // 3600
        mins = (uptime_sec % 3600) // 60
        secs = uptime_sec % 60
        parts = []
        if days: parts.append(f"{days}д")
        if hours: parts.append(f"{hours}ч")
        if mins: parts.append(f"{mins}м")
        parts.append(f"{secs}с")
        uptime_str = " ".join(parts) or "1с"

        status_emoji = TG_EMOJI_CHECK if self.monitoring_active else TG_EMOJI_EYE_OFF
        watch_status = "24/7 активен" if self.monitoring_active else "остановлен"
        searches = list_searches(user_id=chat_id)
        base_url = os.environ.get("MINI_APP_URL", "https://avito-radar.onrender.com/").rstrip("/")
        miniapp_url = f"{base_url}/?user_id={chat_id}"

        text = (
            f"{tg_e(TG_EMOJI_CROWN, '👑')} <b>AVITO RADAR // СТАТУС СЕРВЕРА</b>\n\n"
            f"{tg_e(TG_EMOJI_TIMER, '⏲️')} Аптайм: <code>{uptime_str}</code>\n"
            f"{tg_e(status_emoji, '✅')} Мониторинг 24/7: <code>{watch_status}</code> · интервал 15 мин\n"
            f"{tg_e(TG_EMOJI_TARGET, '🎯')} Активных радаров: <code>{len(searches)}</code>\n"
            f"{tg_e(TG_EMOJI_BROADCAST, '🛜')} Healthcheck: <code>200 OK</code> (/health)\n\n"
            f"<i>Терминал готов к работе на iOS, Android и Desktop.</i>"
        )
        kb = {
            "inline_keyboard": [
                [
                    {
                        "text": "Терминал радара (Mini App)",
                        "web_app": {"url": miniapp_url},
                        "icon_custom_emoji_id": TG_EMOJI_LIGHTNING,
                    }
                ],
                [
                    {
                        "text": "Главное меню",
                        "callback_data": "menu_main",
                        "icon_custom_emoji_id": TG_EMOJI_BACK,
                    }
                ]
            ]
        }
        self.render_menu(chat_id, text, kb)

    def send_avatar_message(self, chat_id: int) -> None:
        avatar_file = Path("avatar.jpg")
        caption = (
            "🏛 <b>AVITO RADAR // ОФИЦИАЛЬНАЯ АВАТАРКА</b>\n\n"
            "<i>Новый стиль Heavy Loft & Quiet Luxury</i>\n\n"
            "• <b>Концепция:</b> Прецизионный хронометр-радар из темного титана со шкалой телеметрии цвета шампанского (#c5a059), сапфировой линзой и визиром.\n\n"
            "⚙️ <b>Как установить аватарку боту:</b>\n"
            "1. Откройте @BotFather\n"
            "2. Отправьте <code>/setuserpic</code>\n"
            "3. Выберите вашего бота\n"
            "4. Отправьте эту картинку как фото"
        )
        if avatar_file.exists():
            try:
                with avatar_file.open("rb") as f:
                    self.call_api(
                        "sendPhoto",
                        data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
                        files={"photo": (avatar_file.name, f, "image/jpeg")},
                    )
                return
            except Exception as e:
                logger.warning("Failed to send avatar photo: %s", e)
        self.send_message(chat_id, caption)

    # --- Incoming Message & Callback Routers ---

    def handle_text_message(self, message: dict[str, Any]) -> None:
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        text = str(message.get("text") or "").strip()
        msg_id = message.get("message_id")
        if not chat_id:
            return

        session = self.get_session(chat_id)

        # Delete user's incoming message so chat history stays completely clean
        if msg_id:
            self.delete_message(chat_id, msg_id)

        # /start command (with optional referral deep link)
        if text.startswith("/start"):
            session.state = "IDLE"
            arg = text.split(" ", 1)[1].strip() if " " in text else ""
            if arg.startswith("ref_"):
                referrer_id = arg[len("ref_"):].strip()
                result = users_store.add_referral(referrer_id, chat_id)
                if result["ok"]:
                    self.send_message(
                        chat_id,
                        f"{tg_e(TG_EMOJI_SPARKLE, '✨')} Вы пришли по приглашению - вашему другу начислено +3 дня PRO!",
                    )
            self.send_main_menu(chat_id)
            return

        # Admin commands (owner only, others are silently ignored)
        if text.startswith(("/grant", "/revoke", "/users")):
            session.state = "IDLE"
            if self._is_owner(chat_id):
                self.handle_admin_command(chat_id, text)
            return

        # /pro command: тарифы
        if text.startswith("/pro"):
            session.state = "IDLE"
            self.send_pro_menu(chat_id, message_id=session.last_menu_message_id)
            return

        # /status command
        if text.startswith("/status"):
            session.state = "IDLE"
            self.send_status_message(chat_id)
            return

        # /avatar command
        if text.startswith("/avatar"):
            session.state = "IDLE"
            self.send_avatar_message(chat_id)
            return

        # /address command: домашний адрес для расчёта расстояния до лотов
        if text.startswith("/address"):
            session.state = "IDLE"
            arg = text.split(" ", 1)[1].strip() if " " in text else ""
            if not arg:
                user = users_store.get_user(chat_id)
                current = user.get("home_address")
                if current:
                    self.send_message(
                        chat_id,
                        f"{tg_e(TG_EMOJI_PIN, '📍')} Текущий адрес: <b>{html.escape(current)}</b>\n"
                        "Чтобы изменить: <code>/address город, улица, дом</code>",
                    )
                else:
                    self.send_message(
                        chat_id,
                        f"{tg_e(TG_EMOJI_PIN, '📍')} Адрес не задан.\n"
                        "Пример: <code>/address Челябинск, Ленина 50</code>",
                    )
                return
            city_hint = ""
            try:
                own_searches = list_searches(user_id=chat_id)
                if own_searches and own_searches[0].city:
                    city_hint = own_searches[0].city
            except Exception:
                city_hint = ""
            geo = geocode_address(arg, city=city_hint or None)
            if not geo:
                self.send_message(
                    chat_id,
                    f"{tg_e(TG_EMOJI_WARN, '❗️')} Адрес не найден, уточните улицу и город.\n"
                    "Пример: <code>/address Челябинск, Ленина 50</code>",
                )
                return
            users_store.set_home_address(chat_id, geo["display_name"], geo["lat"], geo["lon"])
            self.send_message(
                chat_id,
                f"{tg_e(TG_EMOJI_CHECK, '✅')} Адрес сохранён: <b>{html.escape(geo['display_name'])}</b>\n"
                "В уведомлениях будет показываться расстояние до лота.",
            )
            return

        # Обработка шагов визарда, ожидающих текстовый ввод пользователя
        state = session.state
        if state == "WAIT_CUSTOM_QUERY":
            if text:
                session.temp_query = text[:120]
                session.state = "IDLE"
                self.send_city_selection(chat_id, message_id=session.last_menu_message_id)
            else:
                session.state = "IDLE"
                self.send_main_menu(chat_id)
            return

        if state == "WAIT_CUSTOM_CITY":
            session.state = "IDLE"
            slug = transliterate(text).replace(" ", "_").lower().strip("_")
            if not text or not re.fullmatch(r"[a-z0-9_-]+", slug):
                session.state = "WAIT_CUSTOM_CITY"
                self.render_menu(
                    chat_id,
                    f"{tg_e(TG_EMOJI_WARN, '❗️')} Не удалось распознать город. Введите название ещё раз (например: <code>Челябинск</code>):",
                    {"inline_keyboard": [[{"text": "Отмена", "callback_data": "add_wizard_product", "icon_custom_emoji_id": TG_EMOJI_BACK}]]},
                    message_id=session.last_menu_message_id,
                )
                return
            encoded_q = urllib.parse.quote(session.temp_query)
            if session.temp_category_path:
                target_url = f"https://www.avito.ru/{slug}/{session.temp_category_path}?q={encoded_q}"
            else:
                target_url = f"https://www.avito.ru/{slug}?q={encoded_q}"
            if session.temp_pmin:
                target_url += f"&pmin={session.temp_pmin}"
            clean_q = transliterate(session.temp_query).replace(" ", "_").lower()
            c_name = re.sub(r"[^a-z0-9_-]+", "_", f"u{chat_id}_{clean_q}_{slug}").strip("_")
            if not is_valid_search_name(c_name):
                session.state = "WAIT_CUSTOM_QUERY"
                self.render_menu(
                    chat_id,
                    f"{tg_e(TG_EMOJI_WARN, '❗️')} По этому запросу не получается безопасное имя поиска. Введите другое название товара:",
                    {"inline_keyboard": [[{"text": "Отмена", "callback_data": "add_wizard_product", "icon_custom_emoji_id": TG_EMOJI_BACK}]]},
                    message_id=session.last_menu_message_id,
                )
                return
            self.process_create_search(chat_id, target_url, custom_name=c_name, message_id=session.last_menu_message_id)
            return

        if state == "WAIT_URL":
            match = re.search(r"https?://[^\s]+", text)
            if match and "avito.ru" in match.group(0):
                session.state = "IDLE"
                self.process_create_search(chat_id, match.group(0), message_id=session.last_menu_message_id)
            else:
                self.render_menu(
                    chat_id,
                    f"{tg_e(TG_EMOJI_WARN, '❗️')} Это не ссылка Авито. Отправьте ссылку вида <code>https://www.avito.ru/...</code> "
                    "(можно просто скопировать адрес из браузера):",
                    {"inline_keyboard": [[{"text": "Отмена", "callback_data": "menu_main", "icon_custom_emoji_id": TG_EMOJI_BACK}]]},
                    message_id=session.last_menu_message_id,
                )
            return

        if state.startswith("WAIT_PMIN_"):
            search_name = state[len("WAIT_PMIN_"):]
            digits = re.sub(r"[^\d]", "", text)
            if not digits:
                self.render_menu(
                    chat_id,
                    f"{tg_e(TG_EMOJI_WARN, '❗️')} Отправьте целое число (например: <code>35000</code>) или <code>0</code>, чтобы снять ограничение:",
                    {"inline_keyboard": [[{"text": "Отмена", "callback_data": "menu_list", "icon_custom_emoji_id": TG_EMOJI_BACK}]]},
                    message_id=session.last_menu_message_id,
                )
                return
            session.state = "IDLE"
            s = load_search(search_name)
            if s:
                value = int(digits)
                s.min_price = value if value > 0 else None
                save_search(s)
            self.send_searches_list(chat_id, message_id=session.last_menu_message_id)
            return

        # Direct Avito link detection (support quick adding via link if user pastes one)
        if "avito.ru" in text:
            match = re.search(r"https?://[^\s]+avito\.ru[^\s]*", text)
            if match:
                session.state = "IDLE"
                self.process_create_search(chat_id, match.group(0))
                return

        # Always maintain a single clean terminal menu card
        if session.last_menu_message_id:
            self.delete_message(chat_id, session.last_menu_message_id)
            session.last_menu_message_id = None
        self.send_main_menu(chat_id)
        return

    def _find_user_item(self, user_id: int, item_id: str) -> ParsedItem | None:
        for d in load_pending_alerts(str(user_id)):
            if str(d.get("id")) == str(item_id):
                return pending_dict_to_item(d)
        try:
            searches = list_searches(user_id=user_id)
        except Exception:
            searches = []
        for s in searches:
            try:
                raws = load_listings(s)
            except Exception:
                continue
            for raw in raws.values():
                try:
                    item = parse_catalog_item(raw)
                except Exception:
                    continue
                if str(item.id) == str(item_id):
                    return item
        return None

    def handle_bargain_query(self, chat_id: int, cb_id: str, item_id: str) -> None:
        item = self._find_user_item(chat_id, item_id)
        if item is None:
            self.answer_callback(cb_id, text="Лот устарел, откройте объявление на Авито")
            return

        self.answer_callback(cb_id, text="Шаблон ниже")

        price = None
        recommended = getattr(item, "recommended_buy", None)
        if recommended:
            price = int(recommended)
        elif getattr(item, "price", None):
            price = int(int(item.price) * 0.9) // 100 * 100
        price_str = f"{price:,} ₽".replace(",", " ") if price else "вашу цену"
        text = (
            f"{tg_e(TG_EMOJI_PRICE_TAG, '🏷')} <b>Шаблон торга</b>\n\n"
            "«Здравствуйте! Готов(а) забрать сегодня. Предложу "
            f"<b>{price_str}</b> - возможен торг?»\n\n"
            f"🔗 {item.url}"
        )
        self.send_message(chat_id, text)

    def handle_callback_query(self, query: dict[str, Any]) -> None:
        cb_id = query.get("id") or ""
        msg = query.get("message") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        message_id = msg.get("message_id")
        data = str(query.get("data") or "")

        if not chat_id:
            return

        if data.startswith("bargain_"):
            self.handle_bargain_query(chat_id, cb_id, data[len("bargain_"):])
            return

        self.answer_callback(cb_id)
        session = self.get_session(chat_id)

        if data == "menu_main":
            self.send_main_menu(chat_id, message_id=message_id)

        elif data == "menu_add":
            self.send_add_menu(chat_id, message_id=message_id)

        elif data == "menu_list":
            self.send_searches_list(chat_id, message_id=message_id)

        elif data == "menu_settings":
            self.send_settings_menu(chat_id, message_id=message_id)

        elif data == "menu_admin":
            if self._is_owner(chat_id):
                self.send_admin_menu(chat_id, message_id=message_id)

        elif data == "menu_pro":
            self.send_pro_menu(chat_id, message_id=message_id)

        elif data == "pro_trial":
            self.send_trial_result(chat_id)

        elif data.startswith("pro_buy_"):
            plan_id = data[len("pro_buy_"):]
            self.send_stars_invoice(chat_id, plan_id)

        elif data == "menu_toggle_watch":
            self.monitoring_active = not self.monitoring_active
            self.send_main_menu(chat_id, message_id=message_id)

        elif data == "add_wizard_product":
            self.send_product_selection(chat_id, message_id=message_id)

        elif data.startswith("vanish_"):
            item_id = data[len("vanish_"):]
            self.answer_callback(cb_id, text="Лот скрыт из выдачи ✅")
            try:
                dismissed_file = DATA_DIR / "dismissed.json"
                dismissed_ids = set()
                if dismissed_file.exists():
                    try:
                        dismissed_ids = set(json.loads(dismissed_file.read_text(encoding="utf-8")))
                    except Exception:
                        pass
                dismissed_ids.add(str(item_id))
                dismissed_file.write_text(json.dumps(list(dismissed_ids)), encoding="utf-8")
            except Exception as e:
                logger.warning("Could not persist dismissed item %s: %s", item_id, e)

            if msg and message_id:
                try:
                    reply_markup = msg.get("reply_markup") or {}
                    rows = reply_markup.get("inline_keyboard", [])
                    new_rows = []
                    for row in rows:
                        new_row = []
                        for btn in row:
                            if btn.get("callback_data") == data:
                                new_row.append({"text": "Лот скрыт", "callback_data": "noop", "icon_custom_emoji_id": TG_EMOJI_EYE_OFF})
                            else:
                                new_row.append(btn)
                        new_rows.append(new_row)
                    self.call_api("editMessageReplyMarkup", {
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "reply_markup": {"inline_keyboard": new_rows}
                    })
                except Exception as e:
                    logger.debug("Could not edit reply markup: %s", e)

        elif data == "noop":
            self.answer_callback(cb_id, text="Лот уже скрыт")

        elif data.startswith("pick_prod_"):
            val = data[len("pick_prod_"):]
            if val == "custom":
                session.state = "WAIT_CUSTOM_QUERY"
                session.temp_category_path = ""
                session.temp_pmin = 0
                self.render_menu(
                    chat_id,
                    f"{tg_e(TG_EMOJI_PENCIL, '✏️')} <b>Введите название товара</b> (например: <code>iPhone 15</code>, <code>RTX 4060</code>, <code>PlayStation 5</code>):\n\n"
                    "<i>Отправьте название сообщением в чат.</i>",
                    {"inline_keyboard": [[{"text": "Отмена", "callback_data": "add_wizard_product", "icon_custom_emoji_id": TG_EMOJI_BACK}]]},
                    message_id=message_id,
                )
            else:
                try:
                    idx = int(val)
                    label, query, cat_path, pmin, _icon = POPULAR_PRODUCTS[idx]
                    session.temp_query = query
                    session.temp_category_path = cat_path
                    session.temp_pmin = pmin
                except Exception:
                    session.temp_query = val
                    session.temp_category_path = ""
                    session.temp_pmin = 0
                self.send_city_selection(chat_id, message_id=message_id)

        elif data.startswith("pick_city_"):
            parts = data[len("pick_city_"):].split("_", 1)
            slug = parts[0]
            if slug == "custom":
                session.state = "WAIT_CUSTOM_CITY"
                self.render_menu(
                    chat_id,
                    f"{tg_e(TG_EMOJI_PENCIL, '✏️')} <b>Введите название города</b> (например: <code>Челябинск</code>, <code>Сочи</code>, <code>Тюмень</code>):\n\n"
                    "<i>Отправьте название сообщением в чат.</i>",
                    {"inline_keyboard": [[{"text": "Отмена", "callback_data": "add_wizard_product", "icon_custom_emoji_id": TG_EMOJI_BACK}]]},
                    message_id=message_id,
                )
            else:
                encoded_q = urllib.parse.quote(session.temp_query)
                if session.temp_category_path:
                    target_url = f"https://www.avito.ru/{slug}/{session.temp_category_path}?q={encoded_q}"
                else:
                    target_url = f"https://www.avito.ru/{slug}?q={encoded_q}"
                if session.temp_pmin:
                    target_url += f"&pmin={session.temp_pmin}"
                clean_q = transliterate(session.temp_query).replace(" ", "_")
                c_name = re.sub(r"[^a-z0-9_-]+", "_", f"u{chat_id}_{clean_q}_{slug}").strip("_")
                if not is_valid_search_name(c_name):
                    self.render_menu(
                        chat_id,
                        f"{tg_e(TG_EMOJI_WARN, '❗️')} Не удалось сформировать корректное имя поиска. Попробуйте другой запрос.",
                        {"inline_keyboard": [[{"text": "Назад к товарам", "callback_data": "add_wizard_product", "icon_custom_emoji_id": TG_EMOJI_BACK}]]},
                        message_id=message_id,
                    )
                    return
                self.process_create_search(chat_id, target_url, custom_name=c_name, message_id=message_id)

        elif data == "add_by_url":
            session.state = "WAIT_URL"
            self.render_menu(
                chat_id,
                f"{tg_e(TG_EMOJI_LINK, '🔗')} <b>Отправьте сюда скопированную ссылку с Авито</b> (с любыми фильтрами):\n\n"
                "<i>Вставьте ссылку сообщением в чат.</i>",
                {"inline_keyboard": [[{"text": "Отмена", "callback_data": "menu_main", "icon_custom_emoji_id": TG_EMOJI_BACK}]]},
                message_id=message_id,
            )

        elif data.startswith("action_scan_"):
            search_name = data[len("action_scan_"):]
            s = load_search(search_name)
            if not s:
                self.render_menu(chat_id, f"{tg_e(TG_EMOJI_CROSS, '❌')} Поиск «{search_name}» не найден.", message_id=message_id)
                return

            self.render_menu(
                chat_id,
                f"{tg_e(TG_EMOJI_HOURGLASS, '⌛️')} <b>Формирую Excel таблицу для «{html.escape(s.title)}»...</b>\n\n"
                f"Собираю объявления, рассчитываю медианы цен и анализирую выгоду.\n"
                f"Файл таблицы сейчас появится ниже 👇",
                {"inline_keyboard": [[{"text": "К моим поискам", "callback_data": "menu_list", "icon_custom_emoji_id": TG_EMOJI_LIST}]]},
                message_id=message_id,
            )

            def run_scan() -> None:
                client = AvitoClient(delay=3.0)
                try:
                    count, excel_path = scan_search(s, client=client, max_pages=15)
                    self.send_document(
                        chat_id,
                        excel_path,
                        caption=f"{tg_e(TG_EMOJI_CHART, '📊')} <b>Таблица готова!</b>\nПоиск: <b>{html.escape(s.title)}</b>\nСобрано лотов: <b>{count}</b> шт.",
                    )
                    self.send_searches_list(chat_id, message_id=message_id)
                except Exception as exc:
                    self.render_menu(
                        chat_id,
                        f"{tg_e(TG_EMOJI_CROSS, '❌')} Ошибка сбора: {html.escape(str(exc))}",
                        {"inline_keyboard": [[{"text": "В меню", "callback_data": "menu_main", "icon_custom_emoji_id": TG_EMOJI_BACK}]]},
                        message_id=message_id,
                    )

            threading.Thread(target=run_scan, daemon=True).start()

        elif data.startswith("action_del_"):
            search_name = data[len("action_del_"):]
            delete_search(search_name, user_id=chat_id)
            self.send_searches_list(chat_id, message_id=message_id)

        elif data.startswith("set_pmin_"):
            search_name = data[len("set_pmin_"):]
            s = load_search(search_name)
            if not s:
                self.render_menu(chat_id, f"Поиск «{search_name}» не найден.", message_id=message_id)
                return
            session.state = f"WAIT_PMIN_{search_name}"
            pmin_curr = f"{s.min_price:,} ₽" if s.min_price else "не установлена"
            self.render_menu(
                chat_id,
                f"{tg_e(TG_EMOJI_PRICE_TAG, '🏷')} <b>Настройка минимальной цены для «{html.escape(s.title)}»</b>\n\n"
                f"Текущая мин. цена: <b>{pmin_curr}</b>\n\n"
                f"{tg_e(TG_EMOJI_PENCIL, '✏️')} <b>Отправьте число в чат</b> (например: <code>35000</code>), чтобы отсечь мусор и байт-цены.\n"
                f"Или отправьте <code>0</code>, чтобы снять ограничение.",
                {"inline_keyboard": [[{"text": "Отмена", "callback_data": "menu_list", "icon_custom_emoji_id": TG_EMOJI_BACK}]]},
                message_id=message_id,
            )

        elif data.startswith("toggle_acc_"):
            search_name = data[len("toggle_acc_"):]
            s = load_search(search_name)
            if s:
                s.exclude_accessories = not getattr(s, "exclude_accessories", True)
                save_search(s)
                status_str = "аксессуары скрываются ✅" if s.exclude_accessories else "аксессуары показываются ❌"
                self.answer_callback(cb_id, text=f"Фильтр: {status_str}")
            self.send_searches_list(chat_id, message_id=message_id)

        elif data == "set_toggle_junk":
            self.settings.alert_filter_junk = not self.settings.alert_filter_junk
            save_settings(self.settings)
            self.send_settings_menu(chat_id, message_id=message_id)

        elif data == "set_toggle_accessories":
            self.settings.alert_filter_accessories = not getattr(self.settings, "alert_filter_accessories", True)
            save_settings(self.settings)
            status_str = "включен ✅" if self.settings.alert_filter_accessories else "выключен ❌"
            self.answer_callback(cb_id, text=f"Фильтр аксессуаров {status_str}")
            self.send_settings_menu(chat_id, message_id=message_id)

        elif data == "set_toggle_private":
            self.settings.alert_private_only = not self.settings.alert_private_only
            save_settings(self.settings)
            self.send_settings_menu(chat_id, message_id=message_id)

        elif data.startswith("set_interval_"):
            sec = float(data[len("set_interval_"):])
            self.settings.watch_interval = sec
            save_settings(self.settings)
            self.send_settings_menu(chat_id, message_id=message_id)

    # --- Background Watch Worker ---

    def monitoring_loop(self) -> None:
        client = AvitoClient(delay=self.settings.request_delay)
        logger.info("Background monitoring worker started")

        while self.is_running:
            if not self.monitoring_active:
                time.sleep(5)
                continue

            searches = list_searches()
            if not searches:
                time.sleep(10)
                continue

            for s in searches:
                if not self.is_running or not self.monitoring_active:
                    break

                is_first_pass = s.name not in self.primed_searches
                listings = load_listings(s)
                seen = load_seen(s)
                changed = False

                try:
                    params = {**s.params, **SORT_BY_DATE}
                    if s.min_price:
                        params["pmin"] = str(s.min_price)
                    if s.max_price:
                        params["pmax"] = str(s.max_price)

                    fresh_candidates: list[ParsedItem] = []
                    for page_num in range(1, s.watch_pages + 1):
                        page = client.fetch_catalog_page(
                            catalog_url=s.catalog_url,
                            params=params,
                            page_number=page_num,
                        )

                        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                        for raw in page.items:
                            item_id = str(raw["id"])
                            try:
                                price_history.record_price(item_id, parse_catalog_item(raw).price)
                            except Exception:
                                pass
                            if item_id in seen:
                                continue

                            seen[item_id] = now_str
                            listings[item_id] = raw
                            changed = True

                            if is_first_pass:
                                continue

                            # New listing!
                            parsed = parse_catalog_item(raw)
                            q_str = s.title or s.params.get("q", "")
                            classify_item(parsed, category_type=s.category_type, search_query=q_str)

                            # Filter mismatched models
                            if getattr(parsed, "is_mismatched_model", False):
                                continue

                            # Filter private only
                            if s.private_only and any("Агентство" in t or "Магазин" in t for t in parsed.tags):
                                continue

                            # Filter accessories, junk, parts and clickbait prices if enabled
                            if (getattr(s, "exclude_accessories", True) or getattr(self.settings, "alert_filter_accessories", True)) and getattr(parsed, "is_accessory", False):
                                continue
                            if self.settings.alert_filter_junk and is_likely_fake_or_junk(parsed, min_price=s.min_price):
                                continue

                            # Inspect views to verify fresh
                            if s.new_only:
                                total_v, today_v, is_repub = inspect_item_views(client, parsed.url, s.catalog_url)
                                parsed.total_views = total_v
                                parsed.today_views = today_v
                                parsed.is_republished = is_repub
                                if is_repub:
                                    continue

                            fresh_candidates.append(parsed)

                    # Market analysis: one pass over all listings per cycle (was per item)
                    if fresh_candidates:
                        q_str = s.title or s.params.get("q", "")
                        parsed_list = []
                        for it in listings.values():
                            p_it = parse_catalog_item(it)
                            classify_item(p_it, category_type=s.category_type, search_query=q_str)
                            parsed_list.append(p_it)

                        def _variant_key(x: ParsedItem) -> str:
                            return str(x.variant or extract_goods_group(x.title)) if s.category_type == "goods" else "all"

                        stats_map = annotate_market_prices(parsed_list, group_key_fn=_variant_key)
                        group_map = (
                            collect_price_groups(parsed_list, lambda x: extract_broad_group(x.title))
                            if s.category_type == "goods"
                            else {}
                        )

                        # Feed the global variant market DB with this search's valid listings
                        try:
                            update_market_db(parsed_list, s.category_type)
                        except Exception as db_exc:
                            logger.warning("market_db update failed for %s: %s", s.name, db_exc)

                        # Track price history for every lot seen in this scan
                        for it in parsed_list:
                            try:
                                price_history.record_price(it.id, it.price)
                            except Exception as ph_exc:
                                logger.debug("price_history record failed: %s", ph_exc)

                        by_id = {it.id: it for it in parsed_list}
                        drop_pct = getattr(s, "drop_overpriced_pct", 50) or 0
                        _MARKET_FIELDS = (
                            "market_price", "market_diff_percent", "market_samples", "market_min_price",
                            "market_median", "recommended_buy", "profit_abs", "profit_pct", "deal_badge",
                            "market_source", "market_is_global", "variant", "tags",
                        )
                        with_market = overpriced_skipped = alerted = 0
                        for parsed in fresh_candidates:
                            full = by_id.get(parsed.id)
                            if full is not None:
                                if s.category_type == "goods":
                                    try:
                                        apply_market_cascade(
                                            full,
                                            stats_map.get(_variant_key(full)),
                                            group_map.get(extract_broad_group(full.title)),
                                        )
                                    except Exception as db_exc:
                                        logger.warning("market_db cascade failed for %s: %s", parsed.variant, db_exc)
                                for attr in _MARKET_FIELDS:
                                    setattr(parsed, attr, getattr(full, attr, None))

                            if parsed.market_price:
                                with_market += 1
                            parsed.overpriced = is_overpriced(parsed, drop_pct)
                            if parsed.overpriced:
                                overpriced_skipped += 1
                                logger.info(
                                    "Overpriced lot skipped (search=%s, price=%s, market=%s, +%s%% > %s%%)",
                                    s.name, parsed.price, parsed.market_price,
                                    parsed.market_diff_percent, drop_pct,
                                )
                                continue

                            # Photo-repost dedup: same images under a new id do not re-alert
                            if dedup.check_and_mark_post(s, parsed):
                                continue

                            append_alert(s, parsed)
                            alerted += 1
                            target_chat_id = None
                            if s.user_id and str(s.user_id).isdigit() and int(s.user_id) > 0:
                                target_chat_id = int(s.user_id)
                            elif self.config and self.config.chat_id:
                                try:
                                    target_chat_id = int(self.config.chat_id)
                                except Exception:
                                    pass

                            if target_chat_id:
                                try:
                                    try:
                                        target_user = users_store.get_user(target_chat_id)
                                    except Exception:
                                        target_user = None
                                    if users_store.is_pro(target_chat_id) and not users_store.is_quiet_now(target_user):
                                        self.send_photo_alert(target_chat_id, parsed, s.title)
                                    else:
                                        queue_pending_alert(target_chat_id, item_to_pending_dict(parsed, s.title))
                                except Exception as alert_err:
                                    logger.warning("Failed to send alert to user %s for %s: %s", target_chat_id, s.name, alert_err)

                        logger.info(
                            "monitoring %s: new_lots=%d alerted=%d with_market_price=%d overpriced_skipped=%d total_listings=%d",
                            s.name, len(fresh_candidates), alerted, with_market, overpriced_skipped, len(listings),
                        )

                    if changed:
                        save_listings(s, listings)
                        save_seen(s, seen)

                    if is_first_pass:
                        self.primed_searches.add(s.name)

                except Exception as exc:
                    logger.warning("Watch check error for %s: %s", s.name, exc)

            time.sleep(self.settings.watch_interval)

    def pending_alerts_flush_loop(self) -> None:
        """Отправка накопленных уведомлений free-юзерам раз в FREE_ALERT_DELAY_SEC."""
        logger.info("Pending alerts flusher started (free delay %ss)", FREE_ALERT_DELAY_SEC)
        while self.is_running:
            time.sleep(30)
            try:
                if not PENDING_ALERTS_DIR.exists():
                    continue
                now = time.time()
                for meta_file in PENDING_ALERTS_DIR.glob("*.meta.json"):
                    uid = meta_file.name[: -len(".meta.json")]
                    try:
                        chat_id = int(uid)
                    except ValueError:
                        continue
                    meta = read_flush_meta(uid)
                    last_flush = float(meta.get("last_flush") or 0)
                    pending = load_pending_alerts(uid)
                    if not pending:
                        continue
                    try:
                        flush_user = users_store.get_user(chat_id)
                    except Exception:
                        flush_user = None
                    if users_store.is_quiet_now(flush_user):
                        continue
                    if now - last_flush < FREE_ALERT_DELAY_SEC and last_flush > 0:
                        continue
                    sent = 0
                    for d in pending[:10]:
                        try:
                            self.send_photo_alert(chat_id, pending_dict_to_item(d), d.get("search_title") or "")
                            sent += 1
                        except Exception as exc:
                            logger.warning("Flush alert to %s failed: %s", uid, exc)
                    remaining = [d for i, d in enumerate(pending) if i >= sent]
                    if sent:
                        try:
                            PENDING_ALERTS_DIR.mkdir(parents=True, exist_ok=True)
                            path = PENDING_ALERTS_DIR / f"{uid}.jsonl"
                            path.write_text(
                                "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in remaining),
                                encoding="utf-8",
                            )
                        except Exception as exc:
                            logger.warning("Rewrite pending queue for %s failed: %s", uid, exc)
                    write_flush_meta(uid, now)
            except Exception as exc:
                logger.warning("Pending alerts flush error: %s", exc)

    # --- Main polling runner ---

    def run_polling(self) -> None:
        self.is_running = True
        logger.info("Starting Telegram bot polling for %s...", self.config.chat_id)

        # Start background watchdog thread
        watch_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        watch_thread.start()

        # Flush delayed notifications for free users
        flush_thread = threading.Thread(target=self.pending_alerts_flush_loop, daemon=True)
        flush_thread.start()

        offset = 0
        while self.is_running:
            try:
                res = self.call_api("getUpdates", {"offset": offset, "timeout": 20})
                if not res.get("ok"):
                    time.sleep(2)
                    continue

                updates = res.get("result", [])
                for upd in updates:
                    offset = max(offset, upd["update_id"] + 1)
                    if "pre_checkout_query" in upd:
                        billing.handle_pre_checkout(self.config.token, upd["pre_checkout_query"])
                    elif "message" in upd and upd["message"].get("successful_payment"):
                        billing.handle_successful_payment(self.config.token, upd["message"])
                    elif "message" in upd:
                        self.handle_text_message(upd["message"])
                    elif "callback_query" in upd:
                        self.handle_callback_query(upd["callback_query"])

            except Exception as exc:
                logger.error("Polling error: %s", exc)
                time.sleep(2)


def _lot_price_drop(item: Any) -> dict[str, Any] | None:
    try:
        return price_history.price_drop(item.id, item.price)
    except Exception:
        return None


def _pending_alert_ids(user_id: str | int | None) -> set[str]:
    """Ids of lots still sitting in the free-plan delayed notification queue."""
    if user_id is None:
        return set()
    try:
        return {str(d.get("id")) for d in load_pending_alerts(str(user_id)) if d.get("id") is not None}
    except Exception:
        return set()


def generate_api_bundle(user_id: str | int | None = None) -> dict[str, Any]:
    """Compile cached search listings and market analysis for Mini App."""
    bundle: dict[str, Any] = {}
    home: dict[str, Any] | None = None
    if user_id is not None and str(user_id).strip() and str(user_id) != "default":
        try:
            bundle["user"] = build_user_block(user_id)
            u = users_store.get_user(user_id)
            if u.get("home_lat") is not None and u.get("home_lon") is not None:
                home = u
        except Exception as exc:
            logger.warning("Failed to build user block: %s", exc)
    pending_ids = _pending_alert_ids(user_id)
    searches_list: list[dict[str, Any]] = []
    lots_list: list[dict[str, Any]] = []
    for s in list_searches(user_id=user_id):
        raws = load_listings(s)
        if not raws:
            try:
                cl = AvitoClient()
                scan_search(s, client=cl, max_pages=1)
                raws = load_listings(s)
            except Exception as e:
                logger.warning("Auto initial scan failed for %s: %s", s.name, e)
        items = [parse_catalog_item(r) for r in raws.values()]
        for it in items:
            classify_item(it, category_type=s.category_type, search_query=s.title)
        items = [it for it in items if not getattr(it, "is_mismatched_model", False)]
        annotate_market_prices(
            items,
            group_key_fn=(lambda x: str(x.variant or extract_goods_group(x.title))) if s.category_type == "goods" else None,
        )
        if s.category_type == "goods":
            variant_map = collect_price_groups(items, lambda x: str(x.variant or extract_goods_group(x.title)))
            group_map = collect_price_groups(items, lambda x: extract_broad_group(x.title))
            drop_pct = getattr(s, "drop_overpriced_pct", 50) or 0
            for it in items:
                try:
                    apply_market_cascade(
                        it,
                        variant_map.get(str(it.variant or extract_goods_group(it.title))),
                        group_map.get(extract_broad_group(it.title)),
                    )
                except Exception as exc:
                    logger.debug("market cascade failed in bundle for %s: %s", it.id, exc)
                it.overpriced = is_overpriced(it, drop_pct)

        searches_list.append({
            "id": s.name,
            "name": s.name,
            "query": s.title,
            "title": s.title,
            "city": s.city,
            "minPrice": s.min_price,
            "min_price": s.min_price,
            "isActive": True,
            "interval": "каждые 2 мин",
        })
        for it in items:
            posted_ms = None
            if getattr(it, "sort_timestamp", None):
                try:
                    posted_ms = int(it.sort_timestamp.timestamp() * 1000)
                except Exception:
                    posted_ms = None
            seller_raw = (it.seller_type or "").lower()
            lots_list.append({
                "id": it.id,
                "searchId": s.name,
                "title": it.title,
                "price": it.price,
                "priceFormatted": it.price_formatted,
                "price_drop": _lot_price_drop(it),
                "seller_score": score_seller(it),
                "market_min_price": getattr(it, "market_min_price", None),
                "market_samples": getattr(it, "market_samples", None),
                "is_repost": dedup.is_repost(s, it),
                "marketPrice": it.market_price,
                "marketDiffPercent": it.market_diff_percent,
                "market_median": getattr(it, "market_median", None),
                "recommended_buy": getattr(it, "recommended_buy", None),
                "profit_abs": getattr(it, "profit_abs", None),
                "profit_pct": getattr(it, "profit_pct", None),
                "deal_badge": getattr(it, "deal_badge", None),
                "market_source": getattr(it, "market_source", None),
                "overpriced": bool(getattr(it, "overpriced", False)),
                "url": it.url,
                "avitoUrl": it.url,
                "address": it.address,
                "metro": it.metro,
                "city": it.city,
                "publishedText": it.published_text,
                "postedAt": posted_ms,
                "seller": {
                    "name": it.seller_name,
                    "type": "private" if "частн" in seller_raw else "company",
                    "rating": it.seller_rating,
                    "location": it.city or it.address,
                },
                "images": it.images[:4],
                "description": it.description[:600],
                "tags": list(it.tags),
                "variant": getattr(it, "variant", None),
                "realPriceInDesc": it.real_price_in_desc,
                "isComboListing": it.is_combo_listing,
                "is_defect": getattr(it, "is_defect", False),
                "defect_type": getattr(it, "defect_type", None),
                "delayed": str(it.id) in pending_ids,
                "distance_km": lot_distance_km(home, getattr(it, "geo_lat", None), getattr(it, "geo_lon", None)),
            })

        bundle[s.name] = {
            "name": s.name,
            "title": s.title,
            "city": s.city,
            "min_price": s.min_price,
            "category_type": s.category_type,
            "exclude_accessories": getattr(s, "exclude_accessories", True),
            "items": [
                {
                    "id": it.id,
                    "title": it.title,
                    "price": it.price,
                    "price_formatted": it.price_formatted,
                    "market_price": it.market_price,
                    "market_diff_percent": it.market_diff_percent,
                    "market_median": getattr(it, "market_median", None),
                    "recommended_buy": getattr(it, "recommended_buy", None),
                    "profit_abs": getattr(it, "profit_abs", None),
                    "profit_pct": getattr(it, "profit_pct", None),
                    "deal_badge": getattr(it, "deal_badge", None),
                    "market_source": getattr(it, "market_source", None),
                    "overpriced": bool(getattr(it, "overpriced", False)),
                    "price_drop": _lot_price_drop(it),
                    "seller_score": score_seller(it),
                    "market_min_price": getattr(it, "market_min_price", None),
                    "market_samples": getattr(it, "market_samples", None),
                    "is_repost": dedup.is_repost(s, it),
                    "market_is_global": getattr(it, "market_is_global", False),
                    "variant": getattr(it, "variant", None),
                    "real_price_in_desc": it.real_price_in_desc,
                    "is_combo_listing": it.is_combo_listing,
                    "is_in_desc_or_list": getattr(it, "is_in_desc_or_list", False),
                    "is_defect": getattr(it, "is_defect", False),
                    "defect_type": getattr(it, "defect_type", None),
                    "is_exchange_or_wtb": getattr(it, "is_exchange_or_wtb", False),
                    "is_accessory": getattr(it, "is_accessory", False),
                    "is_mismatched_model": getattr(it, "is_mismatched_model", False),
                    "url": it.url,
                    "address": it.address,
                    "metro": it.metro,
                    "city": it.city,
                    "published_text": it.published_text,
                    "seller_name": it.seller_name,
                    "seller_type": it.seller_type,
                    "seller_rating": it.seller_rating,
                    "closed_listings": it.closed_listings,
                    "images": it.images[:4],
                    "description": it.description[:600],
                    "tags": it.tags,
                    "badges": list(it.badges),
                    "geo_lat": getattr(it, "geo_lat", None),
                    "geo_lon": getattr(it, "geo_lon", None),
                    "distance_km": lot_distance_km(home, getattr(it, "geo_lat", None), getattr(it, "geo_lon", None)),
                }
                for it in items
            ],
        }
    bundle["searches"] = searches_list
    bundle["lots"] = lots_list
    return bundle


EXPORT_CSV_COLUMNS = ["id", "title", "price", "market_median", "profit_abs", "profit_pct",
                      "deal_badge", "city", "distance_km", "published", "url"]


def build_lots_csv(user_id: str | int) -> tuple[int, bytes]:
    """PRO-only CSV export of the user's findings. Returns (http_status, body)."""
    uid = str(user_id or "").strip()
    if not users_store.is_pro(uid):
        payload = {"status": "error", "message": "Экспорт доступен в PRO"}
        return 403, json.dumps(payload, ensure_ascii=False).encode("utf-8")
    bundle = generate_api_bundle(user_id=uid)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(EXPORT_CSV_COLUMNS)
    for lot in bundle.get("lots", []):
        distance = lot.get("distance_km")
        writer.writerow([
            lot.get("id"),
            lot.get("title") or "",
            lot.get("price") if lot.get("price") is not None else "",
            lot.get("market_median") if lot.get("market_median") is not None else "",
            lot.get("profit_abs") if lot.get("profit_abs") is not None else "",
            lot.get("profit_pct") if lot.get("profit_pct") is not None else "",
            lot.get("deal_badge") or "",
            lot.get("city") or "",
            round(float(distance), 1) if isinstance(distance, (int, float)) else "",
            lot.get("publishedText") or "",
            lot.get("url") or "",
        ])
    return 200, buf.getvalue().encode("utf-8-sig")


SUGGESTIONS_DB: list[dict[str, Any]] = [
    {"title": "BMW 3 серии (G20) 320d xDrive M Sport", "query": "BMW 320d M Sport", "category": "auto", "meta": "2.0d (190 л.с.) • Полный привод xDrive • M Sport Pro", "minPrice": 2800000, "keywords": ["бмв", "bmw", "320", "320d", "g20", "m sport"]},
    {"title": "BMW 5 серии (G30) 520d xDrive M Sport", "query": "BMW 520d M Sport", "category": "auto", "meta": "2.0d (190 л.с.) • M-пакет • Кожа Dakota", "minPrice": 3200000, "keywords": ["бмв", "bmw", "520", "520d", "g30", "m sport"]},
    {"title": "BMW X5 (G05) xDrive30d M Sport Plus", "query": "BMW X5 G05 30d M Sport", "category": "auto", "meta": "3.0d (249 л.с.) • Пневмоподвеска • Колеса R21", "minPrice": 5500000, "keywords": ["бмв", "bmw", "x5", "g05", "30d", "m sport"]},
    {"title": "Lada Vesta SW Cross 1.6 / 1.8 Luxe Prestige", "query": "Lada Vesta SW Cross Luxe", "category": "auto", "meta": "Универсал • Клиренс 203 мм • Luxe Prestige", "minPrice": 850000, "keywords": ["лада", "lada", "веста", "vesta", "sw cross", "luxe"]},
    {"title": "Lada Vesta NG 1.6 Techno / Life", "query": "Lada Vesta NG Techno", "category": "auto", "meta": "Новое поколение NG • Экран 10.4\", цифровая приборка", "minPrice": 1100000, "keywords": ["лада", "lada", "веста", "vesta", "ng", "techno"]},
    {"title": "Toyota Camry 2.5 (XV70) Elegance Safety", "query": "Toyota Camry 2.5 Elegance", "category": "auto", "meta": "2.5 (181 л.с.) • Автомат • Комплекс Toyota Safety Sense", "minPrice": 2200000, "keywords": ["тойота", "toyota", "камри", "camry", "xv70", "elegance"]},
    {"title": "Toyota RAV4 2.0 / 2.5 (XA50) 4WD Comfort", "query": "Toyota RAV4 Comfort 4WD", "category": "auto", "meta": "Полный привод AWD • Зимний пакет, подогревы", "minPrice": 2400000, "keywords": ["тойота", "toyota", "рав4", "rav4", "comfort", "4wd"]},
    {"title": "Toyota Land Cruiser 300 GR Sport", "query": "Toyota Land Cruiser 300 GR Sport", "category": "auto", "meta": "3.3D дизель (299 л.с.) • E-KDSS, блокировки", "minPrice": 8500000, "keywords": ["тойота", "toyota", "крузак", "land cruiser", "300", "gr sport"]},
    {"title": "Mercedes-Benz E 200 / E 220 d (W213) AMG Line", "query": "Mercedes E 200 AMG Line W213", "category": "auto", "meta": "Бизнес-класс • AMG пакет, панорама, Widescreen Cockpit", "minPrice": 2800000, "keywords": ["мерседес", "mercedes", "е класс", "e 200", "w213", "amg"]},
    {"title": "Mercedes-Benz G 63 AMG 4.0 V8 (W463)", "query": "Mercedes G 63 AMG", "category": "auto", "meta": "Гелендваген • V8 Biturbo (585 л.с.) • Выхлоп AMG", "minPrice": 13000000, "keywords": ["мерседес", "mercedes", "гелик", "g 63", "amg"]},
    {"title": "Audi A4 (B9) 2.0 TFSI / TDI S Line quattro", "query": "Audi A4 B9 S Line quattro", "category": "auto", "meta": "Полный привод quattro • Virtual Cockpit, S Line", "minPrice": 2100000, "keywords": ["ауди", "audi", "а4", "a4", "b9", "s line", "quattro"]},
    {"title": "Volkswagen Tiguan 2.0 TSI (180/220 л.с.) 4Motion R-Line", "query": "VW Tiguan 2.0 TSI R-Line", "category": "auto", "meta": "Спортивный обвес R-Line • Цифровая панель, панорама", "minPrice": 2300000, "keywords": ["фольксваген", "volkswagen", "тигуан", "tiguan", "r-line"]},
    {"title": "Kia K5 2.5 (194 л.с.) GT Line / GT Line+", "query": "Kia K5 2.5 GT Line", "category": "auto", "meta": "Спортивный седан • Красная кожа, панорама, круговой обзор", "minPrice": 2200000, "keywords": ["киа", "kia", "к5", "k5", "gt line"]},
    {"title": "Hyundai Solaris 1.6 Elegance / Comfort", "query": "Hyundai Solaris Elegance", "category": "auto", "meta": "Седан • Климат-контроль, линзованная оптика", "minPrice": 950000, "keywords": ["хендай", "hyundai", "солярис", "solaris", "elegance"]},
    {"title": "Skoda Octavia (A8) 1.4 TSI / 2.0 TSI Style Plus", "query": "Skoda Octavia A8 Style", "category": "auto", "meta": "Лифтбек • Матричные фары, цифровая приборка, Canton", "minPrice": 2200000, "keywords": ["шкода", "skoda", "октавия", "octavia", "a8", "style"]},
    {"title": "Geely Monjaro 2.0 4WD Exclusive / Flagship", "query": "Geely Monjaro Flagship", "category": "auto", "meta": "Премиум кроссовер 238 л.с. • 3 экрана, полный привод", "minPrice": 3200000, "keywords": ["джили", "geely", "монджаро", "monjaro", "flagship"]},
    {"title": "Haval Jolion 1.5 4WD Premium / Tech Plus", "query": "Haval Jolion 4WD Premium", "category": "auto", "meta": "Полный привод • Адаптивный круиз, автопарковщик", "minPrice": 1700000, "keywords": ["хавал", "haval", "джолион", "jolion", "premium", "4wd"]},
    {"title": "Daewoo Matiz 0.8 МКПП", "query": "Daewoo Matiz 0.8 МКПП", "category": "auto", "meta": "0.8 л (52 л.с.) • Расход 5.5л/100км • Надежная механика", "minPrice": 80000, "keywords": ["дэу", "daewoo", "матиз", "matiz", "0.8", "мкпп"]},
    {"title": "Daewoo Matiz 0.8 АКПП Автомат", "query": "Daewoo Matiz автомат", "category": "auto", "meta": "Японский 4-ст автомат Jatco • Идеально для города", "minPrice": 140000, "keywords": ["дэу", "daewoo", "матиз", "matiz", "0.8", "акпп", "автомат", "jatco"]},
    {"title": "Daewoo Matiz 1.0 Best (4 цилиндра)", "query": "Daewoo Matiz 1.0 Best", "category": "auto", "meta": "1.0 л (64 л.с.) 4 цилиндра • Топ комплектация • ГУР, кондиционер", "minPrice": 130000, "keywords": ["дэу", "daewoo", "матиз", "matiz", "1.0", "best", "бест"]},
    {"title": "Daewoo Matiz с кондиционером и ГУР", "query": "Daewoo Matiz с кондиционером", "category": "auto", "meta": "Комплектация MX / Best • Кондиционер, ГУР, электропакет", "minPrice": 110000, "keywords": ["дэу", "daewoo", "матиз", "matiz", "кондиционер", "гур", "mx", "best"]},
    {"title": "Daewoo Matiz Рестайлинг (2008-2015)", "query": "Daewoo Matiz Рестайлинг", "category": "auto", "meta": "Поздние года выпуска кузов M150 • Обновленный салон и оптика", "minPrice": 120000, "keywords": ["дэу", "daewoo", "матиз", "matiz", "рестайлинг", "m150"]},
    {"title": "Гравийный велосипед (Gravel bike) Outleap / Format / Marin", "query": "гравел", "category": "tech", "meta": "Гравийник • Дисковые тормоза • Дропбар • Без мусора и сидушек", "minPrice": 30000, "keywords": ["гравел", "gravel", "гравийный", "велосипед", "велик", "гревел"]},
    {"title": "Гравийный велосипед Merida Silex 300 / 400 (Gravel)", "query": "Merida Silex", "category": "tech", "meta": "Топовый гравийник Merida • Оборудование Shimano GRX", "minPrice": 50000, "keywords": ["мерида", "merida", "silex", "сайлекс", "гравел", "gravel"]},
    {"title": "Шоссейный велосипед (Road bike)", "query": "шоссейный велосипед", "category": "tech", "meta": "Шоссер • Дропбар • Легкая рама", "minPrice": 25000, "keywords": ["шоссейник", "шоссейный", "велосипед"]},
    {"title": "Горный велосипед MTB (Найнер 29 / 27.5)", "query": "горный велосипед 29", "category": "tech", "meta": "Хардтейл MTB • Гидравлические тормоза • 29 колеса", "minPrice": 20000, "keywords": ["горный", "велосипед", "mtb", "мтб", "найнер"]},
    {"title": "DDR5 32GB (2x16GB) 6000MHz Kingston Fury Beast", "query": "DDR5 32GB 6000MHz Kingston", "category": "tech", "meta": "Оперативная память • 6000MHz CL30/CL36 • EXPO / XMP", "minPrice": 7500, "keywords": ["ddr5", "ддр5", "ddr 5", "ддр 5", "оперативка", "память", "kingston", "fury", "32gb"]},
    {"title": "DDR5 32GB (2x16GB) 6000MHz G.Skill Trident Z5 RGB", "query": "DDR5 32GB G.Skill Trident Z5", "category": "tech", "meta": "Премиум память • 6000MHz CL30 • Синхронизация RGB", "minPrice": 9500, "keywords": ["ddr5", "ддр5", "g skill", "g.skill", "trident", "z5", "32gb"]},
    {"title": "DDR5 64GB (2x32GB) 6000MHz CL30", "query": "DDR5 64GB 6000MHz", "category": "tech", "meta": "Комплект 64GB • Идеально для работы и тяжелых задач", "minPrice": 16000, "keywords": ["ddr5", "ддр5", "64gb", "64 gb", "оперативка"]},
    {"title": "DDR5 SODIMM 16GB / 32GB для ноутбука", "query": "DDR5 SODIMM 4800MHz 5600MHz", "category": "tech", "meta": "Память для игровых ноутбуков • 4800/5600MHz", "minPrice": 3500, "keywords": ["ddr5", "ддр5", "sodimm", "содимм", "для ноутбука"]},
    {"title": "DDR4 32GB (2x16GB) 3200MHz / 3600MHz Kingston Fury", "query": "DDR4 32GB 3200MHz Kingston Fury", "category": "tech", "meta": "Надежная память DDR4 • 3200-3600MHz", "minPrice": 4500, "keywords": ["ddr4", "ддр4", "ddr 4", "ддр 4", "оперативка", "32gb"]},
    {"title": "NVIDIA GeForce RTX 4070 Super 12GB", "query": "RTX 4070 Super 12GB", "category": "tech", "meta": "GDDR6X 12GB • DLSS 3.5 Frame Generation", "minPrice": 55000, "keywords": ["видеокарта", "rtx", "4070 super", "nvidia", "видяха"]},
    {"title": "NVIDIA GeForce RTX 4080 Super 16GB", "query": "RTX 4080 Super 16GB", "category": "tech", "meta": "GDDR6X 16GB • Мощнейшая 4K графика", "minPrice": 95000, "keywords": ["видеокарта", "rtx", "4080 super", "nvidia"]},
    {"title": "NVIDIA GeForce RTX 4090 24GB", "query": "RTX 4090 24GB", "category": "tech", "meta": "Флагман 24GB • Топовая производительность", "minPrice": 160000, "keywords": ["видеокарта", "rtx", "4090", "nvidia"]},
    {"title": "NVIDIA GeForce RTX 4060 8GB / 4060 Ti", "query": "RTX 4060 8GB", "category": "tech", "meta": "DLSS 3 • Низкое энергопотребление", "minPrice": 27000, "keywords": ["видеокарта", "rtx", "4060", "4060 ti", "nvidia"]},
    {"title": "AMD Radeon RX 6700 XT 12GB", "query": "RX 6700 XT 12GB", "category": "tech", "meta": "12GB GDDR6 • Отличный выбор для 2K", "minPrice": 25000, "keywords": ["видеокарта", "rx", "6700 xt", "amd", "radeon"]},
    {"title": "AMD Radeon RX 7800 XT 16GB", "query": "RX 7800 XT 16GB", "category": "tech", "meta": "16GB GDDR6 • Мощный 2K/4K гейминг", "minPrice": 48000, "keywords": ["видеокарта", "rx", "7800 xt", "amd"]},
    {"title": "AMD Ryzen 7 7800X3D (AM5)", "query": "Ryzen 7 7800X3D", "category": "tech", "meta": "Лучший процессор для игр • 3D V-Cache • AM5", "minPrice": 29000, "keywords": ["процессор", "проц", "ryzen", "7800x3d", "am5", "amd"]},
    {"title": "AMD Ryzen 5 7500F / 7600 (AM5)", "query": "Ryzen 5 7500F", "category": "tech", "meta": "Топ за свои деньги под AM5 и DDR5", "minPrice": 11000, "keywords": ["процессор", "проц", "ryzen", "7500f", "7600", "am5"]},
    {"title": "Intel Core i5 13400F / 14400F (LGA1700)", "query": "Core i5 13400F", "category": "tech", "meta": "10 ядер • Отличный универсальный процессор", "minPrice": 14000, "keywords": ["процессор", "intel", "i5", "13400f", "14400f"]},
    {"title": "SSD M.2 NVMe 1TB Samsung 980 / 990 Pro", "query": "Samsung 980 Pro 1TB", "category": "tech", "meta": "PCIe 4.0 • Скорость до 7450 МБ/с", "minPrice": 7500, "keywords": ["ssd", "ссд", "m.2", "nvme", "samsung", "980 pro", "990 pro", "1tb"]},
    {"title": "SSD M.2 NVMe 2TB Kingston KC3000 / Samsung 990", "query": "SSD 2TB M.2 NVMe", "category": "tech", "meta": "Объем 2000GB • Высочайшая надежность", "minPrice": 14000, "keywords": ["ssd", "ссд", "2tb", "m.2", "nvme", "kc3000"]},
    {"title": "PlayStation 5 Slim с дисководом 1TB", "query": "PlayStation 5 Slim 1TB", "category": "tech", "meta": "Новая ревизия Slim • 1TB SSD • Геймпад DualSense", "minPrice": 42000, "keywords": ["сони", "playstation", "ps5", "slim", "плойка"]},
    {"title": "Steam Deck OLED 512GB / 1TB", "query": "Steam Deck OLED", "category": "tech", "meta": "OLED 90Hz экран • Автономность • Портативный ПК", "minPrice": 45000, "keywords": ["steam deck", "стим дек", "oled"]},
    {"title": "iPhone 16 Pro Max 256GB / 512GB", "query": "iPhone 16 Pro Max 256GB", "category": "tech", "meta": "Титановый корпус • Камера 48 Мп • Чип A18 Pro", "minPrice": 95000, "keywords": ["айфон", "iphone", "16 pro max", "apple"]},
    {"title": "iPhone 15 Pro Max 256GB / 512GB", "query": "iPhone 15 Pro Max 256GB", "category": "tech", "meta": "Титановый корпус • Чип Apple A17 Pro • Камера 5x", "minPrice": 85000, "keywords": ["айфон", "iphone", "15 pro max", "apple"]},
    {"title": "iPhone 15 128GB", "query": "iPhone 15 128GB", "category": "tech", "meta": "Dynamic Island • Камера 48 Мп • USB-C", "minPrice": 55000, "keywords": ["айфон", "iphone", "15", "apple"]},
    {"title": "MacBook Air M2 8/256GB / 16/512GB", "query": "MacBook Air M2", "category": "tech", "meta": "Экран Liquid Retina 13.6 • Тонкий алюминий • До 18ч", "minPrice": 65000, "keywords": ["макбук", "macbook", "air m2", "apple", "ноут"]}
]


def get_query_suggestions(query: str, limit: int = 8) -> list[dict[str, Any]]:
    q = (query or "").lower().strip()
    if len(q) < 2:
        return []
    matches = []
    for item in SUGGESTIONS_DB:
        title = item["title"].lower()
        q_item = item["query"].lower()
        keywords = [k.lower() for k in item.get("keywords", [])]
        if q in title or q in q_item or any(q in k or k in q for k in keywords):
            matches.append(item)
            if len(matches) >= limit:
                break
    return matches


def start_healthcheck_server() -> None:
    port = int(os.environ.get("PORT", "7860"))

    class MiniAppServerHandler(http.server.BaseHTTPRequestHandler):
        def get_user_id(self, query_params: dict[str, list[str]], body_data: dict[str, Any] | None = None) -> str:
            uid = self.headers.get("X-Telegram-User-Id")
            if uid and uid.strip():
                return uid.strip()

            if "user_id" in query_params and query_params["user_id"]:
                val = query_params["user_id"][0].strip()
                if val:
                    return val

            init_data = (
                self.headers.get("X-Telegram-Init-Data")
                or (query_params.get("initData", [""])[0])
                or (query_params.get("tgWebAppData", [""])[0])
            )
            if init_data:
                bot_token = str(os.environ.get("TELEGRAM_BOT_TOKEN", "")).strip()
                verified_uid = verify_init_data(init_data, bot_token)
                if verified_uid:
                    return verified_uid
                if bot_token:
                    # initData передан, но подпись невалидна
                    return "__invalid_init__"
                # dev/legacy: токен не задан, подпись не проверяем
                try:
                    parsed_qs = urllib.parse.parse_qs(init_data)
                    if "user" in parsed_qs:
                        user_obj = json.loads(parsed_qs["user"][0])
                        if "id" in user_obj:
                            return str(user_obj["id"]).strip()
                except Exception:
                    pass

            if body_data and "user_id" in body_data and body_data["user_id"]:
                return str(body_data["user_id"]).strip()

            owner_id = str(os.environ.get("TELEGRAM_CHAT_ID", "")).strip()
            return owner_id or "default"

        def send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def send_error_json(self, status: int, message: str) -> None:
            self.send_json(status, {"status": "error", "message": message})

        def guard_invalid_init(self, uid: str) -> bool:
            if uid == "__invalid_init__":
                self.send_error_json(403, "invalid initData signature")
                return True
            return False

        def do_OPTIONS(self) -> None:
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.end_headers()

        def do_DELETE(self) -> None:
            parsed_url = urllib.parse.urlparse(self.path)
            path = parsed_url.path
            query_params = urllib.parse.parse_qs(parsed_url.query)
            uid = self.get_user_id(query_params)
            if self.guard_invalid_init(uid):
                return
            if path == "/api/user/address":
                try:
                    users_store.clear_home_address(uid)
                    self.send_json(200, {"ok": True})
                except Exception as exc:
                    logger.warning("Error clearing home address: %s", exc)
                    self.send_error_json(500, str(exc))
                return
            if path.startswith("/api/searches/"):
                search_id = path.replace("/api/searches/", "").strip()
                success = False
                if search_id:
                    success = delete_search(search_id, user_id=uid)
                    logger.info("Search '%s' deleted via DELETE method by user %s (success=%s)", search_id, uid, success)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "id": search_id, "deleted": success}).encode("utf-8"))
                return
            self.send_response(404)
            self.end_headers()

        def do_GET(self) -> None:
            parsed_url = urllib.parse.urlparse(self.path)
            path = parsed_url.path
            query_params = urllib.parse.parse_qs(parsed_url.query)
            uid = self.get_user_id(query_params)
            if self.guard_invalid_init(uid):
                return

            if path in ("/", "/index.html"):
                html_path = Path("index.html") if Path("index.html").exists() else (Path("web/index.html") if Path("web/index.html").exists() else Path("frontend/index.html"))
                if html_path.exists():
                    data = html_path.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(data)
                    return

            if path == "/api/export/lots.csv":
                try:
                    export_uid = (query_params.get("user_id", [""])[0] or uid).strip()
                    status, body = build_lots_csv(export_uid)
                    self.send_response(status)
                    if status == 200:
                        self.send_header("Content-Type", "text/csv; charset=utf-8")
                        self.send_header("Content-Disposition", 'attachment; filename="nakhodki.csv"')
                    else:
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as exc:
                    logger.warning("Error exporting lots csv: %s", exc)
                    self.send_error_json(500, str(exc))
                return

            if path == "/api/bundle":
                try:
                    bundle_data = generate_api_bundle(user_id=uid)
                    payload = json.dumps(bundle_data, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                except Exception as exc:
                    logger.warning("Error generating api bundle: %s", exc)

            if path in ("/health", "/api/health", "/healthz"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b'{"status":"ok","service":"avitoradar-backend"}\n')
                return

            if path == "/api/user":
                try:
                    asked_uid = (query_params.get("user_id", [""])[0] or uid).strip()
                    profile = build_user_block(asked_uid)
                    self.send_json(200, {"status": "ok", "user": profile})
                except Exception as exc:
                    logger.warning("Error getting user profile: %s", exc)
                    self.send_error_json(500, str(exc))
                return

            if path == "/api/address/suggest":
                try:
                    q = (query_params.get("q", [""])[0] or "").strip()
                    if len(q) < 3:
                        self.send_json(200, {"suggestions": []})
                        return
                    city_hint = ""
                    try:
                        ask_uid = (query_params.get("user_id", [""])[0] or uid).strip()
                        own_searches = list_searches(user_id=ask_uid)
                        if own_searches and own_searches[0].city:
                            city_hint = own_searches[0].city
                    except Exception:
                        city_hint = ""
                    suggestions = get_address_suggestions_cached(q, city=city_hint or None)
                    self.send_json(200, {"suggestions": suggestions})
                except Exception as exc:
                    logger.warning("Error getting address suggestions: %s", exc)
                    self.send_error_json(500, str(exc))
                return

            if path == "/api/suggest":
                try:
                    q = query_params.get("q", [""])[0].strip()
                    suggestions = get_query_suggestions(q)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True, "query": q, "suggestions": suggestions}, ensure_ascii=False).encode("utf-8"))
                    return
                except Exception as exc:
                    logger.warning("Error getting suggestions: %s", exc)

            if path == "/api/searches":
                try:
                    user_searches = list_searches(user_id=uid)
                    searches = [
                        {
                            "id": s.name,
                            "query": s.title,
                            "city": s.city,
                            "minPrice": s.min_price or 0,
                            "isActive": True
                        }
                        for s in user_searches
                    ]
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True, "count": len(searches), "searches": searches}, ensure_ascii=False).encode("utf-8"))
                    return
                except Exception as exc:
                    logger.warning("Error getting searches: %s", exc)

            if path == "/api/lots":
                try:
                    bundle = generate_api_bundle(user_id=uid)
                    search_id_filter = query_params.get("searchId", [""])[0].strip()
                    all_lots = []
                    for s_id, s_data in bundle.items():
                        if s_id == "user" or not isinstance(s_data, dict):
                            continue
                        if search_id_filter and search_id_filter != "all" and s_id != search_id_filter:
                            continue
                        for it in s_data.get("items", []):
                            all_lots.append({
                                "id": str(it["id"]),
                                "searchId": s_id,
                                "avitoUrl": it["url"],
                                "title": it["title"],
                                "price": it["price"],
                                "marketPrice": it.get("market_price", 0),
                                "discount": it.get("market_diff_percent", 0),
                                "marketMedian": it.get("market_median"),
                                "recommendedBuy": it.get("recommended_buy"),
                                "profitAbs": it.get("profit_abs"),
                                "profitPct": it.get("profit_pct"),
                                "dealBadge": it.get("deal_badge"),
                                "variant": it.get("variant"),
                                "marketSamples": it.get("market_samples"),
                                "marketIsGlobal": it.get("market_is_global", False),
                                "seller": {
                                    "name": it.get("seller_name", "Частник"),
                                    "type": "business" if "Магазин" in it.get("seller_type", "") else "private",
                                    "rating": it.get("seller_rating"),
                                    "location": it.get("address") or it.get("city", "Челябинск")
                                },
                                "publishedText": it.get("published_text", "сегодня"),
                                "images": it.get("images", []),
                                "description": it.get("description", ""),
                                "tags": it.get("tags", []),
                                "badges": it.get("badges", []),
                                "isComboListing": it.get("is_combo_listing", False),
                                "isInDescOrList": it.get("is_in_desc_or_list", False),
                                "isDefect": it.get("is_defect", False),
                                "defectType": it.get("defect_type"),
                                "isExchangeOrWtb": it.get("is_exchange_or_wtb", False),
                                "isAccessory": it.get("is_accessory", False),
                                "isMismatchedModel": it.get("is_mismatched_model", False),
                                "realPriceInDesc": it.get("real_price_in_desc"),
                                "isDismissed": False
                            })
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True, "count": len(all_lots), "lots": all_lots}, ensure_ascii=False).encode("utf-8"))
                    return
                except Exception as exc:
                    logger.warning("Error getting lots: %s", exc)

            # Static file serving fallback (js, css, images, etc.)
            rel_path = urllib.parse.unquote(path.lstrip("/"))
            # Защита от path traversal: запрещаем "..", скрытые файлы и чувствительные каталоги
            parts = [p for p in rel_path.replace("\\", "/").split("/") if p]
            path_is_safe = (
                bool(parts)
                and all(p not in ("..", ".") and not p.startswith(".") for p in parts)
                and parts[0] not in ("data", "output", "avito_radar", "backend", "node_modules", "tests")
            )
            if path_is_safe:
                for search_dir in [Path("."), Path("frontend"), Path("web")]:
                    candidate = (search_dir / "/".join(parts)).resolve()
                    if not candidate.is_relative_to(search_dir.resolve()):
                        continue
                    if candidate.is_file():
                        ext = candidate.suffix.lower()
                        mime_map = {
                            ".js": "application/javascript; charset=utf-8",
                            ".css": "text/css; charset=utf-8",
                            ".html": "text/html; charset=utf-8",
                            ".svg": "image/svg+xml",
                            ".png": "image/png",
                            ".jpg": "image/jpeg",
                            ".jpeg": "image/jpeg",
                            ".json": "application/json; charset=utf-8",
                            ".woff2": "font/woff2",
                            ".woff": "font/woff",
                        }
                        mime = mime_map.get(ext, "application/octet-stream")
                        try:
                            data = candidate.read_bytes()
                            self.send_response(200)
                            self.send_header("Content-Type", mime)
                            self.send_header("Access-Control-Allow-Origin", "*")
                            self.end_headers()
                            self.wfile.write(data)
                            return
                        except Exception as exc:
                            logger.debug("Error serving static file %s: %s", candidate, exc)

            self.send_response(404)
            self.end_headers()

        def do_POST(self) -> None:
            parsed_url = urllib.parse.urlparse(self.path)
            path = parsed_url.path
            query_params = urllib.parse.parse_qs(parsed_url.query)
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            req_data = {}
            try:
                req_data = json.loads(body)
            except Exception:
                pass
            uid = self.get_user_id(query_params, req_data)
            if self.guard_invalid_init(uid):
                return

            if path == "/api/user/address":
                try:
                    addr_uid = str(req_data.get("user_id") or uid).strip()

                    # Новый флоу: фронт присылает готовые координаты из автокомплита
                    lat_raw = req_data.get("lat")
                    lon_raw = req_data.get("lon")
                    if lat_raw is not None or lon_raw is not None:
                        try:
                            lat = float(lat_raw)
                            lon = float(lon_raw)
                        except (TypeError, ValueError):
                            self.send_error_json(400, "lat and lon must be numbers")
                            return
                        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                            self.send_error_json(400, "lat must be in -90..90, lon in -180..180")
                            return
                        display_name = str(req_data.get("display_name") or "").strip() or f"{lat}, {lon}"
                        users_store.set_home_address(addr_uid, display_name, lat, lon)
                        self.send_json(200, {"ok": True, "display_name": display_name, "lat": lat, "lon": lon})
                        return

                    addr = str(req_data.get("address") or "").strip()
                    if not addr:
                        users_store.clear_home_address(addr_uid)
                        self.send_json(200, {"ok": True, "cleared": True})
                        return
                    city_hint = ""
                    try:
                        own_searches = list_searches(user_id=addr_uid)
                        if own_searches and own_searches[0].city:
                            city_hint = own_searches[0].city
                    except Exception:
                        city_hint = ""
                    geo = geocode_address(addr, city=city_hint or None)
                    if not geo:
                        self.send_json(422, {"status": "error", "message": "Адрес не найден, уточните улицу и город"})
                        return
                    users_store.set_home_address(addr_uid, geo["display_name"], geo["lat"], geo["lon"])
                    self.send_json(200, {
                        "ok": True,
                        "display_name": geo["display_name"],
                        "lat": geo["lat"],
                        "lon": geo["lon"],
                    })
                except Exception as exc:
                    logger.warning("Error setting home address: %s", exc)
                    self.send_error_json(500, str(exc))
                return

            if path == "/api/user/quiet_hours":
                try:
                    q_uid = str(req_data.get("user_id") or uid).strip()
                    if q_uid in ("", "default"):
                        self.send_error_json(400, "user_id required")
                        return
                    enabled = bool(req_data.get("enabled"))
                    start = int(req_data.get("start", 23))
                    end = int(req_data.get("end", 8))
                    users_store.set_quiet_hours(q_uid, enabled, start, end)
                    self.send_json(200, {"ok": True})
                except (TypeError, ValueError) as exc:
                    self.send_error_json(400, f"invalid quiet hours: {exc}")
                except Exception as exc:
                    logger.warning("Error setting quiet hours: %s", exc)
                    self.send_error_json(500, str(exc))
                return

            if path == "/api/pay/stars":
                try:
                    plan_id = str(req_data.get("plan_id") or "").strip()
                    pay_uid = str(req_data.get("user_id") or uid).strip()
                    bot_token = str(os.environ.get("TELEGRAM_BOT_TOKEN", "")).strip()
                    if not billing.get_plan(plan_id):
                        self.send_error_json(400, "unknown plan_id")
                        return
                    link = billing.create_stars_invoice_link(bot_token, pay_uid, plan_id)
                    if not link:
                        self.send_error_json(502, "failed to create invoice link")
                        return
                    self.send_json(200, {"status": "ok", "invoice_link": link})
                except Exception as exc:
                    logger.warning("Error creating stars invoice: %s", exc)
                    self.send_error_json(500, str(exc))
                return

            if path == "/api/pay/yookassa":
                try:
                    plan_id = str(req_data.get("plan_id") or "").strip()
                    pay_uid = str(req_data.get("user_id") or uid).strip()
                    if not billing.get_plan(plan_id):
                        self.send_error_json(400, "unknown plan_id")
                        return
                    if not (os.environ.get("YOOKASSA_SHOP_ID", "").strip() and os.environ.get("YOOKASSA_SECRET", "").strip()):
                        self.send_error_json(501, "yookassa not configured")
                        return
                    payment_url = billing.get_yookassa_payment_url(pay_uid, plan_id)
                    if not payment_url:
                        self.send_error_json(502, "failed to create payment")
                        return
                    self.send_json(200, {"status": "ok", "payment_url": payment_url})
                except Exception as exc:
                    logger.warning("Error creating yookassa payment: %s", exc)
                    self.send_error_json(500, str(exc))
                return

            if path == "/api/trial":
                try:
                    trial_uid = str(req_data.get("user_id") or uid).strip()
                    if trial_uid == "default":
                        self.send_error_json(400, "user_id required")
                        return
                    result = users_store.grant_trial(trial_uid)
                    if result["ok"]:
                        self.send_json(200, {
                            "status": "ok",
                            "ok": True,
                            "pro_expires_at": result["user"].get("pro_expires_at"),
                        })
                    else:
                        self.send_json(200, {"status": "ok", "ok": False, "reason": result["reason"]})
                except Exception as exc:
                    logger.warning("Error granting trial: %s", exc)
                    self.send_error_json(500, str(exc))
                return

            if path == "/api/analysis":
                try:
                    an_uid = str(req_data.get("user_id") or uid).strip()
                    if an_uid == "default":
                        self.send_error_json(400, "user_id required")
                        return
                    allowed = users_store.use_analysis(an_uid)
                    if not allowed["allowed"]:
                        self.send_json(429, {
                            "status": "error",
                            "message": f"Лимит бесплатного тарифа: {allowed['limit']} анализа рынка в сутки. Оформите PRO для безлимита.",
                            "used": allowed["used"],
                            "limit": allowed["limit"],
                        })
                        return
                    search_name = str(req_data.get("search_name") or req_data.get("search") or "").strip()
                    query = str(req_data.get("query") or "").strip()
                    analysis = analyze_market_for(query=query, search_name=search_name, user_id=an_uid)
                    if not analysis:
                        self.send_error_json(404, "search or listings not found")
                        return
                    analysis["status"] = "ok"
                    analysis["analysis_used_today"] = allowed["used"]
                    analysis["analysis_limit"] = allowed["limit"]
                    self.send_json(200, analysis)
                except Exception as exc:
                    logger.warning("Error running analysis: %s", exc)
                    self.send_error_json(500, str(exc))
                return

            if path == "/webhook/yookassa":
                try:
                    result = billing.process_yookassa_webhook(req_data)
                    if result["ok"]:
                        self.send_json(200, {"status": "ok", "message": result["message"]})
                    else:
                        self.send_json(400, {"status": "error", "message": result["message"]})
                except Exception as exc:
                    logger.warning("Error processing yookassa webhook: %s", exc)
                    self.send_error_json(500, str(exc))
                return

            if path in ("/api/searches", "/api/searches/create"):
                try:
                    query = req_data.get("query", "").strip()
                    city = req_data.get("city", "chelyabinsk").strip()
                    min_price = int(req_data.get("min_price") or 0)
                    c_name = ""
                    s_rec = None
                    if query:
                        clean_city = (city or "").lower().strip()
                        if clean_city in ("rossiya", "россия", "вся россия", "vsya_rossiya", "vsya-rossiya", "all", "all_russia", "russia"):
                            city_slug = "rossiya"
                            loc_id = "621540"
                            city_display = "Вся Россия"
                        else:
                            city_slug = transliterate(city).replace(" ", "_").lower()
                            cache = load_locations_cache()
                            city_entry = (cache.get("cities") or {}).get(city_slug)
                            if not city_entry:
                                for k, v in (cache.get("cities") or {}).items():
                                    if str(v.get("name", "")).lower() == clean_city or k == clean_city:
                                        city_entry = v
                                        city_slug = k
                                        break
                            loc_id = str(city_entry["id"]) if city_entry else "661420"
                            city_display = city_entry.get("name", city) if city_entry else city

                        clean_q = transliterate(query).replace(" ", "_").lower()
                        c_name = re.sub(r"[^a-z0-9_-]+", "_", f"u{uid}_{clean_q}_{city_slug}").strip("_")
                        if not is_valid_search_name(c_name):
                            self.send_response(400)
                            self.send_header("Content-Type", "application/json; charset=utf-8")
                            self.send_header("Access-Control-Allow-Origin", "*")
                            self.end_headers()
                            self.wfile.write(json.dumps({"ok": False, "error": "invalid search name"}).encode("utf-8"))
                            return
                        encoded_q = urllib.parse.quote(query)
                        target_url = f"https://www.avito.ru/{city_slug}?q={encoded_q}"
                        if min_price > 0:
                            target_url += f"&pmin={min_price}"

                        s_rec = load_search(c_name)
                        if not s_rec:
                            limit = users_store.get_limits(uid)["max_searches"]
                            if uid not in ("default", "") and len(list_searches(user_id=uid)) >= limit:
                                self.send_error_json(403, f"Достигнут лимит радаров вашего тарифа ({limit}). Оформите PRO.")
                                return
                            s_rec = SearchRecord(
                                name=c_name,
                                title=query,
                                category_type="goods",
                                catalog_url=target_url,
                                city=city_display,
                                params={"q": query, "locationId": loc_id},
                                min_price=min_price if min_price > 0 else None,
                                user_id=str(uid),
                            )
                            save_search(s_rec)
                            logger.info("Search '%s' successfully created via API for user %s", c_name, uid)

                        # Trigger background scan of first page immediately
                        def _bg_scan(rec: SearchRecord) -> None:
                            try:
                                client = AvitoClient()
                                scan_search(rec, client=client, max_pages=1)
                                logger.info("Initial scan completed for %s", rec.name)
                            except Exception as e:
                                logger.warning("Bg scan error for %s: %s", rec.name, e)

                        threading.Thread(target=_bg_scan, args=(s_rec,), daemon=True).start()

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "ok": True,
                        "success": True,
                        "name": c_name,
                        "search": {
                            "id": s_rec.name if s_rec else c_name,
                            "query": s_rec.title if s_rec else query,
                            "city": s_rec.city if s_rec else city,
                            "minPrice": s_rec.min_price or 0 if s_rec else min_price,
                            "isActive": True
                        }
                    }, ensure_ascii=False).encode("utf-8"))
                    return
                except Exception as exc:
                    logger.warning("Error creating search from API: %s", exc)
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": str(exc)}).encode("utf-8"))
                    return

            if path in ("/api/searches/delete", "/api/delete"):
                try:
                    name = (req_data.get("name") or req_data.get("id") or "").strip()
                    success = False
                    if name:
                        success = delete_search(name, user_id=uid)
                        logger.info("Search '%s' deleted via API by user %s (success=%s)", name, uid, success)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True, "deleted": name, "success": success}).encode("utf-8"))
                    return
                except Exception as exc:
                    logger.warning("Error deleting search via API: %s", exc)
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": str(exc)}).encode("utf-8"))
                    return

            if path in ("/api/searches/scan", "/api/scan"):
                try:
                    name = (req_data.get("name") or req_data.get("id") or "").strip()
                    count = 0
                    if name:
                        s_rec = load_search(name)
                        if s_rec:
                            cl = AvitoClient()
                            count, _excel_path = scan_search(s_rec, client=cl, max_pages=1)
                    bundle_data = generate_api_bundle(user_id=uid)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True, "count": count, "searchId": name, "bundle": bundle_data}).encode("utf-8"))
                    return
                except Exception as exc:
                    logger.warning("Error scanning search via API: %s", exc)
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": str(exc)}).encode("utf-8"))
                    return

            if "/dismiss" in path:
                # POST /api/lots/<id>/dismiss
                parts = path.strip("/").split("/")
                lot_id = parts[2] if len(parts) >= 3 else ""
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "id": lot_id, "isDismissed": True}).encode("utf-8"))
                return

            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            pass  # Suppress noisy HTTP healthcheck logs

    try:
        server = http.server.ThreadingHTTPServer(("0.0.0.0", port), MiniAppServerHandler)
        logger.info("MiniApp & Healthcheck HTTP server listening on port %d", port)
        server.serve_forever()
    except Exception as exc:
        logger.warning("Could not start healthcheck server on port %d: %s", port, exc)


def start_bot_service() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        force=True,
    )
    from avito_radar.storage.git_sync import restore_data, start_sync_thread

    restore_data()
    start_sync_thread()

    if not acquire_bot_lock():
        logger.warning("Бот уже запущен в другом процессе! Повторный запуск остановлен.")
        print("⚠️ Бот уже запущен в другом процессе! (Вторая копия остановлена)")
        return

    # Start HTTP healthcheck server for Hugging Face / cloud containers
    threading.Thread(target=start_healthcheck_server, daemon=True).start()

    cfg = load_telegram_config()
    if not cfg:
        print("Telegram не настроен! Запустите: python run.py telegram --setup")
        return

    bot = AvitoTelegramBot(cfg)
    bot.run_polling()
