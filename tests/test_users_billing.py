import os
from datetime import datetime, timedelta

import pytest

from avito_radar import billing
from avito_radar.analysis.market import compute_deal_fields, format_money
from avito_radar.storage import users as users_store
from avito_radar.storage.db import DATA_DIR, load_json, save_json


@pytest.fixture(autouse=True)
def isolated_users_file(tmp_path, monkeypatch):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(users_store, "USERS_PATH", users_path)
    # reload-safe: functions reference module attr directly
    yield users_path
    users_path.unlink(missing_ok=True)


def test_get_user_creates_free():
    user = users_store.get_user(12345)
    assert user["plan"] == "free"
    assert user["trial_used"] is False
    assert user["referrals"] == 0


def test_grant_pro_and_expiry():
    uid = "777"
    users_store.grant_pro(uid, 30)
    assert users_store.is_pro(uid) is True
    # force expiry
    user = users_store.get_user(uid)
    user["pro_expires_at"] = (datetime.now() - timedelta(hours=1)).isoformat()
    users_store.save_user(user)
    assert users_store.is_pro(uid) is False
    assert users_store.get_user(uid)["plan"] == "free"


def test_trial_once():
    res = users_store.grant_trial(100)
    assert res["ok"] is True
    assert users_store.is_pro(100) is True
    res2 = users_store.grant_trial(100)
    assert res2["ok"] is False
    assert res2["reason"] == "already_used"
    # trial expires -> free again
    user = users_store.get_user(100)
    user["pro_expires_at"] = (datetime.now() - timedelta(minutes=1)).isoformat()
    users_store.save_user(user)
    assert users_store.is_pro(100) is False


def test_analysis_limit_free_and_pro():
    uid = "200"
    for _ in range(3):
        res = users_store.use_analysis(uid)
        assert res["allowed"] is True
    res = users_store.use_analysis(uid)
    assert res["allowed"] is False
    assert res["limit"] == 3
    # PRO - безлимит
    users_store.grant_pro("201", 5)
    for _ in range(10):
        assert users_store.use_analysis("201")["allowed"] is True


def test_owner_always_pro(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    try:
        assert users_store.is_pro(999) is True
    finally:
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)


def test_referral_grants_days():
    res = users_store.add_referral("300", "301")
    assert res["ok"] is True
    referrer = users_store.get_user("300")
    assert referrer["referrals"] >= 1
    assert users_store.is_pro("300") is True
    assert users_store.get_user("301")["referred_by"] == "300"
    # повторная привязка невозможна
    res2 = users_store.add_referral("300", "301")
    assert res2["ok"] is False
    # самореферал отклоняется
    assert users_store.add_referral("300", "300")["ok"] is False


def test_plans_limits_constants():
    assert users_store.PLANS_LIMITS["free"]["max_searches"] == 1
    assert users_store.PLANS_LIMITS["free"]["analysis_per_day"] == 3
    assert users_store.PLANS_LIMITS["free"]["notify_delay_min"] == 15
    assert users_store.PLANS_LIMITS["pro"]["max_searches"] == 15
    assert users_store.PLANS_LIMITS["pro"]["analysis_per_day"] == -1
    assert users_store.PLANS_LIMITS["pro"]["notify_delay_min"] == 0


def test_billing_plans():
    assert billing.PLANS["pro_month"]["stars"] == 299
    assert billing.PLANS["pro_month"]["days"] == 30
    assert billing.PLANS["pro_year"]["stars"] == 1999
    assert billing.PLANS["pro_year"]["days"] == 365
    assert billing.get_plan("pro_month")["days"] == 30
    assert billing.get_plan("nope") is None


def test_billing_successful_payment_grants_pro(monkeypatch):
    sent = {}

    def fake_post(url, json=None, timeout=None):
        sent["url"] = url
        sent["json"] = json
        class R:
            status_code = 200
            def json(self):
                return {"ok": True}
        return R()

    monkeypatch.setattr("avito_radar.billing.requests.post", fake_post)
    message = {
        "chat": {"id": 42},
        "successful_payment": {"invoice_payload": "pro:pro_month:42:nonce123"},
    }
    billing.handle_successful_payment("TOKEN", message)
    assert users_store.is_pro(42) is True
    assert users_store.get_user(42)["pro_expires_at"] is not None
    assert "sendMessage" in sent["url"]


def test_compute_deal_fields_profit():
    fields = compute_deal_fields(100000, 82000)
    assert fields["market_median"] == 100000
    assert fields["recommended_buy"] == 88000
    assert fields["profit_abs"] == 18000
    assert fields["profit_pct"] == 18.0
    assert fields["deal_badge"] == "Ниже рынка на 18 000 руб. (-18%)"


def test_compute_deal_fields_rounding_and_no_deal():
    fields = compute_deal_fields(100123, 100000)
    assert fields["recommended_buy"] == 88100
    assert fields["deal_badge"] is None
    assert fields["profit_pct"] == 0.1
    # отрицательный профит
    fields2 = compute_deal_fields(50000, 60000)
    assert fields2["profit_abs"] == -10000
    assert fields2["profit_pct"] == -20.0
    assert fields2["deal_badge"] is None


def test_format_money_thousands_separator():
    assert format_money(12500) == "12 500"
    assert format_money(1000000) == "1 000 000"


def test_deal_fields_on_annotated_item():
    from avito_radar.analysis.market import annotate_market_prices
    from avito_radar.parsers.item_parser import ParsedItem

    def make(pid, price):
        return ParsedItem(
            id=pid,
            title="iPhone 15, 128 ГБ",
            price=price,
            price_formatted=f"{price} ₽",
            url=f"https://www.avito.ru/{pid}",
            address="Москва",
            metro="",
            city="moskva",
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

    items = [make(1, 60000), make(2, 62000), make(3, 59000), make(4, 45000)]
    annotate_market_prices(items)
    deal = next(it for it in items if it.id == 4)
    assert deal.market_median == 59500
    assert deal.recommended_buy == 52400
    assert deal.profit_abs == 14500
    assert deal.profit_pct == 24.4
    assert deal.deal_badge == "Ниже рынка на 14 500 руб. (-24.4%)"
    median_item = next(it for it in items if it.id == 1)
    assert median_item.deal_badge is None
    assert median_item.recommended_buy == 52400
