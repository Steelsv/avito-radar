"""Telegram notification service for new Avito listings."""

from __future__ import annotations

import html
import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from avito_radar.parsers.item_parser import ParsedItem
from avito_radar.storage.db import DATA_DIR, load_json, save_json

logger = logging.getLogger(__name__)
TELEGRAM_CONFIG_PATH = DATA_DIR / "telegram.json"
API_URL = "https://api.telegram.org/bot{token}/{method}"


# Custom Telegram Emojis (Telegram iOS Icons pack: https://emoji.wivvi.net / tgiosicons)
TG_EMOJI_LIGHTNING = "5884428842780594914"  # ⚡
TG_EMOJI_LINK = "6028171274939797252"       # 🔗
TG_EMOJI_RADAR = "6037397706505195857"      # 👁
TG_EMOJI_SEARCH = "6032850693348399258"     # 🔎
TG_EMOJI_PROFILE = "6035084557378654059"    # 👤
TG_EMOJI_PIN = "6042011682497106307"        # 📍
TG_EMOJI_STAR = "6034923938486684992"       # ⭐️
TG_EMOJI_CHECK = "5774022692642492953"      # ✅
TG_EMOJI_WARN = "6030563507299160824"       # ❗️
TG_EMOJI_TRASH = "6039522349517115015"      # 🗑
TG_EMOJI_GROWTH = "5938539885907415367"     # 📈
TG_EMOJI_COIN = "5890848474563352982"       # 🪙
TG_EMOJI_BOX = "5884479287171485878"        # 📦
TG_EMOJI_SHIELD = "6030445631921721471"     # 🛡
TG_EMOJI_REPEAT = "6030657343744644592"     # 🔁
TG_EMOJI_STORE = "5920332557466997677"      # 🏪
TG_EMOJI_CLOCK = "5983150113483134607"      # ⏰

def tg_e(emoji_id: str, fallback: str) -> str:
    """Format custom Telegram emoji tag."""
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


@dataclass
class TelegramConfig:
    token: str
    chat_id: int | str
    enabled: bool = True


def load_telegram_config() -> TelegramConfig | None:
    data = load_json(TELEGRAM_CONFIG_PATH)
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or data.get("token")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or data.get("chat_id")
    if token and chat_id:
        return TelegramConfig(token=str(token), chat_id=chat_id, enabled=bool(data.get("enabled", True)))
    return None


def save_telegram_config(config: TelegramConfig) -> None:
    save_json(TELEGRAM_CONFIG_PATH, {
        "token": config.token,
        "chat_id": config.chat_id,
        "enabled": config.enabled,
    })


