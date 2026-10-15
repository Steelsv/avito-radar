import pytest
from avito_radar.storage.db import load_locations_cache, DEFAULT_CITIES
from avito_radar.telegram_bot import get_query_suggestions, POPULAR_PRODUCTS


def test_location_cache_has_rossiya_aliases():
    cache = load_locations_cache()
    cities = cache.get("cities") or {}
    assert "rossiya" in cities
    assert cities["rossiya"]["id"] == 621540
    assert "vsya_rossiya" in cities
    assert cities["vsya_rossiya"]["id"] == 621540


def test_telegram_bot_suggestions_include_ddr5():
    res = get_query_suggestions("ddr5")
    assert len(res) > 0
    assert any("ddr5" in item["title"].lower() for item in res)

    res_ru = get_query_suggestions("ддр5")
    assert len(res_ru) > 0
    assert any("ddr5" in item["title"].lower() for item in res_ru)


def test_popular_products_has_ddr5_and_pc_parts():
    has_ddr5 = any("ddr5" in q.lower() for _, q, *_ in POPULAR_PRODUCTS)
    has_rtx = any("rtx" in q.lower() for _, q, *_ in POPULAR_PRODUCTS)
    has_matiz = any("matiz" in q.lower() for _, q, *_ in POPULAR_PRODUCTS)
    assert has_ddr5
    assert has_rtx
    assert has_matiz


def test_telegram_bot_suggestions_include_matiz():
    res = get_query_suggestions("matiz")
    assert len(res) > 0
    assert any("matiz" in item["title"].lower() for item in res)
    assert any("мкпп" in item["title"].lower() or "автомат" in item["title"].lower() for item in res)

    res_ru = get_query_suggestions("матиз")
    assert len(res_ru) > 0
    assert any("matiz" in item["title"].lower() or "матиз" in item["title"].lower() for item in res_ru)

