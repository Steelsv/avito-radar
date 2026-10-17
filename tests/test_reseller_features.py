import json
from datetime import datetime, timedelta

import pytest

from avito_radar.analysis import market as market_mod
from avito_radar.analysis.seller_score import score_seller
from avito_radar.parsers.item_parser import ParsedItem
from avito_radar.storage import db as db_mod
from avito_radar.storage import dedup, price_history
from avito_radar.storage import users as users_store


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setattr(price_history, "PRICE_HISTORY_PATH", tmp_path / "price_history.json")
    monkeypatch.setattr(users_store, "USERS_PATH", tmp_path / "users.json")
    monkeypatch.setattr(db_mod, "SEARCHES_DIR", tmp_path / "searches")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    yield tmp_path


def make_item(pid=1, price=50000, seller_type="частное лицо", rating=5.0, closed=3,
              title="iPhone 15, 128 ГБ", images=None, seller_name="Иван"):
    return ParsedItem(
        id=pid,
        title=title,
        price=price,
        price_formatted=f"{price} ₽",
        url=f"https://www.avito.ru/{pid}",
        address="Москва",
        metro="",
        city="moskva",
        published_text="сегодня",
        sort_timestamp=None,
        seller_name=seller_name,
        seller_type=seller_type,
        seller_rating=rating,
        closed_listings=closed,
        badges=(),
        images=images if images is not None else ["https://img.avito.ru/1.jpg"],
        description="ok",
        phone_available=True,
    )


def make_search(name="s1"):
    return db_mod.SearchRecord(
        name=name,
        title="iPhone 15",
        category_type="goods",
        catalog_url="https://www.avito.ru/moskva",
        city="Москва",
        params={"q": "iphone 15"},
        user_id="42",
    )


# --- 1. price history ---

def test_record_price_and_dedup_unchanged():
    assert price_history.record_price("L1", 50000) is True
    assert price_history.record_price("L1", 50000) is False
    assert len(price_history.get_history("L1")) == 1
    assert price_history.record_price("L1", 47000) is True
    assert len(price_history.get_history("L1")) == 2


def test_record_price_invalid():
    assert price_history.record_price("LX", None) is False
    assert price_history.record_price("LX", 0) is False
    assert price_history.get_history("LX") == []


def test_history_cap_30():
    base = datetime(2026, 1, 1)
    for i in range(35):
        price_history.record_price("LC", 1000 + i, ts=(base + timedelta(hours=i)).isoformat())
    assert len(price_history.get_history("LC")) == 30
    assert price_history.get_history("LC")[0]["price"] == 1005


def test_price_drop_calculation():
    now = datetime(2026, 1, 10, 12, 0)
    old = (now - timedelta(days=2)).isoformat()
    price_history.record_price("LD", 50000, ts=old)
    price_history.record_price("LD", 47000, ts=old)
    drop = price_history.price_drop("LD", 44000, now=now)
    assert drop == {"amount": 6000, "days": 2.0}


def test_price_drop_requires_12h_old_record():
    now = datetime(2026, 1, 10, 12, 0)
    recent = (now - timedelta(hours=2)).isoformat()
    price_history.record_price("LT", 50000, ts=recent)
    assert price_history.price_drop("LT", 40000, now=now) is None


def test_price_drop_no_drop_when_price_not_lower():
    now = datetime(2026, 1, 10, 12, 0)
    old = (now - timedelta(days=1)).isoformat()
    price_history.record_price("LN", 50000, ts=old)
    assert price_history.price_drop("LN", 50000, now=now) is None
    assert price_history.price_drop("LN", 52000, now=now) is None


def test_price_drop_empty_history():
    assert price_history.price_drop("NONE", 1000) is None
    assert price_history.price_drop("NONE", None) is None


# --- 2. seller score ---

def test_seller_score_reseller_by_type():
    assert score_seller(make_item(seller_type="Магазин техники"))["level"] == "reseller"
    assert score_seller(make_item(seller_type="Агентство недвижимости"))["level"] == "reseller"


def test_seller_score_reseller_by_closed_listings():
    score = score_seller(make_item(closed=15, seller_type="частное лицо"))
    assert score == {"level": "reseller", "label": "Перекуп/магазин"}
    assert score_seller(make_item(closed=14))["level"] != "reseller"


def test_seller_score_reliable():
    score = score_seller(make_item(rating=4.5, closed=3))
    assert score == {"level": "reliable", "label": "Надежный продавец"}
    assert score_seller(make_item(rating=4.4, closed=3))["level"] == "regular"
    assert score_seller(make_item(rating=4.9, closed=2))["level"] == "regular"


def test_seller_score_new_account():
    score = score_seller(make_item(rating=None, closed=None))
    assert score == {"level": "new", "label": "Свежий аккаунт - риск"}
    assert score_seller(make_item(rating=0, closed=0))["level"] == "new"


def test_seller_score_regular():
    score = score_seller(make_item(rating=4.0, closed=5))
    assert score == {"level": "regular", "label": "Частный продавец"}


# --- 3. photo repost dedup ---

