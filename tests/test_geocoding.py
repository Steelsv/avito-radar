import json

import pytest

from avito_radar.core import geocoding
from avito_radar.core.geocoding import format_distance, geocode_address, haversine_km, lot_distance_km
from avito_radar.parsers.item_parser import parse_catalog_item
from avito_radar.storage import users as users_store


# --- haversine_km ---


def test_haversine_zero():
    assert haversine_km(55.16, 61.4, 55.16, 61.4) == 0.0


def test_haversine_symmetry():
    assert haversine_km(55.16, 61.4, 55.3, 61.65) == haversine_km(55.3, 61.65, 55.16, 61.4)


def test_haversine_chelyabinsk_center_vs_outskirts():
    # центр Челябинска (пл. Революции) vs северо-запад (Чурилово): ~10-12 км
    d = haversine_km(55.160, 61.403, 55.245, 61.278)
    assert 8.0 <= d <= 15.0


def test_haversine_known_distance():
    # 1 градус широты ~ 111 км
    d = haversine_km(55.0, 61.0, 56.0, 61.0)
    assert 110.0 <= d <= 112.0


# --- format_distance ---


def test_format_distance_under_1km():
    assert format_distance(0.4) == "<1 км от вас"
    assert format_distance(0.0) == "<1 км от вас"
    assert format_distance(0.99) == "<1 км от вас"


def test_format_distance_km():
    assert format_distance(2.34) == "~2.3 км от вас"
    assert format_distance(12.95) == "~13.0 км от вас"
    assert format_distance(1.0) == "~1.0 км от вас"


# --- geocode_address (мок requests.get) ---


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_geocode_address_success(monkeypatch):
    calls = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        calls["params"] = params
        calls["headers"] = headers
        calls["timeout"] = timeout
        return FakeResponse([{"lat": "55.160", "lon": "61.403", "display_name": "Ленина 50, Челябинск"}])

    monkeypatch.setattr(geocoding.requests, "get", fake_get)
    res = geocode_address("Ленина 50", city="Челябинск")
    assert res == {"lat": 55.160, "lon": 61.403, "display_name": "Ленина 50, Челябинск"}
    assert "Челябинск" in calls["params"]["q"]
    assert calls["params"]["format"] == "jsonv2"
    assert calls["params"]["countrycodes"] == "ru"
    assert calls["headers"]["User-Agent"] == "avito-radar/1.0 (steelsv)"
    assert calls["timeout"] == 10


def test_geocode_address_empty_list(monkeypatch):
    monkeypatch.setattr(geocoding.requests, "get", lambda *a, **kw: FakeResponse([]))
    assert geocode_address("несуществующий адрес 999") is None


def test_geocode_address_timeout(monkeypatch):
    def fake_get(*a, **kw):
        raise TimeoutError("timeout")

    monkeypatch.setattr(geocoding.requests, "get", fake_get)
    assert geocode_address("Ленина 50") is None


def test_geocode_address_invalid_json(monkeypatch):
    class BadResponse:
        def raise_for_status(self):
            return None

        def json(self):
            raise ValueError("not json")

    monkeypatch.setattr(geocoding.requests, "get", lambda *a, **kw: BadResponse())
    assert geocode_address("Ленина 50") is None


def test_geocode_address_empty_input():
    assert geocode_address("") is None
    assert geocode_address("   ") is None


# --- parser coords ---


def _raw_item(coords=None, geo=None, location=None):
    raw = {
        "id": 1,
        "title": "iPhone 15, 128 ГБ",
        "priceDetailed": {"value": 54000},
        "urlPath": "chelyabinsk/telefony/iphone_15_123",
        "description": "телефон",
    }
    if coords is not None:
        raw["coords"] = coords
    if geo is not None:
        raw["geo"] = geo
    if location is not None:
        raw["location"] = location
    return raw


def test_parse_catalog_item_coords_from_coords():
    it = parse_catalog_item(_raw_item(coords={"lat": 55.16, "lng": 61.4, "address_user": "Ленина 50"}))
    assert it.geo_lat == 55.16
    assert it.geo_lon == 61.4
    assert it.address == "Ленина 50"


def test_parse_catalog_item_coords_from_geo():
    it = parse_catalog_item(_raw_item(geo={"lat": 55.2, "lng": 61.5}))
    assert it.geo_lat == 55.2
    assert it.geo_lon == 61.5


def test_parse_catalog_item_coords_from_location():
    it = parse_catalog_item(_raw_item(location={"lat": "55.1", "lon": "61.3"}))
    assert it.geo_lat == 55.1
    assert it.geo_lon == 61.3


def test_parse_catalog_item_no_coords():
    it = parse_catalog_item(_raw_item())
    assert it.geo_lat is None
    assert it.geo_lon is None


def test_parse_catalog_item_invalid_coords_ignored():
    it = parse_catalog_item(_raw_item(coords={"lat": 999.0, "lng": 61.4}))
    assert it.geo_lat is None
    assert it.geo_lon is None


# --- lot_distance_km ---


def test_lot_distance_km_requires_home_and_coords():
    home = {"home_lat": 55.16, "home_lon": 61.4}
    assert lot_distance_km(None, 55.2, 61.5) is None
    assert lot_distance_km(home, None, 61.5) is None
    assert lot_distance_km(home, 55.2, None) is None
    assert lot_distance_km({}, 55.2, 61.5) is None
    assert lot_distance_km({"home_lat": "bad", "home_lon": 61.4}, 55.2, 61.5) is None
    d = lot_distance_km(home, 55.245, 61.278)
    assert d is not None and 8.0 <= d <= 15.0


# --- users store: home address ---


@pytest.fixture(autouse=True)
def isolated_users_file(tmp_path, monkeypatch):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(users_store, "USERS_PATH", users_path)
    yield users_path
    users_path.unlink(missing_ok=True)


def test_set_and_clear_home_address():
    uid = "4242"
    user = users_store.set_home_address(uid, "Ленина 50, Челябинск", 55.16, 61.4)
    assert user["home_address"] == "Ленина 50, Челябинск"
    assert user["home_lat"] == 55.16
    assert user["home_lon"] == 61.4

    stored = users_store.get_user(uid)
    assert stored["home_address"] == "Ленина 50, Челябинск"
    assert stored["home_lat"] == 55.16

    profile = users_store.public_profile(uid)
    assert profile["home_address"] == "Ленина 50, Челябинск"

    users_store.clear_home_address(uid)
    cleared = users_store.get_user(uid)
    assert cleared["home_address"] is None
    assert cleared["home_lat"] is None
    assert cleared["home_lon"] is None
    assert users_store.public_profile(uid)["home_address"] is None


def test_old_user_record_without_home_fields(tmp_path):
    # старая запись без geo-полей -> None, ничего не падает
    legacy = {
        "user_id": "1111",
        "plan": "free",
        "pro_expires_at": None,
        "trial_used": False,
        "analysis_used_today": 0,
        "analysis_date": "2026-10-17",
        "referrals": 0,
        "referred_by": None,
        "created_at": "2025-01-01T00:00:00",
        "username": "",
    }
    (tmp_path / "users.json").write_text(json.dumps({"1111": legacy}), encoding="utf-8")
    user = users_store.get_user("1111")
    assert user["home_address"] is None
    assert user["home_lat"] is None
    assert user["home_lon"] is None
