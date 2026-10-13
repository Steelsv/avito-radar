import pytest
from avito_radar.parsers.item_parser import ParsedItem
from avito_radar.analysis.market import calculate_group_stats, annotate_market_prices
from avito_radar.analysis.classifier import classify_item, extract_goods_group


def test_calculate_group_stats():
    prices = [50000, 52000, 48000, 51000, 10000, 200000]  # outliers: 10000 and 200000
    stats = calculate_group_stats(prices)
    assert stats is not None
    assert 48000 <= stats.median_price <= 52000
    assert stats.count >= 4


def test_annotate_market_prices():
    def make_item(pid: int, price: int):
        return ParsedItem(
            id=pid,
            title="iPhone 15, 128 ГБ",
            price=price,
            price_formatted=f"{price} ₽",
            url=f"https://www.avito.ru/{pid}",
            address="Москва",
            metro="Арбат",
            city="moskva",
            published_text="сегодня",
            sort_timestamp=None,
            seller_name="Иван",
            seller_type="частное лицо",
            seller_rating=5.0,
            closed_listings=3,
            badges=(),
            images=[],
            description="Отличное состояние",
            phone_available=True,
        )

    items = [
        make_item(1, 60000),
        make_item(2, 62000),
        make_item(3, 59000),
        make_item(4, 45000),  # Underpriced deal!
    ]

    annotate_market_prices(items)
    deal_item = next(it for it in items if it.id == 4)
    assert deal_item.market_diff_percent is not None
    assert deal_item.market_diff_percent < -15
    assert any("Выгодно" in t for t in deal_item.tags)


def test_classify_item_agency():
    item = ParsedItem(
        id=10,
        title="2-к. квартира, 60 м²",
        price=10000000,
        price_formatted="10 000 000 ₽",
        url="https://www.avito.ru/10",
        address="СПб",
        metro="Невский",
        city="spb",
        published_text="сегодня",
        sort_timestamp=None,
        seller_name="Агентство недвижимости",
        seller_type="Агентство недвижимости",
        seller_rating=4.8,
        closed_listings=150,
        badges=(),
        images=[],
        description="Эксклюзивный договор. Наше агентство поможет с ипотекой.",
        phone_available=True,
    )
    classify_item(item, category_type="realty")
    assert any("Агентство" in t for t in item.tags)


def test_classify_item_owner():
    item = ParsedItem(
        id=11,
        title="2-к. квартира, 60 м²",
        price=9500000,
        price_formatted="9 500 000 ₽",
        url="https://www.avito.ru/11",
        address="СПб",
        metro="Невский",
        city="spb",
        published_text="сегодня",
        sort_timestamp=None,
        seller_name="Алексей",
        seller_type="частное лицо",
        seller_rating=5.0,
        closed_listings=1,
        badges=(),
        images=[],
        description="Я единственный собственник. Продаю свою квартиру без посредников. Агентам не беспокоить!",
        phone_available=True,
    )
    classify_item(item, category_type="realty")
    assert any("Собственник" in t for t in item.tags)
    assert any("Без агентов" in t for t in item.tags)
