import json
import os
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest
import requests

import avito_radar.telegram_bot as bot_module
from avito_radar.core import geocoding
from avito_radar.notifications.telegram import TelegramConfig
from avito_radar.storage import db as storage_db
from avito_radar.storage import price_history
from avito_radar.storage import users as users_store
from avito_radar.storage.db import SearchRecord, cap_seen, is_lot_too_old, load_seen, save_seen
from avito_radar.telegram_bot import AvitoTelegramBot

NOW_MS = int(time.time() * 1000)


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_db, "SEARCHES_DIR", tmp_path / "searches")
    monkeypatch.setattr(storage_db, "SEEDS_PATH", tmp_path / "seeds.json")
    monkeypatch.setattr(price_history, "PRICE_HISTORY_PATH", tmp_path / "price_history.json")
    monkeypatch.setattr(users_store, "USERS_PATH", tmp_path / "users.json")
    yield tmp_path


# --- cap_seen / load_seen ---


def test_cap_seen_keeps_newest_ids():
    seen = {
        "old1": "2026-01-01T00:00:00",
        "old2": "2026-01-02T00:00:00",
        "new1": "2026-06-01T00:00:00",
        "new2": "2026-06-02T00:00:00",
    }
    capped = cap_seen(seen, max_ids=2)
    assert set(capped) == {"new1", "new2"}


def test_cap_seen_empty_ts_counts_as_oldest():
    seen = {"a": "", "b": "2026-01-01T00:00:00"}
    capped = cap_seen(seen, max_ids=1)
    assert "b" in capped and "a" not in capped


def test_load_seen_migrates_legacy_list(tmp_path):
    rec = SearchRecord(name="mig_test", title="x", category_type="goods",
                       catalog_url="https://avito.ru", city="c", params={})
    rec.folder.mkdir(parents=True)
    (rec.folder / "seen.json").write_text(json.dumps(["111", "222"]), encoding="utf-8")
    seen = load_seen(rec)
    assert set(seen) == {"111", "222"}
    assert all(isinstance(v, str) and v for v in seen.values())
    save_seen(rec, seen)
    assert set(load_seen(rec)) == {"111", "222"}


def test_load_seen_bad_json_returns_empty(tmp_path):
    rec = SearchRecord(name="bad_test", title="x", category_type="goods",
                       catalog_url="https://avito.ru", city="c", params={})
    rec.folder.mkdir(parents=True)
    (rec.folder / "seen.json").write_text("not json", encoding="utf-8")
    assert load_seen(rec) == {}


# --- age guard ---


def test_is_lot_too_old_three_days():
    assert is_lot_too_old({"id": 1, "sortTimeStamp": NOW_MS - 3 * 86400 * 1000}) is True


def test_is_lot_too_old_fresh_lot():
    assert is_lot_too_old({"id": 1, "sortTimeStamp": NOW_MS - 3600 * 1000}) is False


def test_is_lot_too_old_no_stamp():
    assert is_lot_too_old({"id": 1}) is False
    assert is_lot_too_old(None) is False


def test_is_lot_too_old_env_override(monkeypatch):
    monkeypatch.setenv("ALERT_MAX_AGE_HOURS", "1")
    raw = {"id": 1, "sortTimeStamp": NOW_MS - 2 * 3600 * 1000}
    assert is_lot_too_old(raw) is True
    monkeypatch.setenv("ALERT_MAX_AGE_HOURS", "0")
    assert is_lot_too_old(raw) is False


# --- monitoring loop: stale lots and seen loss do not re-alert ---


class FakePage:
    def __init__(self, items):
        self.items = items
        self.is_last = True


class FakeClient:
    def __init__(self):
        self.items = []

    def fetch_catalog_page(self, *, catalog_url, params, page_number):
        return FakePage(self.items)


