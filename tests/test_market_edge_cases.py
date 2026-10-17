import pytest

from avito_radar.analysis import market_db
from avito_radar.analysis.market import calculate_group_stats, compute_deal_fields
from avito_radar.parsers.item_parser import ParsedItem


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


# --- calculate_group_stats: граничные случаи ---


def test_stats_too_few_samples():
    assert calculate_group_stats([]) is None
    assert calculate_group_stats([50000]) is None
    assert calculate_group_stats([50000, 52000]) is None


def test_stats_filters_none_and_invalid_prices():
    assert calculate_group_stats([None, 0, -100, "x", 50000, 52000, 48000]) is not None
    stats = calculate_group_stats([None, 0, -100, "x", 50000, 52000, 48000])
    assert stats.median_price == 50000


def test_stats_all_equal_prices():
    stats = calculate_group_stats([30000, 30000, 30000, 30000])
    assert stats is not None
    assert stats.median_price == 30000
    assert stats.min_price == 30000
    assert stats.max_price == 30000
    assert stats.count == 4


def test_stats_extreme_high_outlier_trimmed():
    # один бредовый лот в 20 раз дороже рынка
    stats = calculate_group_stats([50000, 52000, 48000, 1000000])
    assert stats is not None
    assert stats.median_price == 50000
    assert stats.max_price == 52000


def test_stats_extreme_low_outliers_trimmed():
    # дешевые запчасти/аксессуары не должны рушить медиану
    stats = calculate_group_stats([500, 800, 1200, 42000, 55000, 68000, 85000])
    assert stats is not None
    assert stats.median_price >= 55000


def test_stats_low_tail_cut_keeps_min_three():
    # даже если отсечение почти все срезало, остается >= 3 образцов
    stats = calculate_group_stats([300, 400, 500, 40000, 45000, 50000])
    assert stats is not None
    assert stats.count >= 3
    assert stats.median_price >= 40000


def test_stats_mid_price_lower_tail_cut():
    # ветка upper_median >= 5000: отсечение 20% от верхней медианы
    stats = calculate_group_stats([200, 300, 400, 9000, 10000, 11000])
    assert stats is not None
    assert stats.median_price >= 9000


def test_stats_does_not_mutate_input():
    prices = [52000, 50000, 48000, 1000000]
    calculate_group_stats(prices)
    assert prices == [52000, 50000, 48000, 1000000]


def test_stats_float_prices():
    stats = calculate_group_stats([50000.5, 52000.5, 48000.5])
    assert stats is not None
    assert stats.median_price in (50000, 50000.5, 50001)


# --- compute_deal_fields: знаки, деление на ноль, округление ---


def test_deal_fields_zero_median_and_price():
    fields = compute_deal_fields(0, 50000)
    assert fields["profit_abs"] is None
    assert fields["profit_pct"] is None
    assert fields["deal_badge"] is None
    assert fields["recommended_buy"] == 0

    fields2 = compute_deal_fields(50000, 0)
    assert fields2["profit_abs"] is None
    assert fields2["profit_pct"] is None

    fields3 = compute_deal_fields(50000, None)
    assert fields3["profit_abs"] is None


def test_deal_fields_negative_profit():
    fields = compute_deal_fields(50000, 60000)
    assert fields["profit_abs"] == -10000
    assert fields["profit_pct"] == -20.0
    assert fields["deal_badge"] is None


def test_deal_fields_positive_profit_and_badge():
    fields = compute_deal_fields(100000, 80000)
    assert fields["profit_abs"] == 20000
    assert fields["profit_pct"] == 20.0
    assert fields["recommended_buy"] == 88000
    assert fields["deal_badge"] is not None
    assert "20 000" in fields["deal_badge"]


def test_deal_fields_badge_threshold_boundary():
    # ровно на пороге 10% бейдж уже есть
    fields = compute_deal_fields(100000, 90000)
    assert fields["profit_pct"] == 10.0
    assert fields["deal_badge"] is not None
    # чуть ниже порога - бейджа нет
    fields2 = compute_deal_fields(100000, 90100)
    assert fields2["profit_pct"] == 9.9
    assert fields2["deal_badge"] is None


def test_deal_fields_rounding():
    fields = compute_deal_fields(100001, 82500)
    # 100001*0.88/100 = 880.0088 -> round 880 -> 88000
    assert fields["recommended_buy"] == 88000
    # (100001-82500)/100001*100 = 17.4982 -> 17.5
    assert fields["profit_pct"] == 17.5


