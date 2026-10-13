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
    ("📱 iPhone 16", "iPhone 16", "telefony/mobilnye_telefony/apple", 50000),
    ("📱 iPhone 15", "iPhone 15", "telefony/mobilnye_telefony/apple", 40000),
    ("📱 iPhone 14", "iPhone 14", "telefony/mobilnye_telefony/apple", 30000),
    ("🎮 PlayStation 5", "PlayStation 5", "igry_pristavki_i_programmy/igrovye_pristavki", 25000),
    ("💻 MacBook Air", "MacBook Air", "noutbuki/apple", 30000),
    ("🎮 Xbox Series X", "Xbox Series X", "igry_pristavki_i_programmy/igrovye_pristavki", 25000),
    ("📺 Телевизор 55", "Телевизор 55", "audio_i_video/televizory_i_proektory", 15000),
    ("💻 RTX 4070", "RTX 4070", "tovary_dlya_kompyutera/komplektuyuschie/videokarty", 35000),
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
        self.setup_menu_button()

    def setup_menu_button(self) -> None:
        """Configure Telegram bottom-left Menu Button to open Mini App on iOS & Android."""
        miniapp_url = os.environ.get("MINI_APP_URL", "https://steelsv.github.io/avito-radar/")
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
        miniapp_url = os.environ.get("MINI_APP_URL", "https://avito-radar.onrender.com/")
        kb = {
            "inline_keyboard": [
                [
                    {
                        "text": "Открыть в терминале",
                        "web_app": {"url": miniapp_url},
                        "icon_custom_emoji_id": TG_EMOJI_LIGHTNING,
                    },
                    {
                        "text": "На Авито",
                        "url": item.url,
                        "icon_custom_emoji_id": TG_EMOJI_LINK,
                    },
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

    def main_menu_keyboard(self) -> dict[str, Any]:
        miniapp_url = os.environ.get("MINI_APP_URL", "https://avito-radar.onrender.com/")
        return {
            "inline_keyboard": [
                [
                    {
                        "text": "ОТКРЫТЬ ТЕРМИНАЛ (MINI APP)",
                        "web_app": {"url": miniapp_url},
                        "icon_custom_emoji_id": TG_EMOJI_LIGHTNING,
                    },
                ],
            ]
        }

    def send_main_menu(self, chat_id: int, message_id: int | None = None) -> None:
        session = self.get_session(chat_id)
        session.state = "IDLE"
        watch_status = f"{tg_e(TG_EMOJI_CHECK, '✅')} ВКЛ (24/7)" if self.monitoring_active else f"{tg_e(TG_EMOJI_WARN, '❗️')} ВЫКЛ"
        searches = list_searches()
        text = (
            f"{tg_e(TG_EMOJI_RADAR, '👁')} <b>СМОТРЯЩИЙ ЗА АВИТО // RADAR TERMINAL</b>\n\n"
            f"{tg_e(TG_EMOJI_LIGHTNING, '⚡')} <b>Все управление перенесено в Mini App:</b>\n"
            f"• {tg_e(TG_EMOJI_SEARCH, '🔎')} Создание любого нового поиска и запуск радара\n"
            f"• {tg_e(TG_EMOJI_TRASH, '🗑')} Удаление существующих поисков в 1 клик\n"
            f"• {tg_e(TG_EMOJI_SHIELD, '🛡')} Карточки с фильтрацией дефектов и байт-цен\n"
            f"• {tg_e(TG_EMOJI_GROWTH, '📈')} Встроенная таблица (полная замена Excel)\n\n"
            f"{tg_e(TG_EMOJI_RADAR, '👁')} Статус мониторинга: <b>{watch_status}</b>\n"
            f"{tg_e(TG_EMOJI_SEARCH, '🔎')} Активных радаров: <b>{len(searches)}</b>\n\n"
            f"<i>В этот чат приходят только карточки новых выгодных объявлений.</i>\n\n"
            f"Нажмите кнопку ниже для перехода в терминал 👇"
        )
        self.render_menu(chat_id, text, self.main_menu_keyboard(), message_id=message_id)

    def send_add_menu(self, chat_id: int, message_id: int | None = None) -> None:
        text = "<b>Как вы хотите настроить поиск?</b>"
        kb = {
            "inline_keyboard": [
                [{"text": "🔍 Выбрать товар и город", "callback_data": "add_wizard_product"}],
                [{"text": "🔗 Вставить ссылку с Авито", "callback_data": "add_by_url"}],
                [{"text": "🔙 В главное меню", "callback_data": "menu_main"}],
            ]
        }
        self.render_menu(chat_id, text, kb, message_id=message_id)

    def send_product_selection(self, chat_id: int, message_id: int | None = None) -> None:
        text = "📱 <b>Шаг 1 из 2. Что ищем?</b>\nВыберите товар из каталога (с авто-категорией и мин. ценой) или введите своё:"
        buttons = []
        row = []
        for idx, (label, *_) in enumerate(POPULAR_PRODUCTS):
            row.append({"text": label, "callback_data": f"pick_prod_{idx}"})
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([{"text": "✏️ Ввести другое название", "callback_data": "pick_prod_custom"}])
        buttons.append([{"text": "🔙 Назад", "callback_data": "menu_add"}])

        kb = {"inline_keyboard": buttons}
        self.render_menu(chat_id, text, kb, message_id=message_id)

    def send_city_selection(self, chat_id: int, message_id: int | None = None) -> None:
        session = self.get_session(chat_id)
        text = f"📍 <b>Шаг 2 из 2. В каком городе искать?</b>\nТовар: <b>{html.escape(session.temp_query)}</b>\n\nВыберите город:"
        buttons = []
        row = []
        for label, slug in POPULAR_CITIES:
            row.append({"text": label, "callback_data": f"pick_city_{slug}_{label}"})
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([{"text": "✏️ Ввести другой город", "callback_data": "pick_city_custom"}])
        buttons.append([{"text": "🔙 Назад к товарам", "callback_data": "add_wizard_product"}])

        kb = {"inline_keyboard": buttons}
        self.render_menu(chat_id, text, kb, message_id=message_id)

    def send_searches_list(self, chat_id: int, message_id: int | None = None) -> None:
        searches = list_searches()
        if not searches:
            text = "📋 <b>У вас пока нет сохранённых поисков.</b>\nНажмите «➕ Добавить поиск», чтобы создать первый!"
            kb = {
                "inline_keyboard": [
                    [{"text": "➕ Добавить поиск", "callback_data": "menu_add"}],
                    [{"text": "🔙 В главное меню", "callback_data": "menu_main"}],
                ]
            }
            self.render_menu(chat_id, text, kb, message_id=message_id)
            return

        text = "📋 <b>Ваши активные поиски:</b>\n\n"
        buttons = []
        for idx, s in enumerate(searches, start=1):
            listings = load_listings(s)
            pmin_info = f" · 💰 от {s.min_price:,} ₽" if s.min_price else " · 💰 Мин. цена не задана"
            text += f"<b>{idx}. {html.escape(s.title)}</b>\n"
            text += f"   📍 Город: {html.escape(s.city)} · В базе: {len(listings)} шт.{pmin_info}\n"
            text += f"   🔑 Имя: <code>{s.name}</code>\n\n"
            buttons.append([
                {"text": f"📊 Excel", "callback_data": f"action_scan_{s.name}"},
                {"text": f"💰 Мин. цена ({s.min_price or 'нет'})", "callback_data": f"set_pmin_{s.name}"},
                {"text": f"❌", "callback_data": f"action_del_{s.name}"},
            ])

        buttons.append([{"text": "➕ Добавить ещё поиск", "callback_data": "menu_add"}])
        buttons.append([{"text": "🔙 В главное меню", "callback_data": "menu_main"}])

        kb = {"inline_keyboard": buttons}
        self.render_menu(chat_id, text, kb, message_id=message_id)

    def send_settings_menu(self, chat_id: int, message_id: int | None = None) -> None:
        self.settings = load_settings()
        priv_text = "Только частники: ✅ Да" if self.settings.alert_private_only else "Только частники: ❌ Все"
        junk_text = "Фильтр мусора и цен: ✅ ВКЛ" if self.settings.alert_filter_junk else "Фильтр мусора и цен: ❌ ВЫКЛ"
        text = (
            "⚙️ <b>Настройки «Смотрящего за Авито»</b>\n\n"
            f"• Интервал проверки: <b>{self.settings.watch_interval:.0f} сек</b>\n"
            f"• Фильтр продавцов: <b>{'Только частные лица' if self.settings.alert_private_only else 'Все (включая магазины)'}</b>\n"
            f"• Фильтр мусора/запчастей/байт-цен: <b>{'Включён ✅' if self.settings.alert_filter_junk else 'Выключен ❌'}</b>\n"
            f"• Отсекать старые переопубликованные: <b>{'Да' if self.settings.alert_no_republished else 'Нет'}</b>"
        )
        kb = {
            "inline_keyboard": [
                [{"text": priv_text, "callback_data": "set_toggle_private"}],
                [{"text": junk_text, "callback_data": "set_toggle_junk"}],
                [
                    {"text": "⏱ 1 мин", "callback_data": "set_interval_60"},
                    {"text": "⏱ 2 мин", "callback_data": "set_interval_120"},
                    {"text": "⏱ 5 мин", "callback_data": "set_interval_300"},
                ],
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

            rec = create_search_from_url(client, url, custom_name=resolved_name)
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

        self.send_main_menu(chat_id)

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
                c_name = re.sub(r"[^a-z0-9_-]+", "_", f"{clean_q}_{slug}").strip("_")
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
            delete_search(search_name)
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

        elif data == "set_toggle_junk":
            self.settings.alert_filter_junk = not self.settings.alert_filter_junk
            save_settings(self.settings)
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

                            # Filter junk, parts and clickbait prices if enabled
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
                            self.send_photo_alert(int(self.config.chat_id), parsed, s.title)

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


def generate_api_bundle() -> dict[str, Any]:
    """Compile cached search listings and market analysis for Mini App."""
    bundle: dict[str, Any] = {}
    for s in list_searches():
        raws = load_listings(s)
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


def start_healthcheck_server() -> None:
    port = int(os.environ.get("PORT", "7860"))

    class MiniAppServerHandler(http.server.BaseHTTPRequestHandler):
        def do_OPTIONS(self) -> None:
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.end_headers()

        def do_DELETE(self) -> None:
            path = self.path.split("?")[0]
            if path.startswith("/api/searches/"):
                search_id = path.replace("/api/searches/", "").strip()
                success = False
                if search_id:
                    success = delete_search(search_id)
                    logger.info("Search '%s' deleted via DELETE method (success=%s)", search_id, success)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "id": search_id, "deleted": success}).encode("utf-8"))
                return
            self.send_response(404)
            self.end_headers()

        def do_GET(self) -> None:
            path = self.path.split("?")[0]
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
                    bundle_data = generate_api_bundle()
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

            if path == "/api/searches":
                try:
                    searches = [
                        {
                            "id": s.name,
                            "query": s.title,
                            "city": s.city,
                            "minPrice": s.min_price or 0,
                            "isActive": True
                        }
                        for s in list_searches()
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
                    bundle = generate_api_bundle()
                    all_lots = []
                    for s_id, s_data in bundle.items():
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
            path = self.path.split("?")[0]
            if path in ("/api/searches", "/api/searches/create"):
                try:
                    content_length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(content_length).decode("utf-8")
                    req_data = json.loads(body)
                    query = req_data.get("query", "").strip()
                    city = req_data.get("city", "chelyabinsk").strip()
                    min_price = int(req_data.get("min_price") or 0)
                    c_name = ""
                    s_rec = None
                    if query:
                        city_slug = transliterate(city).replace(" ", "_").lower()
                        clean_q = transliterate(query).replace(" ", "_").lower()
                        c_name = re.sub(r"[^a-z0-9_-]+", "_", f"{clean_q}_{city_slug}").strip("_")
                        encoded_q = urllib.parse.quote(query)
                        target_url = f"https://www.avito.ru/{city_slug}?q={encoded_q}"
                        if min_price > 0:
                            target_url += f"&pmin={min_price}"

                        cache = load_locations_cache()
                        city_entry = (cache.get("cities") or {}).get(city_slug)
                        loc_id = str(city_entry["id"]) if city_entry else "661420"
                        city_display = city_entry.get("name", city) if city_entry else city

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
                            )
                            save_search(s_rec)
                            logger.info("Search '%s' successfully created via API", c_name)

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
                    content_length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(content_length).decode("utf-8")
                    req_data = json.loads(body)
                    name = req_data.get("name", "").strip()
                    success = False
                    if name:
                        success = delete_search(name)
                        logger.info("Search '%s' deleted via API (success=%s)", name, success)
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
                    content_length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(content_length).decode("utf-8")
                    req_data = json.loads(body)
                    name = req_data.get("name", "").strip()
                    count = 0
                    if name:
                        s_rec = load_search(name)
                        if s_rec:
                            cl = AvitoClient()
                            count = scan_search(s_rec, client=cl, max_pages=1)
                    bundle_data = generate_api_bundle()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True, "count": count, "bundle": bundle_data}).encode("utf-8"))
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