def make_raw(item_id, stamp_ms):
    return {
        "id": item_id,
        "title": f"iPhone 15 Pro 256GB лот {item_id}",
        "priceDetailed": {"value": 65000},
        "urlPath": f"chelyabinsk/telefony/{item_id}",
        "sortTimeStamp": stamp_ms,
    }


@pytest.fixture
def monitoring_bot(monkeypatch):
    cfg = TelegramConfig(token="12345:TEST", chat_id="111000")
    bot = AvitoTelegramBot(cfg)
    bot.fake_client = FakeClient()
    monkeypatch.setattr(bot_module, "AvitoClient", lambda *a, **kw: bot.fake_client)
    monkeypatch.setattr(bot_module, "update_market_db", lambda *a, **kw: None)
    bot.alerts = []
    monkeypatch.setattr(
        bot_module, "queue_pending_alert",
        lambda user_id, item: bot.alerts.append(str(item.get("id") if isinstance(item, dict) else item.id)),
    )
    monkeypatch.setattr(bot_module, "scan_search", lambda *a, **kw: (0, None))
    return bot


def test_monitoring_skips_stale_and_no_realert_after_seen_loss(monitoring_bot, monkeypatch):
    bot = monitoring_bot
    rec = SearchRecord(
        name="seen_loss_test", title="iphone 15", category_type="goods",
        catalog_url="https://www.avito.ru/chelyabinsk?q=iphone+15", city="Челябинск",
        params={"q": "iphone 15"}, user_id="111000", new_only=False,
    )
    storage_db.save_search(rec)
    bot.primed_searches = {rec.name}

    fresh = make_raw(501, NOW_MS - 60 * 1000)
    stale = make_raw(502, NOW_MS - 3 * 86400 * 1000)

    bot.fake_client.items = [fresh, stale]
    state = {"stop": False}
    orig_is_running = bot.is_running

    def run_cycle():
        bot.is_running = True
        state["stop"] = False
        orig_sleep = time.sleep

        def stop_sleep(sec):
            state["stop"] = True
            bot.is_running = False

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(time, "sleep", stop_sleep)
            bot.monitoring_loop()
        bot.is_running = orig_is_running

    run_cycle()
    assert bot.alerts == ["501"]

    # seen.json lost the stale id (cap or rotation) - it must not re-alert
    seen = load_seen(rec)
    del seen["502"]
    save_seen(rec, seen)

    run_cycle()
    assert bot.alerts == ["501"]
    # stale lot still marked as seen, so it never comes back as new
    assert "502" in load_seen(rec)


def test_pending_flush_sends_max_10_per_cycle(monitoring_bot):
    bot = monitoring_bot
    sent = []
    pending = [{"id": str(i), "search_title": "x"} for i in range(50)]

    class FakeDir:
        def exists(self):
            return True

        def glob(self, pattern):
            from pathlib import Path
            return [Path("911.meta.json")]

        def mkdir(self, *a, **kw):
            return None

    bot.send_photo_alert = lambda chat_id, item, title: sent.append(item.id)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(bot_module, "PENDING_ALERTS_DIR", FakeDir())
        mp.setattr(bot_module, "load_pending_alerts", lambda uid: list(pending))
        mp.setattr(bot_module, "read_flush_meta", lambda uid: {"last_flush": 0})
        mp.setattr(bot_module, "write_flush_meta", lambda uid, ts: None)
        mp.setattr(bot_module.users_store, "get_user", lambda uid: None)
        mp.setattr(bot_module.users_store, "is_quiet_now", lambda u: False)

        orig_sleep = time.sleep

        def stop_sleep(sec):
            bot.is_running = False

        mp.setattr(time, "sleep", stop_sleep)
        bot.is_running = True
        bot.pending_alerts_flush_loop()

    assert len(sent) == 10


# --- reverse geocoding (Nominatim mock) ---


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


REVERSE_OK = {
    "lat": "55.160",
    "lon": "61.403",
    "display_name": "улица Ленина, 50, Челябинск, Челябинская область, Россия",
    "address": {"road": "улица Ленина", "house_number": "50", "city": "Челябинск"},
}