def test_repost_not_alerted_twice():
    s = make_search()
    first = make_item(pid=100)
    assert dedup.check_and_mark_post(s, first) is False
    same_post_new_id = make_item(pid=200)
    assert dedup.check_and_mark_post(s, same_post_new_id) is True
    assert dedup.is_repost(s, same_post_new_id) is True
    assert dedup.is_repost(s, first) is False


def test_repost_different_photos_alerted():
    s = make_search()
    first = make_item(pid=100, images=["https://img.avito.ru/a.jpg"])
    assert dedup.check_and_mark_post(s, first) is False
    other = make_item(pid=200, images=["https://img.avito.ru/b.jpg"])
    assert dedup.check_and_mark_post(s, other) is False


def test_post_key_normalizes_title_and_seller():
    a = make_item(pid=1, title="iPhone 15  128ГБ", seller_name="Иван")
    b = make_item(pid=2, title="iphone 15 128гб", seller_name=" иван ")
    assert dedup.post_key(a) == dedup.post_key(b)


# --- 5. quiet hours ---

def test_is_quiet_now_overnight_interval():
    user = users_store.get_user("777")
    users_store.set_quiet_hours("777", True, 23, 8)
    user = users_store.get_user("777")
    assert users_store.is_quiet_now(user, now=datetime(2026, 1, 1, 23, 30)) is True
    assert users_store.is_quiet_now(user, now=datetime(2026, 1, 1, 12, 0)) is False
    assert users_store.is_quiet_now(user, now=datetime(2026, 1, 1, 7, 59)) is True
    assert users_store.is_quiet_now(user, now=datetime(2026, 1, 1, 8, 0)) is False


def test_is_quiet_now_disabled_or_day_interval():
    user = users_store.set_quiet_hours("778", False, 23, 8)
    assert users_store.is_quiet_now(user, now=datetime(2026, 1, 1, 2, 0)) is False
    user2 = users_store.set_quiet_hours("779", True, 1, 5)
    assert users_store.is_quiet_now(user2, now=datetime(2026, 1, 1, 3, 0)) is True
    assert users_store.is_quiet_now(user2, now=datetime(2026, 1, 1, 5, 0)) is False
    assert users_store.is_quiet_now(None) is False


def test_set_quiet_hours_validation():
    with pytest.raises(ValueError):
        users_store.set_quiet_hours("780", True, 24, 8)
    with pytest.raises(ValueError):
        users_store.set_quiet_hours("780", True, -1, 8)
    with pytest.raises(ValueError):
        users_store.set_quiet_hours("780", True, 8, 8)
    with pytest.raises(ValueError):
        users_store.set_quiet_hours("780", True, "23", 8)
    user = users_store.set_quiet_hours("780", True, 22, 7)
    assert user["quiet_enabled"] is True
    assert user["quiet_start"] == 22
    assert user["quiet_end"] == 7


def test_default_user_has_quiet_fields():
    user = users_store.get_user("781")
    assert user["quiet_enabled"] is False
    assert user["quiet_start"] == 23
    assert user["quiet_end"] == 8


# --- 4. CSV export ---

@pytest.fixture
def export_env(monkeypatch):
    import avito_radar.telegram_bot as tb
    fake_bundle = {
        "lots": [
            {
                "id": 1, "title": "iPhone 15", "price": 50000,
                "market_median": 60000, "profit_abs": 10000, "profit_pct": 16.7,
                "deal_badge": "Ниже рынка на 10 000 руб. (-16.7%)",
                "city": "Москва", "distance_km": 3.25,
                "publishedText": "сегодня", "url": "https://avito.ru/1",
            },
        ]
    }
    monkeypatch.setattr(tb, "generate_api_bundle", lambda user_id=None: fake_bundle)
    monkeypatch.setattr(users_store, "is_pro", lambda uid: False)
    yield tb
    monkeypatch.setattr(users_store, "is_pro", lambda uid: True)


def test_export_csv_free_403(export_env):
    tb = export_env
    status, body = tb.build_lots_csv("42")
    assert status == 403
    assert json.loads(body.decode("utf-8")) == {"status": "error", "message": "Экспорт доступен в PRO"}


def test_export_csv_pro_200(export_env, monkeypatch):
    tb = export_env
    monkeypatch.setattr(users_store, "is_pro", lambda uid: True)
    status, body = tb.build_lots_csv("42")
    assert status == 200
    text = body.decode("utf-8-sig")
    lines = text.strip().splitlines()
    assert lines[0] == "id;title;price;market_median;profit_abs;profit_pct;deal_badge;city;distance_km;published;url"
    row = lines[1].split(";")
    assert row[0] == "1"
    assert row[1] == "iPhone 15"
    assert row[2] == "50000"
    assert row[8] == "3.2"
    assert row[9] == "сегодня"


# --- 6. market min price ---

def test_market_min_price_annotated():
    items = [make_item(pid=1, price=60000), make_item(pid=2, price=62000),
             make_item(pid=3, price=59000), make_item(pid=4, price=45000)]
    market_mod.annotate_market_prices(items)
    for it in items:
        assert it.market_min_price == 45000
        assert it.market_samples >= 3


def test_market_min_price_cleared_when_no_stats():
    items = [make_item(pid=1, price=60000)]
    market_mod.annotate_market_prices(items)
    assert items[0].market_min_price is None
