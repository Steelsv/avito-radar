import json
import os
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

from avito_radar import telegram_bot as tb
from avito_radar.analysis import market_db
from avito_radar.analysis.market import is_overpriced
from avito_radar.core import geocoding
from avito_radar.core.geocoding import suggest_addresses
from avito_radar.parsers.item_parser import ParsedItem
from avito_radar.storage import users as users_store
from avito_radar.storage import db as storage_db
from avito_radar.storage.db import SearchRecord, cap_seen, rotate_listings, save_listings


def make_item(pid: int, price: int | None, title: str = "iPhone 15, 128 ГБ") -> ParsedItem:
    return ParsedItem(
        id=pid,
        title=title,
        price=price,
        price_formatted=f"{price} ₽" if price else "",
        url=f"https://www.avito.ru/{pid}",
        address="Челябинск",
        metro="",
        city="chelyabinsk",
        published_text="сегодня",
        sort_timestamp=None,
        seller_name="Иван",
        seller_type="частное лицо",
        seller_rating=5.0,
        closed_listings=3,
        badges=(),
        images=[],
        description="Состояние отличное",
        phone_available=True,
    )


# --- suggest_addresses ---


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_suggest_addresses_success_with_address_fields(monkeypatch):
    payload = [
        {
            "lat": "55.160",
            "lon": "61.403",
            "display_name": "улица Ленина, 50, Челябинск, Челябинская область, РФ",
            "address": {"road": "улица Ленина", "house_number": "50", "city": "Челябинск"},
        },
        {
            "lat": "55.150",
            "lon": "61.410",
            "display_name": "Молодогвардейцев, 60, Челябинск",
            "address": {"road": "Молодогвардейцев", "house_number": "60", "town": "Челябинск"},
        },
    ]

    calls = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        calls["params"] = params
        calls["timeout"] = timeout
        return FakeResponse(payload)

    monkeypatch.setattr(geocoding.requests, "get", fake_get)
    res = suggest_addresses("Ленина 50", city="Челябинск")
    assert len(res) == 2
    assert res[0]["short"] == "улица Ленина, 50, Челябинск"
    assert res[1]["short"] == "Молодогвардейцев, 60, Челябинск"
    assert res[0]["lat"] == 55.160 and res[0]["lon"] == 61.403
    assert calls["params"]["format"] == "jsonv2"
    assert calls["params"]["countrycodes"] == "ru"
    assert calls["params"]["accept-language"] == "ru"
    assert "Челябинск" in calls["params"]["q"]
    assert calls["timeout"] == 10


def test_suggest_addresses_short_from_display_name(monkeypatch):
    payload = [{"lat": "55.1", "lon": "61.4", "display_name": "Ленина, 50, Челябинск, Область, РФ"}]
    monkeypatch.setattr(geocoding.requests, "get", lambda *a, **kw: FakeResponse(payload))
    res = suggest_addresses("Ленина")
    assert res[0]["short"] == "Ленина, 50, Челябинск"


def test_suggest_addresses_empty(monkeypatch):
    monkeypatch.setattr(geocoding.requests, "get", lambda *a, **kw: FakeResponse([]))
    assert suggest_addresses("несуществующий адрес 999") == []


def test_suggest_addresses_timeout(monkeypatch):
    def fake_get(*a, **kw):
        raise TimeoutError("timeout")

    monkeypatch.setattr(geocoding.requests, "get", fake_get)
    assert suggest_addresses("Ленина 50") == []


def test_suggest_cache_skips_short_queries(monkeypatch):
    def boom(*a, **kw):
        raise AssertionError("Nominatim must not be called for short queries")

    monkeypatch.setattr(geocoding.requests, "get", boom)
    assert tb.get_address_suggestions_cached("аб") == []


# --- HTTP endpoints (live healthcheck server) ---