def test_reverse_geocode_success(monkeypatch):
    monkeypatch.setattr(geocoding.requests, "get", lambda *a, **kw: FakeResponse(REVERSE_OK))
    res = geocoding.reverse_geocode(55.160, 61.403)
    assert res is not None
    assert res["lat"] == 55.160
    assert res["lon"] == 61.403
    assert res["short"] == "улица Ленина, 50, Челябинск"
    assert res["display_name"].startswith("улица Ленина")


def test_reverse_geocode_empty_result(monkeypatch):
    monkeypatch.setattr(
        geocoding.requests, "get",
        lambda *a, **kw: FakeResponse({"error": "Unable to geocode"}),
    )
    assert geocoding.reverse_geocode(55.0, 61.0) is None


def test_reverse_geocode_timeout(monkeypatch):
    def boom(*a, **kw):
        raise requests.Timeout("timeout")

    monkeypatch.setattr(geocoding.requests, "get", boom)
    assert geocoding.reverse_geocode(55.0, 61.0) is None


def test_reverse_geocode_invalid_coords():
    assert geocoding.reverse_geocode(200.0, 61.0) is None
    assert geocoding.reverse_geocode(55.0, 500.0) is None
    assert geocoding.reverse_geocode("abc", "def") is None


# --- HTTP endpoints ---


@pytest.fixture(scope="module")
def http_server():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    old_port = os.environ.get("PORT")
    os.environ["PORT"] = str(port)
    thread = threading.Thread(target=bot_module.start_healthcheck_server, daemon=True)
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


def _get_json(base, path):
    try:
        with urllib.request.urlopen(base + path, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


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


def test_reverse_endpoint_success(http_server, monkeypatch):
    monkeypatch.setattr(bot_module, "reverse_geocode", lambda lat, lon: {
        "display_name": "улица Ленина, 50, Челябинск",
        "short": "улица Ленина, 50, Челябинск",
        "lat": lat, "lon": lon,
    })
    status, body = _get_json(http_server, "/api/address/reverse?user_id=424242&lat=55.160&lon=61.403")
    assert status == 200
    assert body["short"] == "улица Ленина, 50, Челябинск"
    assert body["lat"] == 55.160


def test_reverse_endpoint_not_found(http_server, monkeypatch):
    monkeypatch.setattr(bot_module, "reverse_geocode", lambda lat, lon: None)
    status, body = _get_json(http_server, "/api/address/reverse?user_id=424242&lat=0.0&lon=0.0")
    assert status == 404
    assert body["status"] == "error"
    assert body["message"] == "Не удалось определить адрес"


def test_reverse_endpoint_invalid_coords(http_server):
    status, _ = _get_json(http_server, "/api/address/reverse?user_id=424242&lat=abc&lon=61")
    assert status == 400
    status, _ = _get_json(http_server, "/api/address/reverse?user_id=424242&lat=200&lon=61")
    assert status == 400


def test_create_search_returns_before_scan(http_server, monkeypatch):
    scan_calls = []
    scan_done = threading.Event()

    def fake_scan(rec, *a, **kw):
        scan_calls.append((threading.get_ident(), rec.name))
        scan_done.set()
        return 0, None

    monkeypatch.setattr(bot_module, "scan_search", fake_scan)
    monkeypatch.setattr(bot_module, "AvitoClient", lambda *a, **kw: None)
    monkeypatch.setattr(bot_module.users_store, "get_limits", lambda uid: {"max_searches": 10})

    status, body = _post_json(http_server, "/api/searches", {
        "user_id": "777001",
        "query": "создание без скана",
        "city": "chelyabinsk",
    })
    assert status == 200
    assert body["status"] == "created"
    assert body["name"]
    # scan runs only in a background thread, never in the request thread
    assert scan_done.wait(5)
    assert scan_calls and scan_calls[0][0] != threading.get_ident()