# --- market_db: глобальная база и market_is_global ---


@pytest.fixture(autouse=True)
def isolated_market_db(tmp_path, monkeypatch):
    db_path = tmp_path / "market_db.json"
    monkeypatch.setattr(market_db, "MARKET_DB_PATH", db_path)
    yield db_path
    db_path.unlink(missing_ok=True)


def _seed_db(db_path, variant: str, median: int, count: int = 10):
    from datetime import datetime
    from avito_radar.storage.db import save_json

    save_json(db_path, {
        variant: {
            "median": median,
            "count": count,
            "min": median - 5000,
            "max": median + 5000,
            "updated_at": datetime.now().isoformat(),
        }
    })


def test_update_market_db_merges_and_returns_records():
    items = [
        make_item(1, 54000, "iPhone 15, 128 ГБ"),
        make_item(2, 56000, "iPhone 15, 256 ГБ"),
        make_item(3, 58000, "iPhone 15, 128 ГБ"),
    ]
    updated = market_db.update_market_db(items, category_type="goods")
    assert updated
    for rec in updated.values():
        assert rec["median"] > 0
        assert rec["count"] >= 1


def test_update_market_db_ignores_non_goods():
    items = [make_item(1, 54000)]
    assert market_db.update_market_db(items, category_type="realty") == {}


def test_get_variant_stats_stale_record_rejected(isolated_market_db):
    from datetime import datetime, timedelta
    from avito_radar.storage.db import save_json

    save_json(isolated_market_db, {
        "iphone 15 128gb": {
            "median": 55000,
            "count": 5,
            "min": 50000,
            "max": 60000,
            "updated_at": (datetime.now() - timedelta(days=31)).isoformat(),
        }
    })
    assert market_db.get_variant_stats("iphone 15 128gb") is None


def test_apply_global_market_sets_flag_and_deal_fields(isolated_market_db):
    variant = "iphone 15 128gb"
    _seed_db(isolated_market_db, variant, median=60000)

    item = make_item(1, 48000)
    item.variant = variant
    item.market_price = None

    applied = market_db.apply_global_market(item)
    assert applied is True
    assert item.market_is_global is True
    assert item.market_price == 60000
    # deal-поля пересчитаны от глобальной медианы
    assert item.market_median == 60000
    assert item.recommended_buy == 52800
    assert item.profit_abs == 12000
    assert item.profit_pct == 20.0
    assert item.deal_badge is not None
    assert any("Выгодно" in t for t in item.tags)


def test_apply_global_market_skipped_when_local_strong(isolated_market_db):
    variant = "iphone 15 128gb"
    _seed_db(isolated_market_db, variant, median=60000)

    item = make_item(1, 55000)
    item.variant = variant
    item.market_price = 55000
    from avito_radar.analysis.market import PriceStats

    local = PriceStats(count=5, median_price=55000, min_price=52000, max_price=58000)
    assert market_db.apply_global_market(item, local_stats=local) is False
    assert item.market_is_global is False
    assert item.market_price == 55000


def test_apply_global_market_defect_no_deal(isolated_market_db):
    variant = "iphone 15 128gb"
    _seed_db(isolated_market_db, variant, median=60000)

    item = make_item(1, 20000)
    item.variant = variant
    item.market_price = None
    item.is_defect = True
    item.defect_type = "icloud"

    assert market_db.apply_global_market(item) is True
    assert item.market_is_global is True
    assert item.market_price == 60000
    assert item.market_diff_percent is None
    assert item.profit_pct is None
    assert item.deal_badge is None


def test_apply_global_market_combo_bait_no_fake_diff(isolated_market_db):
    variant = "rx 6700 xt 12gb"
    _seed_db(isolated_market_db, variant, median=29000)

    item = make_item(1, 8000, "Видеокарты амд 6700хт 580")
    item.variant = variant
    item.market_price = None
    item.is_combo_listing = True
    item.real_price_in_desc = None

    assert market_db.apply_global_market(item) is True
    # байт-цена 8000 не должна дать фейковую выгоду -75%
    assert item.market_diff_percent is None
    assert item.profit_pct is None
    assert item.deal_badge is None


def test_apply_global_market_missing_variant(isolated_market_db):
    item = make_item(1, 48000)
    item.variant = None
    assert market_db.apply_global_market(item) is False
