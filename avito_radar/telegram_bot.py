"""Interactive Telegram Bot service for Avito Radar.

Allows users to manage searches, start monitoring, select city and product,
and receive Excel spreadsheets directly through Telegram buttons and commands.
"""

from __future__ import annotations

import html
import http.server
import json
import logging
import os
import re
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

from avito_radar.analysis.classifier import classify_item, extract_goods_group, is_likely_fake_or_junk
from avito_radar.analysis.market import annotate_market_prices
from avito_radar.config import AppSettings, load_settings, save_settings
from avito_radar.core.client import AvitoClient
from avito_radar.engine import create_search_from_url, scan_search
from avito_radar.exporters.excel import export_to_excel
from avito_radar.notifications.telegram import (
    TG_EMOJI_CHECK,
    TG_EMOJI_COIN,
    TG_EMOJI_GROWTH,
    TG_EMOJI_LIGHTNING,
    TG_EMOJI_LINK,
    TG_EMOJI_PIN,
    TG_EMOJI_PROFILE,
    TG_EMOJI_RADAR,
    TG_EMOJI_SEARCH,
    TG_EMOJI_SHIELD,
    TG_EMOJI_STAR,
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
    list_searches,
    load_listings,
    load_locations_cache,
    load_search,
    load_seen,
    save_listings,
    save_search,
    save_seen,
)

logger = logging.getLogger(__name__)

_LOCK_FILE_HANDLE = None


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


