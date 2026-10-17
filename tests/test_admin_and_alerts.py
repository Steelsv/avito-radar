import os
from datetime import datetime, timedelta

import pytest

from avito_radar.notifications.telegram import TelegramConfig
from avito_radar.parsers.item_parser import ParsedItem
from avito_radar.storage import price_history
from avito_radar.storage import users as users_store
from avito_radar.telegram_bot import AvitoTelegramBot, _build_alert_caption


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setattr(price_history, "PRICE_HISTORY_PATH", tmp_path / "price_history.json")
    monkeypatch.setattr(users_store, "USERS_PATH", tmp_path / "users.json")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "111000")
    yield tmp_path


def make_item(title="iPhone 15 Pro 256GB", price=65000, **extra):
    item = ParsedItem(
        id=42,
        title=title,
        price=price,
        price_formatted=f"{price:,} ₽".replace(",", " "),
        url="https://www.avito.ru/item_42",
        address="ул. Ленина, 50",
        metro="",
        city="Челябинск",
        published_text="сегодня",
        sort_timestamp=None,
        seller_name="Иван",
        seller_type="частное лицо",
        seller_rating=4.9,
        closed_listings=12,
        badges=(),
        images=["https://image.url/1.jpg"],
        description="",
        phone_available=True,
    )
    item.deal_badge = extra.get("deal_badge")
    item.recommended_buy = extra.get("recommended_buy")
    item.profit_abs = extra.get("profit_abs")
    item.profit_pct = extra.get("profit_pct")
    item.market_median = extra.get("market_median")
    item.market_samples = extra.get("market_samples")
    item.market_min_price = extra.get("market_min_price")
    item.geo_lat = extra.get("geo_lat")
    item.geo_lon = extra.get("geo_lon")
    return item


def make_user():
    return {
        "user_id": "111000",
        "home_lat": 55.16,
        "home_lon": 61.40,
    }


class TestForeverPro:
    def test_grant_pro_forever(self):
        users_store.grant_pro_forever("222")
        u = users_store.get_user("222")
        assert u["plan"] == "pro"
        assert u["pro_expires_at"] == "forever"
        assert users_store.is_pro("222")

    def test_forever_survives_no_expiry_check(self):
        users_store.grant_pro_forever("222")
        users_store.get_user("222")  # triggers expiry check path
        assert users_store.is_pro("222")
        assert users_store.get_user("222")["plan"] == "pro"

    def test_revoke_pro(self):
        users_store.grant_pro("222", 30)
        assert users_store.is_pro("222")
        users_store.revoke_pro("222")
        u = users_store.get_user("222")
        assert u["plan"] == "free"
        assert u["pro_expires_at"] is None
        assert not users_store.is_pro("222")


class TestAlertCaption:
    def test_full_caption_contains_all_blocks(self):
        item = make_item(
            deal_badge="Ниже рынка на 19%",
            recommended_buy=58000,
            profit_abs=12500,
            profit_pct=19,
            market_median=77500,
            market_samples=7,
            market_min_price=70000,
            geo_lat=55.15,
            geo_lon=61.37,
        )
        caption = _build_alert_caption(make_user(), item, "iPhone 15")
        assert "Выгодная находка" in caption
        assert "iPhone 15 Pro 256GB" in caption
        assert "+12 500 ₽" in caption
        assert "км" in caption
        assert "Челябинск" in caption
        assert "⭐" in caption
        assert "Аналогов на рынке: 7" in caption
        assert "от 70 000 ₽" in caption
        assert "Выкуп: 58 000 ₽" in caption
        assert "возможен торг" in caption
        assert len(caption) <= 1024

    def test_caption_without_optional_fields(self):
        item = make_item()
        caption = _build_alert_caption(None, item, "iPhone 15")
        assert "Новый лот по радару" in caption
        assert "iPhone 15" in caption
        assert "Аналогов" not in caption
        assert "Снижение" not in caption
        assert len(caption) <= 1024

    def test_caption_fits_limit_with_long_title(self):
        item = make_item(
            title="У" * 500,
            deal_badge="Ниже рынка на 19%",
            recommended_buy=58000,
        )
        caption = _build_alert_caption(make_user(), item, "Очень длинное название радара")
        assert len(caption) <= 1024

    def test_caption_includes_price_drop(self):
        item = make_item(price=60000)
        two_days_ago = datetime.now() - timedelta(days=2)
        price_history.record_price(42, 63000, ts=two_days_ago.isoformat())
        caption = _build_alert_caption(make_user(), item, "iPhone 15")
        assert "Снижение цены: 3 000 ₽" in caption
        assert len(caption) <= 1024


def make_bot():
    cfg = TelegramConfig(token="12345:TEST_TOKEN", chat_id="111000")
    return AvitoTelegramBot(cfg)


class TestAdminCommands:
    def _msg(self, text, chat_id=111000):
        return {"chat": {"id": chat_id}, "message_id": 5, "text": text}

    def test_grant_days(self):
        bot = make_bot()
        sent = []
        bot.send_message = lambda chat_id, text, reply_markup=None: sent.append(text) or 1
        bot.delete_message = lambda *a, **k: None
        bot.handle_text_message(self._msg("/grant 222 7"))
        assert users_store.is_pro("222")
        assert any("7 дн." in t for t in sent)

    def test_grant_forever(self):
        bot = make_bot()
        sent = []
        bot.send_message = lambda chat_id, text, reply_markup=None: sent.append(text) or 1
        bot.delete_message = lambda *a, **k: None
        bot.handle_text_message(self._msg("/grant 222 forever"))
        assert users_store.get_user("222")["pro_expires_at"] == "forever"
        assert any("навсегда" in t for t in sent)

    def test_grant_default_30_days(self):
        bot = make_bot()
        sent = []
        bot.send_message = lambda chat_id, text, reply_markup=None: sent.append(text) or 1
        bot.delete_message = lambda *a, **k: None
        bot.handle_text_message(self._msg("/grant 222"))
        assert users_store.is_pro("222")
        assert any("30 дн." in t for t in sent)

    def test_grant_invalid(self):
        bot = make_bot()
        sent = []
        bot.send_message = lambda chat_id, text, reply_markup=None: sent.append(text) or 1
        bot.delete_message = lambda *a, **k: None
        bot.handle_text_message(self._msg("/grant 222 abc"))
        assert any("Неверный срок" in t for t in sent)
        assert not users_store.is_pro("222")

    def test_revoke(self):
        users_store.grant_pro("222", 30)
        bot = make_bot()
        sent = []
        bot.send_message = lambda chat_id, text, reply_markup=None: sent.append(text) or 1
        bot.delete_message = lambda *a, **k: None
        bot.handle_text_message(self._msg("/revoke 222"))
        assert not users_store.is_pro("222")
        assert any("снят" in t for t in sent)

    def test_users_stats(self):
        users_store.grant_pro("222", 30)
        users_store.get_user("333")
        bot = make_bot()
        sent = []
        bot.send_message = lambda chat_id, text, reply_markup=None: sent.append(text) or 1
        bot.delete_message = lambda *a, **k: None
        bot.handle_text_message(self._msg("/users"))
        assert any("PRO: <b>1</b>" in t for t in sent)
        assert any("Free: <b>1</b>" in t for t in sent)

    def test_non_owner_ignored(self):
        bot = make_bot()
        sent = []
        bot.send_message = lambda chat_id, text, reply_markup=None: sent.append(text) or 1
        bot.delete_message = lambda *a, **k: None
        bot.handle_text_message(self._msg("/grant 222 30", chat_id=999))
        assert sent == []
        assert not users_store.is_pro("222")
