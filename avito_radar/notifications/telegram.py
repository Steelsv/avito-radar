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
    lines = [
        f"🔔 <b>{html.escape(item.title)}</b>",
        f"💰 <b>{html.escape(item.price_formatted)}</b>",
    ]

    if item.market_price:
        market_str = f"{item.market_price:,} ₽".replace(",", " ")
        diff_str = f"{item.market_diff_percent}%" if item.market_diff_percent else ""
        if (item.market_diff_percent or 0) < 0:
            lines.append(f"🔥 <i>Ниже рынка на {abs(item.market_diff_percent or 0)}% (рынок ~{market_str})</i>")
        else:
            lines.append(f"📊 <i>Рыночная цена ~{market_str} ({diff_str})</i>")

    loc_parts = []
    if item.city:
        loc_parts.append(item.city)
    if item.metro:
        loc_parts.append(f"м. {item.metro}")
    elif item.address:
        loc_parts.append(item.address)
    if loc_parts:
        lines.append(f"📍 {html.escape(' · '.join(loc_parts))}")

    # Seller
    seller_info = item.seller_name or item.seller_type
    if item.seller_rating:
        seller_info += f" (⭐ {item.seller_rating})"
    if item.closed_listings is not None:
        seller_info += f", сделок: {item.closed_listings}"
    lines.append(f"👤 {html.escape(seller_info)}")

    if item.total_views is not None:
        lines.append(f"👁 Просмотров: {item.total_views} (+{item.today_views or 0} сегодня)")

    if item.tags:
        lines.append("🏷 " + " · ".join(html.escape(t) for t in item.tags))

    lines.append(f'\n👉 <a href="{html.escape(item.url)}">Открыть на Авито</a>')
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
        api_request(self.config.token, "sendMessage", {
            "chat_id": self.config.chat_id,
            "text": "🚀 <b>Avito Radar подключён!</b>\n\nУведомления о новых объявлениях будут приходить сюда в реальном времени.",
            "parse_mode": "HTML",
        })