def api_request(token: str, method: str, payload: dict[str, Any] | None = None) -> Any:
    url = API_URL.format(token=token, method=method)
    req = urllib.request.Request(
        url,
        data=json.dumps(payload or {}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            if not res_data.get("ok"):
                raise RuntimeError(res_data.get("description", "Unknown Telegram error"))
            return res_data.get("result")
    except urllib.error.HTTPError as exc:
        try:
            err = json.loads(exc.read().decode("utf-8")).get("description")
        except Exception:
            err = exc.reason
        raise RuntimeError(f"Telegram API {exc.code}: {err}") from exc
    except Exception as exc:
        raise RuntimeError(f"Ошибка связи с Telegram: {exc}") from exc


def auto_detect_chat_id(token: str) -> tuple[int, str]:
    """Find chat ID from latest /start update."""
    updates = api_request(token, "getUpdates", {"timeout": 0})
    for upd in reversed(updates or []):
        msg = upd.get("message") or upd.get("my_chat_member") or {}
        chat = msg.get("chat") or {}
        if "id" in chat:
            title = chat.get("username") or chat.get("first_name") or chat.get("title") or str(chat["id"])
            return int(chat["id"]), str(title)
    raise RuntimeError("Бот ещё не получил ни одного сообщения. Отправьте ему /start в Telegram и повторите.")


def format_ad_message(search_title: str, item: ParsedItem) -> str:
    e_growth = tg_e(TG_EMOJI_GROWTH, "📈")
    e_coin = tg_e(TG_EMOJI_COIN, "🪙")
    e_warn = tg_e(TG_EMOJI_WARN, "❗️")
    e_pin = tg_e(TG_EMOJI_PIN, "📍")
    e_user = tg_e(TG_EMOJI_PROFILE, "👤")
    e_star = tg_e(TG_EMOJI_STAR, "⭐️")
    e_radar = tg_e(TG_EMOJI_RADAR, "👁")
    e_lightning = tg_e(TG_EMOJI_LIGHTNING, "⚡")

    is_top_deal = item.market_diff_percent and item.market_diff_percent <= -12 and not item.is_combo_listing
    header = f"{e_growth} <b>НАЙДЕН ВЫГОДНЫЙ ЛОТ ({item.market_diff_percent}%)</b>" if is_top_deal else f"{e_radar} <b>{html.escape(item.title)}</b>"

    lines = [
        header,
        f"<b>{html.escape(item.title)}</b>" if is_top_deal else "",
        f"{e_coin} <b>{html.escape(item.price_formatted)}</b>",
    ]
    lines = [l for l in lines if l]

    if item.market_price:
        market_str = f"{item.market_price:,} ₽".replace(",", " ")
        if item.is_combo_listing:
            real_str = f"{item.real_price_in_desc:,} ₽".replace(",", " ") if item.real_price_in_desc else "в тексте"
            lines.append(f"{e_warn} <i>Внимание: в описании целевой товар от ~{real_str}</i>")
        elif (item.market_diff_percent or 0) < 0:
            diff_abs = abs(round(item.market_diff_percent or 0, 1))
            lines.append(f"{e_growth} <i>Ниже рынка на {diff_abs}% (оценка рынка ~{market_str})</i>")
        else:
            lines.append(f"<i>Рыночная цена ~{market_str} ({item.market_diff_percent:+.1f}%)</i>")

    loc_parts = []
    if item.city:
        loc_parts.append(item.city)
    if item.metro:
        loc_parts.append(f"м. {item.metro}")
    elif item.address:
        loc_parts.append(item.address)
    if loc_parts:
        lines.append(f"{e_pin} {html.escape(' · '.join(loc_parts))}")

    # Seller
    seller_name = html.escape(item.seller_name or item.seller_type or "Частное лицо")
    rating_part = f" ({e_star} {item.seller_rating})" if item.seller_rating else ""
    deals_part = f", {item.closed_listings} сделок" if item.closed_listings is not None else ""
    lines.append(f"{e_user} {seller_name}{rating_part}{deals_part}")

    if item.tags:
        clean_tags = [t for t in item.tags if not t.startswith("🔥 Выгодно") and not t.startswith("Выгодно")]
        if clean_tags:
            lines.append("· " + " · ".join(html.escape(t) for t in clean_tags[:3]))

    lines.append(f"\n{e_lightning} <i>Откройте терминал для полной аналитики и сравнения лотов</i>")
    lines.append(f"<i>Поиск: #{html.escape(search_title.replace(' ', '_'))}</i>")

    return "\n".join(lines)


class TelegramNotifier:
    def __init__(self, config: TelegramConfig) -> None:
        self.config = config

    def send_notification(self, search_title: str, item: ParsedItem) -> bool:
        if not self.config.enabled:
            return False

        text = format_ad_message(search_title, item)
        # If photo available, try sending photo first
        if item.images:
            try:
                api_request(self.config.token, "sendPhoto", {
                    "chat_id": self.config.chat_id,
                    "photo": item.images[0],
                    "caption": text,
                    "parse_mode": "HTML",
                })
                return True
            except Exception as exc:
                logger.warning("Failed to send photo, falling back to text: %s", exc)

        # Fallback to text message
        api_request(self.config.token, "sendMessage", {
            "chat_id": self.config.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        })
        return True

    def send_test_message(self) -> None:
        e_lightning = tg_e(TG_EMOJI_LIGHTNING, "⚡")
        api_request(self.config.token, "sendMessage", {
            "chat_id": self.config.chat_id,
            "text": f"{e_lightning} <b>Avito Radar подключён!</b>\n\nУведомления о новых объявлениях будут приходить сюда в реальном времени.",
            "parse_mode": "HTML",
        })