# Format: (label, query, category_path, default_pmin)
POPULAR_PRODUCTS = [
    ("⚡ DDR5 32GB 6000MHz", "DDR5 32GB 6000MHz", "tovary_dlya_kompyutera/komplektuyuschie/operativnaya_pamyat", 7000),
    ("💻 RTX 4070 Super", "RTX 4070 Super", "tovary_dlya_kompyutera/komplektuyuschie/videokarty", 50000),
    ("📱 iPhone 16 Pro Max", "iPhone 16 Pro Max", "telefony/mobilnye_telefony/apple", 90000),
    ("📱 iPhone 15 128GB", "iPhone 15", "telefony/mobilnye_telefony/apple", 45000),
    ("🎮 PlayStation 5 Slim", "PlayStation 5 Slim", "igry_pristavki_i_programmy/igrovye_pristavki", 38000),
    ("⚡ Ryzen 7 7800X3D", "Ryzen 7 7800X3D", "tovary_dlya_kompyutera/komplektuyuschie/processory", 28000),
    ("💻 MacBook Air M2 / M3", "MacBook Air M2", "noutbuki/apple", 65000),
    ("🎮 Steam Deck OLED", "Steam Deck OLED", "igry_pristavki_i_programmy/igrovye_pristavki", 45000),
    ("🚗 Lada Vesta SW Cross", "Lada Vesta SW Cross", "avtomobili", 700000),
    ("🚗 BMW 320d (G20)", "BMW 320d M Sport", "avtomobili", 2500000),
    ("🚗 Toyota Camry 2.5", "Toyota Camry 2.5", "avtomobili", 2000000),
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
        caption = format_ad_message(search_title, item)
        base_url = os.environ.get("MINI_APP_URL", "https://avito-radar.onrender.com/").rstrip("/")
        miniapp_url = f"{base_url}/?user_id={chat_id}"
        kb = {
            "inline_keyboard": [
                [
                    {
                        "text": "⚡️ ТЕРМИНАЛ РАДАРА (MINI APP)",
                        "web_app": {"url": miniapp_url},
                    }
                ],
                [
                    {
                        "text": "🔗 Открыть на Авито",
                        "url": item.url,
                    },
                    {
                        "text": "👁️ Скрыть лот",
                        "callback_data": f"vanish_{item.id}",
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
                        "text": "⚡️ ТЕРМИНАЛ РАДАРА (MINI APP)",
                        "web_app": {"url": miniapp_url},
                    }
                ],
                [
                    {
                        "text": "➕ СОЗДАТЬ НОВЫЙ РАДАР",
                        "callback_data": "menu_add",
                    }
                ],
                [
                    {
                        "text": "📋 МОИ РАДАРЫ И ВЫГРУЗКА",
                        "callback_data": "menu_list",
                    }
                ],
                [
                    {
                        "text": "⚙️ НАСТРОЙКИ МОНИТОРИНГА 24/7",
                        "callback_data": "menu_settings",
                    }
                ],
            ]
        }

    def send_main_menu(self, chat_id: int, message_id: int | None = None) -> None:
        session = self.get_session(chat_id)
        session.state = "IDLE"
        watch_status = "24/7 Активен" if self.monitoring_active else "Выключен"
        searches = list_searches(user_id=chat_id)
        text = (
            f"🏛 <b>AVITO RADAR // TERMINAL</b>\n"
            f"<i>Премиальный мониторинг выгодных предложений</i>\n\n"
            f"🟢 <b>Статус:</b> <code>{watch_status}</code> (интервал: 15 мин)\n"
            f"🎯 <b>Отслеживаемых радаров:</b> <code>{len(searches)} шт.</code>\n\n"
            f"⚡ <b>Все функции доступны в едином терминале:</b>\n"
            f"• 🔎 Мгновенный поиск товаров и авто с автодополнением\n"
            f"• 📊 Оценка рыночной стоимости и подсветка максимальной выгоды\n"
            f"• 🛡 Защита от байт-цен (100 ₽), дефектов и мусора\n"
            f"• 📈 Режим интерактивной таблицы прямо в Telegram\n\n"
            f"<i>Уведомления о новых предложениях ниже рынка поступают мгновенно.</i>"
        )
        self.render_menu(chat_id, text, self.main_menu_keyboard(chat_id), message_id=message_id)

    def send_add_menu(self, chat_id: int, message_id: int | None = None) -> None:
        text = (
            "📡 <b>НАСТРОЙКА НОВОГО РАДАРА</b>\n\n"
            "Выберите способ настройки отслеживания:"
        )
        kb = {
            "inline_keyboard": [
                [{"text": "⚡️ Выбрать товар и город (Каталог)", "callback_data": "add_wizard_product"}],
                [{"text": "🔗 Вставить скопированную ссылку с Авито", "callback_data": "add_by_url"}],
                [{"text": "🔙 Назад в главное меню", "callback_data": "menu_main"}],
            ]
        }
        self.render_menu(chat_id, text, kb, message_id=message_id)

    def send_product_selection(self, chat_id: int, message_id: int | None = None) -> None:
        text = (
            "📡 <b>ШАГ 1 ИЗ 2: ЧТО ОТСЛЕЖИВАТЬ?</b>\n\n"
            "Выберите популярную категорию или введите свой запрос:"
        )
        buttons = []
        for idx, (label, *_) in enumerate(POPULAR_PRODUCTS):
            buttons.append([{"text": label, "callback_data": f"pick_prod_{idx}"}])
        buttons.append([{"text": "✏️ Ввести другое название вручную", "callback_data": "pick_prod_custom"}])
        buttons.append([{"text": "🔙 Назад в меню", "callback_data": "menu_add"}])
        kb = {"inline_keyboard": buttons}
        self.render_menu(chat_id, text, kb, message_id=message_id)

    def send_city_selection(self, chat_id: int, message_id: int | None = None) -> None:
        session = self.get_session(chat_id)
        text = (
            f"📍 <b>ШАГ 2 ИЗ 2: ВЫБОР РЕГИОНА</b>\n\n"
            f"Товар: <b>{html.escape(session.temp_query)}</b>\n\n"
            f"Выберите город или отслеживание по всей стране:"
        )
        buttons = []
        for label, slug in POPULAR_CITIES:
            icon = "🌐" if slug == "rossiya" else "📍"
            buttons.append([{"text": f"{icon} {label}", "callback_data": f"pick_city_{slug}_{label}"}])
        buttons.append([{"text": "✏️ Ввести другой город вручную", "callback_data": "pick_city_custom"}])
        buttons.append([{"text": "🔙 Назад к товарам", "callback_data": "add_wizard_product"}])
        kb = {"inline_keyboard": buttons}
        self.render_menu(chat_id, text, kb, message_id=message_id)

    def send_searches_list(self, chat_id: int, message_id: int | None = None) -> None:
        searches = list_searches(user_id=chat_id)
        if not searches:
            text = (
                "📋 <b>АКТИВНЫЕ РАДАРЫ</b>\n\n"
                "У вас пока нет сохранённых поисков.\n"
                "Нажмите кнопку ниже, чтобы запустить первый радар!"
            )
            kb = {
                "inline_keyboard": [
                    [{"text": "➕ ДОБАВИТЬ НОВЫЙ РАДАР", "callback_data": "menu_add"}],
                    [{"text": "🔙 В главное меню", "callback_data": "menu_main"}],
                ]
            }
            self.render_menu(chat_id, text, kb, message_id=message_id)
            return

        text = f"📋 <b>АКТИВНЫЕ РАДАРЫ ({len(searches)} шт.):</b>\n\n"
        buttons = []
        for idx, s in enumerate(searches, start=1):
            listings = load_listings(s)
            pmin_info = f" · от {s.min_price:,} ₽" if s.min_price else ""
            acc_status = "ВКЛ ✅" if getattr(s, "exclude_accessories", True) else "ВЫКЛ ❌"
            text += f"<b>{idx}. {html.escape(s.title)}</b>\n"
            text += f"   📍 {html.escape(s.city)} · В базе: {len(listings)} лотов{pmin_info} · Без аксов: {acc_status}\n\n"
            buttons.append([
                {"text": f"🛡 Без аксов ({acc_status})", "callback_data": f"toggle_acc_{s.name}"},
                {"text": f"💰 Порог ({s.min_price or '0'} ₽)", "callback_data": f"set_pmin_{s.name}"},
            ])
            buttons.append([
                {"text": f"📊 Скачать Excel — {s.title}", "callback_data": f"action_scan_{s.name}"},
                {"text": f"🗑 Удалить «{s.title}»", "callback_data": f"action_del_{s.name}"},
            ])

        buttons.append([{"text": "➕ СОЗДАТЬ ЕЩЁ РАДАР", "callback_data": "menu_add"}])
        buttons.append([{"text": "🔙 В главное меню", "callback_data": "menu_main"}])

        kb = {"inline_keyboard": buttons}
        self.render_menu(chat_id, text, kb, message_id=message_id)

    def send_settings_menu(self, chat_id: int, message_id: int | None = None) -> None:
        self.settings = load_settings()
        priv_text = "👤 Продавцы: ТОЛЬКО ЧАСТНИКИ ✅" if self.settings.alert_private_only else "👥 Продавцы: ВСЕ (с магазинами) ❌"
        junk_text = "🛡 Анти-мусор и байт-цены: ВКЛЮЧЕНО ✅" if self.settings.alert_filter_junk else "⚠️ Анти-мусор: ВЫКЛЮЧЕНО ❌"
        acc_text = "🛡 Исключать аксессуары: ВКЛЮЧЕНО ✅" if getattr(self.settings, "alert_filter_accessories", True) else "⚠️ Исключать аксессуары: ВЫКЛЮЧЕНО ❌"
        text = (
            "⚙️ <b>НАСТРОЙКИ МОНИТОРИНГА 24/7</b>\n\n"
            f"• Проверка новинок: <b>каждые {self.settings.watch_interval:.0f} сек</b>\n"
            f"• Фильтр продавцов: <b>{'Только частники' if self.settings.alert_private_only else 'Все предложения'}</b>\n"
            f"• Фильтр фейковых цен (100 ₽): <b>{'Активен ✅' if self.settings.alert_filter_junk else 'Выключен'}</b>\n"
            f"• Фильтр аксессуаров / запчастей: <b>{'Активен ✅' if getattr(self.settings, 'alert_filter_accessories', True) else 'Выключен'}</b>\n"
            f"• Игнорировать дубликаты: <b>{'Да' if self.settings.alert_no_republished else 'Нет'}</b>\n\n"
            "Нажмите на нужную кнопку для переключения параметра:"
        )
        kb = {
            "inline_keyboard": [
                [{"text": priv_text, "callback_data": "set_toggle_private"}],
                [{"text": junk_text, "callback_data": "set_toggle_junk"}],
                [{"text": acc_text, "callback_data": "set_toggle_accessories"}],
                [{"text": "⏱ Проверка раз в 1 минуту", "callback_data": "set_interval_60"}],
                [{"text": "⏱ Проверка раз в 2 минуты", "callback_data": "set_interval_120"}],
                [{"text": "⏱ Проверка раз в 5 минут", "callback_data": "set_interval_300"}],
                [{"text": "🔙 В главное меню", "callback_data": "menu_main"}],
            ]
        }
        self.render_menu(chat_id, text, kb, message_id=message_id)

    # --- Search Creation Logic ---

    def process_create_search(self, chat_id: int, url: str, custom_name: str | None = None, message_id: int | None = None) -> None:
        self.render_menu(
            chat_id,
            "⏳ <b>Анализирую параметры и фильтры на Авито...</b>\nПодождите пару секунд.",
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
            pmin_str = f"\n💰 Мин. цена: {rec.min_price:,} ₽" if rec.min_price else ""
            text = (
                f"✅ <b>Поиск успешно настроен и сохранён!</b>\n\n"
                f"📌 <b>{html.escape(rec.title)}</b>\n"
                f"📍 Город: {html.escape(rec.city)}{pmin_str}\n"
                f"🏷 Категория: {html.escape(rec.category_type)}\n"
                f"🔑 Имя: <code>{rec.name}</code>\n\n"
                f"Что сделать прямо сейчас?"
            )
            kb = {
                "inline_keyboard": [
                    [{"text": "📊 Скачать Excel", "callback_data": f"action_scan_{rec.name}"}],
                    [{"text": f"💰 Мин. цена ({rec.min_price or 'нет'})", "callback_data": f"set_pmin_{rec.name}"}],
                    [{"text": "📋 Перейти к моим поискам", "callback_data": "menu_list"}],
                    [{"text": "🔙 В главное меню", "callback_data": "menu_main"}],
                ]
            }
            self.render_menu(chat_id, text, kb, message_id=message_id)
        except Exception as exc:
            self.render_menu(
                chat_id,
                f"❌ <b>Не удалось добавить поиск:</b> {html.escape(str(exc))}\nПопробуйте ещё раз или скопируйте другую ссылку.",
                {"inline_keyboard": [[{"text": "🔙 В главное меню", "callback_data": "menu_main"}]]},
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

        watch_status = "24/7 Активен" if self.monitoring_active else "Выключен"
        searches = list_searches(user_id=chat_id)
        base_url = os.environ.get("MINI_APP_URL", "https://avito-radar.onrender.com/").rstrip("/")
        miniapp_url = f"{base_url}/?user_id={chat_id}"

        text = (
            f"🏛 <b>AVITO RADAR // СТАТУС СЕРВЕРА</b>\n\n"
            f"⏱ <b>Время работы (Uptime):</b> <code>{uptime_str}</code>\n"
            f"🟢 <b>Мониторинг 24/7:</b> <code>{watch_status}</code> (интервал: 15 мин)\n"
            f"🎯 <b>Активных радаров:</b> <code>{len(searches)} шт.</code>\n"
            f"📡 <b>Healthcheck:</b> <code>200 OK</code> (/health)\n\n"
            f"<i>Терминал готов к работе на iOS, Android и Desktop.</i>"
        )
        kb = {
            "inline_keyboard": [
                [
                    {
                        "text": "⚡️ ТЕРМИНАЛ РАДАРА (MINI APP)",
                        "web_app": {"url": miniapp_url},
                    }
                ],
                [
                    {
                        "text": "🔙 Главное меню",
                        "callback_data": "menu_main",
                    }
                ]
            ]
        }
        self.render_menu(chat_id, text, kb)

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

        # /status command
        if text.startswith("/status"):
            session.state = "IDLE"
            self.send_status_message(chat_id)
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

    def handle_callback_query(self, query: dict[str, Any]) -> None:
        cb_id = query.get("id") or ""
        msg = query.get("message") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        message_id = msg.get("message_id")
        data = str(query.get("data") or "")

        if not chat_id:
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
                                new_row.append({"text": "👁️ Лот скрыт", "callback_data": "noop"})
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
                    "✏️ <b>Введите название товара</b> (например: <code>iPhone 15</code>, <code>RTX 4060</code>, <code>PlayStation 5</code>):\n\n"
                    "<i>Отправьте название сообщением в чат.</i>",
                    {"inline_keyboard": [[{"text": "🔙 Отмена", "callback_data": "add_wizard_product"}]]},
                    message_id=message_id,
                )
            else:
                try:
                    idx = int(val)
                    label, query, cat_path, pmin = POPULAR_PRODUCTS[idx]
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
                    "✏️ <b>Введите название города</b> (например: <code>Челябинск</code>, <code>Сочи</code>, <code>Тюмень</code>):\n\n"
                    "<i>Отправьте название сообщением в чат.</i>",
                    {"inline_keyboard": [[{"text": "🔙 Отмена", "callback_data": "add_wizard_product"}]]},
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
                self.process_create_search(chat_id, target_url, custom_name=c_name, message_id=message_id)

        elif data == "add_by_url":
            session.state = "WAIT_URL"
            self.render_menu(
                chat_id,
                "🔗 <b>Отправьте сюда скопированную ссылку с Авито</b> (с любыми фильтрами):\n\n"
                "<i>Вставьте ссылку сообщением в чат.</i>",
                {"inline_keyboard": [[{"text": "🔙 Отмена", "callback_data": "menu_main"}]]},
                message_id=message_id,
            )

        elif data.startswith("action_scan_"):
            search_name = data[len("action_scan_"):]
            s = load_search(search_name)
            if not s:
                self.render_menu(chat_id, f"❌ Поиск «{search_name}» не найден.", message_id=message_id)
                return

            self.render_menu(
                chat_id,
                f"⏳ <b>Формирую Excel таблицу для «{html.escape(s.title)}»...</b>\n\n"
                f"Собираю объявления, рассчитываю медианы цен и анализирую выгоду.\n"
                f"Файл таблицы сейчас появится ниже 👇",
                {"inline_keyboard": [[{"text": "📋 К моим поискам", "callback_data": "menu_list"}]]},
                message_id=message_id,
            )

            def run_scan() -> None:
                client = AvitoClient(delay=3.0)
                try:
                    count, excel_path = scan_search(s, client=client, max_pages=15)
                    self.send_document(
                        chat_id,
                        excel_path,
                        caption=f"📊 <b>Таблица готова!</b>\nПоиск: <b>{html.escape(s.title)}</b>\nСобрано лотов: <b>{count}</b> шт.",
                    )
                    self.send_searches_list(chat_id, message_id=message_id)
                except Exception as exc:
                    self.render_menu(
                        chat_id,
                        f"❌ Ошибка сбора: {html.escape(str(exc))}",
                        {"inline_keyboard": [[{"text": "🔙 В меню", "callback_data": "menu_main"}]]},
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
                f"💰 <b>Настройка минимальной цены для «{html.escape(s.title)}»</b>\n\n"
                f"Текущая мин. цена: <b>{pmin_curr}</b>\n\n"
                f"✏️ <b>Отправьте число в чат</b> (например: <code>35000</code>), чтобы отсечь мусор и байт-цены.\n"
                f"Или отправьте <code>0</code>, чтобы снять ограничение.",
                {"inline_keyboard": [[{"text": "🔙 Отмена", "callback_data": "menu_list"}]]},
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

                    for page_num in range(1, s.watch_pages + 1):
                        page = client.fetch_catalog_page(
                            catalog_url=s.catalog_url,
                            params=params,
                            page_number=page_num,
                        )

                        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                        for raw in page.items:
                            item_id = str(raw["id"])
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

                            # Calculate market diff
                            parsed_list = []
                            for it in listings.values():
                                p_it = parse_catalog_item(it)
                                classify_item(p_it, category_type=s.category_type, search_query=q_str)
                                parsed_list.append(p_it)
                            annotate_market_prices(
                                parsed_list,
                                group_key_fn=lambda x: extract_goods_group(x.title) if s.category_type == "goods" else "all",
                            )
                            # Update parsed item stats
                            for it in parsed_list:
                                if it.id == parsed.id:
                                    parsed.market_price = it.market_price
                                    parsed.market_diff_percent = it.market_diff_percent
                                    parsed.tags = it.tags
                                    break

                            append_alert(s, parsed)
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
                                    self.send_photo_alert(target_chat_id, parsed, s.title)
                                except Exception as alert_err:
                                    logger.warning("Failed to send alert to user %s for %s: %s", target_chat_id, s.name, alert_err)

                    if changed:
                        save_listings(s, listings)
                        save_seen(s, seen)

                    if is_first_pass:
                        self.primed_searches.add(s.name)

                except Exception as exc:
                    logger.warning("Watch check error for %s: %s", s.name, exc)

            time.sleep(self.settings.watch_interval)

    # --- Main polling runner ---

    def run_polling(self) -> None:
        self.is_running = True
        logger.info("Starting Telegram bot polling for %s...", self.config.chat_id)

        # Start background watchdog thread
        watch_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        watch_thread.start()

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
                    if "message" in upd:
                        self.handle_text_message(upd["message"])
                    elif "callback_query" in upd:
                        self.handle_callback_query(upd["callback_query"])

            except Exception as exc:
                logger.error("Polling error: %s", exc)
                time.sleep(2)


def generate_api_bundle(user_id: str | int | None = None) -> dict[str, Any]:
    """Compile cached search listings and market analysis for Mini App."""
    bundle: dict[str, Any] = {}
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
        annotate_market_prices(items)

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
                    "real_price_in_desc": it.real_price_in_desc,
                    "is_combo_listing": it.is_combo_listing,
                    "is_accessory": getattr(it, "is_accessory", False),
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
                }
                for it in items
            ],
        }
    return bundle


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
            rel_path = path.lstrip("/")
            if rel_path:
                for search_dir in [Path("."), Path("frontend"), Path("web")]:
                    candidate = (search_dir / rel_path).resolve()
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
                        encoded_q = urllib.parse.quote(query)
                        target_url = f"https://www.avito.ru/{city_slug}?q={encoded_q}"
                        if min_price > 0:
                            target_url += f"&pmin={min_price}"

                        s_rec = load_search(c_name)
                        if not s_rec:
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
                            count = scan_search(s_rec, client=cl, max_pages=1)
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
