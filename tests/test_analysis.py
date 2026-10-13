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


def test_classify_combo_listing_bait_price():
    from avito_radar.analysis.classifier import is_likely_fake_or_junk

    item = ParsedItem(
        id=20,
        title="Видеокарты амд 6700хт 580",
        price=8000,
        price_formatted="8 000 ₽",
        url="https://www.avito.ru/20",
        address="Челябинск",
        metro="",
        city="chelyabinsk",
        published_text="сегодня",
        sort_timestamp=None,
        seller_name="Продавец",
        seller_type="частное лицо",
        seller_rating=5.0,
        closed_listings=29,
        badges=(),
        images=[],
        description=(
            "1. Sapphire Rx6700xt — 32 500 руб. Есть небольшой звук.\n"
            "2. Sapphire RX580 — 8 000 руб. На пломбах.\n"
            "3. Powercolor Rx6700xt — 29 000 руб. На пломбе."
        ),
        phone_available=True,
    )
    classify_item(item, category_type="goods", search_query="rx6700 xt")
    assert item.is_combo_listing is True
    assert item.real_price_in_desc in (29000, 32500)
    assert any("Сборное объявление" in t for t in item.tags)
    assert any("Реальная цена в описании" in t for t in item.tags)
    assert is_likely_fake_or_junk(item) is True


def test_defect_detection_kernel_141():
    item = ParsedItem(
        id=21,
        title="Видеокарта Yeston RX 6700 XT 12gb",
        price=10000,
        price_formatted="10 000 ₽",
        url="https://www.avito.ru/21",
        address="Челябинск",
        metro="",
        city="chelyabinsk",
        published_text="сегодня",
        sort_timestamp=None,
        seller_name="Продавец",
        seller_type="частное лицо",
        seller_rating=5.0,
        closed_listings=11,
        badges=(),
        images=[],
        description="Продаю как условно рабочую. Проблемы с драйверами — кернел 141.",
        phone_available=True,
    )
    classify_item(item, category_type="goods", search_query="rx6700 xt")
    assert any("Дефект" in t for t in item.tags)


def test_market_median_ignores_combo_and_defects():
    def make_card(pid: int, title: str, price: int, desc: str):
        it = ParsedItem(
            id=pid,
            title=title,
            price=price,
            price_formatted=f"{price} ₽",
            url=f"https://www.avito.ru/{pid}",
            address="Челябинск",
            metro="",
            city="chelyabinsk",
            published_text="сегодня",
            sort_timestamp=None,
            seller_name="Продавец",
            seller_type="частное лицо",
            seller_rating=5.0,
            closed_listings=10,
            badges=(),
            images=[],
            description=desc,
            phone_available=True,
        )
        classify_item(it, category_type="goods", search_query="rx6700 xt")
        return it

    cards = [
        make_card(1, "Запчасти для видеокарт бренда MSI", 250, "Оригинальные комплектующие кулеры"),
        make_card(2, "Оперативная память", 600, "Ddr3 2gb, 1600mhz"),
        make_card(3, "Запчасти для видеокарт", 3500, "Система охлаждения для видеокарты"),
        make_card(4, "Видеокарты амд 6700хт 580", 8000, "1. Sapphire Rx6700xt — 32 500 руб.\n2. Sapphire RX580 — 8 000 руб."),
        make_card(5, "Видеокарта Yeston RX 6700 XT 12gb", 10000, "Условно рабочая, кернел 141"),
        make_card(6, "Rx 6700 xt gigabyte eagle 12gb", 25000, "Работает, любые тесты, стоит в ПК"),
        make_card(7, "Sapphire RX 6700 XT 12GB Pulse", 30000, "Отличное состояние, любые тесты"),
        make_card(8, "PowerColor RX 6700 XT 12GB", 31000, "Полный комплект, в идеале"),
    ]

    annotate_market_prices(cards)
    genuine_card = next(c for c in cards if c.id == 6)
    combo_card = next(c for c in cards if c.id == 4)

    # Median must be around ~30000, NOT 9000!
    assert genuine_card.market_price is not None
    assert genuine_card.market_price >= 25000
    # 25000 must NOT be tagged 'Выше рынка'
    assert not any("Выше рынка" in t for t in genuine_card.tags)
    # Combo bait 8000 card must NOT be tagged 'Супер-цена' or 'Выгодно'
    assert not any("Выгодно" in t or "Супер-цена" in t for t in combo_card.tags)

