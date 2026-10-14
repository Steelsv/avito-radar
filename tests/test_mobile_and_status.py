import json
from pathlib import Path
from avito_radar.notifications.telegram import TelegramConfig
from avito_radar.parsers.item_parser import ParsedItem
from avito_radar.telegram_bot import AvitoTelegramBot


def test_telegram_bot_status_and_alerts(tmp_path, monkeypatch):
    cfg = TelegramConfig(token="12345:TEST_TOKEN", chat_id="123456")
    bot = AvitoTelegramBot(cfg)

    # Verify start_time initialized
    assert hasattr(bot, "start_time")
    assert bot.start_time > 0

    # Verify photo alert buttons include direct Avito URL and Vanish
    item = ParsedItem(
        id=999,
        title="DDR5 32GB Kingston",
        price=8500,
        price_formatted="8 500 ₽",
        url="https://www.avito.ru/item_999",
        address="ул. Ленина",
        metro="",
        city="Челябинск",
        published_text="сегодня",
        sort_timestamp=None,
        seller_name="Иван",
        seller_type="private",
        seller_rating=5.0,
        closed_listings=10,
        badges=(),
        images=["https://image.url/1.jpg"],
        description="Новая память DDR5",
        phone_available=True,
    )

    sent_payloads = []
    def mock_call_api(method, data=None, files=None):
        sent_payloads.append((method, data))
        return {"ok": True, "result": {"message_id": 101}}

    bot.call_api = mock_call_api

    bot.send_photo_alert(123456, item, "DDR5")
    assert len(sent_payloads) > 0
    method, payload = sent_payloads[0]
    kb = payload.get("reply_markup", {}).get("inline_keyboard", [])

    flat_buttons = [btn for row in kb for btn in row]
    has_avito = any(btn.get("url") == item.url for btn in flat_buttons)
    has_vanish = any(btn.get("callback_data") == f"vanish_{item.id}" for btn in flat_buttons)
    has_miniapp = any("web_app" in btn for btn in flat_buttons)

    assert has_avito, "Photo alert must contain direct Avito link"
    assert has_vanish, "Photo alert must contain Vanish inline button"
    assert has_miniapp, "Photo alert must contain Terminal WebApp button"


def test_telegram_bot_vanish_callback(tmp_path, monkeypatch):
    cfg = TelegramConfig(token="12345:TEST_TOKEN", chat_id="123456")
    bot = AvitoTelegramBot(cfg)

    calls = []
    bot.call_api = lambda method, data=None, files=None: calls.append((method, data)) or {"ok": True}
    bot.answer_callback = lambda cb_id, text="": calls.append(("answerCallback", cb_id, text))

    query = {
        "id": "cb_001",
        "data": "vanish_test_lot_777",
        "message": {
            "message_id": 42,
            "chat": {"id": 123456},
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "👁️ Скрыть лот", "callback_data": "vanish_test_lot_777"}]
                ]
            }
        }
    }

    bot.handle_callback_query(query)

    # Check that answerCallback was called with success text
    has_answer = any(c[0] == "answerCallback" and "скрыт" in c[2] for c in calls)
    assert has_answer, "Callback must be answered with confirmation"


def test_styles_and_scripts_have_swipes_and_skeletons():
    root_dir = Path(__file__).resolve().parent.parent
    css_content = (root_dir / "css" / "styles.css").read_text(encoding="utf-8")
    app_js_content = (root_dir / "js" / "app.js").read_text(encoding="utf-8")

    assert ".skeleton-card" in css_content
    assert "skeletonShimmer" in css_content
    assert ".vanished-swipe" in css_content
    assert ".rotating" in css_content

    assert "attachSwipeToCard" in app_js_content
    assert "renderSkeletonCards" in app_js_content
    assert "selectionChanged" in app_js_content
    assert "vanishLot" in app_js_content


def test_node_services_have_status_and_timeout():
    root_dir = Path(__file__).resolve().parent.parent
    scraper_content = (root_dir / "backend" / "services" / "avito-scraper.js").read_text(encoding="utf-8")
    tg_content = (root_dir / "backend" / "services" / "telegram-bot.js").read_text(encoding="utf-8")

    assert "timeout: 45000" in scraper_content
    assert "runPeriodicWatch" in scraper_content

    assert "/status" in tg_content
    assert "vanish_" in tg_content
    assert "LotModel.dismiss" in tg_content