@pytest.fixture(scope="module")
def http_server():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    old_port = os.environ.get("PORT")
    os.environ["PORT"] = str(port)
    thread = threading.Thread(target=tb.start_healthcheck_server, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            with urllib.request.urlopen(base + "/health", timeout=1) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(0.1)
    yield base
    if old_port is None:
        os.environ.pop("PORT", None)
    else:
        os.environ["PORT"] = old_port


def _post_json(base, path, payload):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def _get_json(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def test_address_suggest_endpoint(http_server, monkeypatch):
    monkeypatch.setattr(
        geocoding.requests,
        "get",
        lambda *a, **kw: FakeResponse([{
            "lat": "55.160", "lon": "61.403", "display_name": "улица Ленина, 50, Челябинск",
            "address": {"road": "улица Ленина", "house_number": "50", "city": "Челябинск"},
        }]),
    )
    tb.ADDRESS_SUGGEST_CACHE.clear()
    status, body = _get_json(http_server, "/api/address/suggest?user_id=424242&q=" + urllib.parse.quote("Ленина 50"))
    assert status == 200
    assert body["suggestions"][0]["short"] == "улица Ленина, 50, Челябинск"

    status, body = _get_json(http_server, "/api/address/suggest?user_id=424242&q=" + urllib.parse.quote("аб"))
    assert status == 200
    assert body["suggestions"] == []


def test_post_address_with_coords_no_geocoding(http_server, tmp_path, monkeypatch):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(users_store, "USERS_PATH", users_path)

    def boom(*a, **kw):
        raise AssertionError("geocode_address must not be called when lat/lon given")

    monkeypatch.setattr(tb, "geocode_address", boom)
    status, body = _post_json(http_server, "/api/user/address", {
        "user_id": "424243",
        "lat": 55.160,
        "lon": 61.403,
        "display_name": "улица Ленина, 50, Челябинск",
    })
    assert status == 200
    assert body["ok"] is True
    user = users_store.get_user("424243")
    assert user["home_lat"] == 55.160
    assert user["home_lon"] == 61.403
    assert user["home_address"] == "улица Ленина, 50, Челябинск"


def test_post_address_invalid_coords_400(http_server, tmp_path, monkeypatch):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(users_store, "USERS_PATH", users_path)
    status, body = _post_json(http_server, "/api/user/address", {"user_id": "424244", "lat": 999, "lon": 61})
    assert status == 400
    status, body = _post_json(http_server, "/api/user/address", {"user_id": "424244", "lat": 55, "lon": 200})
    assert status == 400
    status, body = _post_json(http_server, "/api/user/address", {"user_id": "424244", "lat": "abc", "lon": 61})
    assert status == 400


# --- каскадный фолбэк рыночной цены ---


@pytest.fixture
def isolated_market_db(tmp_path, monkeypatch):
    db_path = tmp_path / "market_db.json"
    monkeypatch.setattr(market_db, "MARKET_DB_PATH", db_path)
    return db_path


def test_cascade_local_group_fallback(isolated_market_db):
    from avito_radar.analysis.classifier import extract_broad_group, extract_goods_group
    from avito_radar.analysis.market import annotate_market_prices, collect_price_groups
    from avito_radar.analysis.market_db import apply_market_cascade

    # 3 лота узкого варианта 128GB + 1 лот варианта 256GB (вариантная группа слабая)
    items = [
        make_item(1, 50000, "iPhone 15, 128 ГБ"),
        make_item(2, 52000, "iPhone 15, 128 ГБ"),
        make_item(3, 54000, "iPhone 15, 128 ГБ"),
        make_item(4, 55000, "iPhone 15, 256 ГБ"),
    ]
    annotate_market_prices(items, group_key_fn=lambda x: str(x.variant or extract_goods_group(x.title)))
    target = items[3]
    variant_map = collect_price_groups(items, lambda x: str(x.variant or extract_goods_group(x.title)))
    group_map = collect_price_groups(items, lambda x: extract_broad_group(x.title))
    source = apply_market_cascade(
        target,
        variant_map.get(str(target.variant)),
        group_map.get(extract_broad_group(target.title)),
    )
    assert source == "local_group"
    assert target.market_source == "local_group"
    assert target.market_price is not None and target.market_price > 0


def test_cascade_local_variant_wins(isolated_market_db):
    from avito_radar.analysis.classifier import extract_broad_group, extract_goods_group
    from avito_radar.analysis.market import annotate_market_prices, collect_price_groups
    from avito_radar.analysis.market_db import apply_market_cascade

    items = [make_item(i, 50000 + i * 1000, "iPhone 15, 128 ГБ") for i in range(1, 5)]
    annotate_market_prices(items, group_key_fn=lambda x: str(x.variant or extract_goods_group(x.title)))
    variant_map = collect_price_groups(items, lambda x: str(x.variant or extract_goods_group(x.title)))
    group_map = collect_price_groups(items, lambda x: extract_broad_group(x.title))
    source = apply_market_cascade(
        items[0], variant_map.get(str(items[0].variant)), group_map.get(extract_broad_group(items[0].title))
    )
    assert source == "local_variant"


def test_cascade_full_failure_returns_none(isolated_market_db):
    from avito_radar.analysis.classifier import extract_broad_group
    from avito_radar.analysis.market_db import apply_market_cascade

    item = make_item(10, 30000, "iPhone 15, 512 ГБ")
    source = apply_market_cascade(item, None, None)
    assert source is None
    assert item.market_source is None
    assert item.market_price is None


def test_cascade_global_variant_fallback(isolated_market_db):
    from avito_radar.analysis.classifier import extract_broad_group
    from avito_radar.analysis.market_db import apply_market_cascade
    from avito_radar.storage.db import save_json

    save_json(isolated_market_db, {
        "iPhone 15": {
            "median": 60000, "count": 10, "min": 55000, "max": 65000,
            "updated_at": "2099-01-01T00:00:00",
        },
    })
    item = make_item(11, 30000, "iPhone 15, 512 ГБ")
    source = apply_market_cascade(item, None, None)
    assert source == "global_group"
    assert item.market_price == 60000


# --- фильтр переплаты ---


def test_overpriced_filter_60_pct_skipped():
    item = make_item(20, 160000)
    item.market_price = 100000
    assert is_overpriced(item, 50) is True


def test_overpriced_filter_40_pct_allowed():
    item = make_item(21, 140000)
    item.market_price = 100000
    assert is_overpriced(item, 50) is False


def test_overpriced_filter_unknown_market_allowed():
    item = make_item(22, 160000)
    item.market_price = None
    assert is_overpriced(item, 50) is False


# --- ротация listings и кап seen ---


def test_rotate_listings_keeps_300_newest():
    listings = {str(i): {"id": i, "sortTimeStamp": i * 1000} for i in range(305)}
    rotated = rotate_listings(listings)
    assert len(rotated) == 300
    assert rotated["304"]["sortTimeStamp"] == 304000
    assert "0" not in rotated
    assert "4" not in rotated


def test_save_listings_rotates_to_300(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_db, "SEARCHES_DIR", tmp_path / "searches")
    rec = SearchRecord(
        name="rot_test",
        title="iphone 15",
        category_type="goods",
        catalog_url="https://avito.ru",
        city="chelyabinsk",
        params={},
    )
    listings = {str(i): {"id": i, "title": f"iPhone 15, {i} ГБ", "sortTimeStamp": i * 1000} for i in range(320)}
    save_listings(rec, listings)
    saved = storage_db.load_listings(rec)
    assert len(saved) == 300
    assert max(int(k) for k in saved) == 319
    assert min(int(k) for k in saved) == 20


def test_cap_seen_limits_to_2000():
    seen = {str(i): f"2026-01-01 00:{i // 60:02d}:{i % 60:02d}" for i in range(2500)}
    capped = cap_seen(seen)
    assert len(capped) == 2000
    assert "2499" in capped


def test_search_record_default_drop_overpriced_pct():
    rec = SearchRecord(
        name="pct_test",
        title="x",
        category_type="goods",
        catalog_url="https://avito.ru",
        city="chelyabinsk",
        params={},
    )
    assert rec.drop_overpriced_pct == 50
