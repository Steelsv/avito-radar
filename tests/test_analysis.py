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


def test_gravel_bike_accessories_dont_break_median():
    """Verify that tires, saddles, pedals, handlebars and tubes do NOT ruin bike median price."""
    from avito_radar.analysis.classifier import is_item_accessory, is_likely_fake_or_junk

    def make_lot(pid: int, title: str, price: int, desc: str = ""):
        it = ParsedItem(
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
            seller_name="Продавец",
            seller_type="частное лицо",
            seller_rating=5.0,
            closed_listings=5,
            badges=(),
            images=[],
            description=desc,
            phone_available=True,
        )
        classify_item(it, category_type="goods", search_query="гравел")
        return it

    # Mixed listings returned by Avito for 'гравел':
    # Accessories & parts (1000 - 2500 ₽)
    acc1 = make_lot(101, "Покрышки WTB Riddler 700x37c для гравела", 1200, "Пара покрышек в хорошем состоянии")
    acc2 = make_lot(102, "Сидушка Selle Royal для гравийного велосипеда", 1500, "Комфортное седло")
    acc3 = make_lot(103, "Седло Brooks B17 на гравел", 2500, "Кожаное седло")
    acc4 = make_lot(104, "Педали контактные Shimano SPD для гравела", 1800, "Педали с шипами")
    acc5 = make_lot(105, "Руль баран дропбар для гравела", 2200, "Алюминиевый руль с флейром")
    acc6 = make_lot(106, "Камера велосипедная Continental 700c гравел", 500, "Новая велокамера")

    # Genuine gravel bicycles (42000 - 85000 ₽)
    bike1 = make_lot(201, "Велосипед Outleap Rudeway гравел", 42000, "Гравийный велосипед, трансмиссия Claris, дисковые тормоза")
    bike2 = make_lot(202, "Гравийный велосипед Marin Nicasio", 55000, "Хромоль, отличное состояние")
    bike3 = make_lot(203, "Велосипед Merida Silex 300 гравел", 68000, "Карбоновая вилка, идеальное состояние")
    bike4 = make_lot(204, "Gravel bike Cannondale Topstone", 85000, "Топовый гравел на GRX")

    # 1. Check classification
    accessories = [acc1, acc2, acc3, acc4, acc5, acc6]
    for acc in accessories:
        assert acc.is_accessory is True, f"Expected {acc.title} to be classified as accessory!"
        assert any("Велозапчасть" in t or "Аксессуар" in t for t in acc.tags), f"Missing accessory tag on {acc.title}"
        assert is_likely_fake_or_junk(acc) is True

    bikes = [bike1, bike2, bike3, bike4]
    for b in bikes:
        assert b.is_accessory is False, f"Expected {b.title} to be genuine bike, not accessory!"

    # 2. Run market price analysis
    all_items = accessories + bikes
    annotate_market_prices(all_items)

    # Median MUST reflect genuine bikes (~61,500 ₽), NOT 1,650 ₽!
    for b in bikes:
        assert b.market_price is not None
        assert 50000 <= b.market_price <= 70000, f"Market price {b.market_price} is distorted by accessories!"

    # Outleap at 42,000 ₽ is a great deal (-31.7%), and MUST NOT be labeled 'Выше рынка'
    assert not any("Выше рынка" in t for t in bike1.tags), "Bike must not be tagged 'Выше рынка' due to accessory price collapse!"
    assert any("Выгодно" in t for t in bike1.tags), "Bargain bike should be tagged 'Выгодно'!"

    # Accessories (1,200 ₽) MUST NOT be tagged as -98% bargain deal for a bicycle
    for acc in accessories:
        assert not any("Выгодно" in t or "Супер-цена" in t for t in acc.tags), f"Accessory {acc.title} wrongly tagged as deal!"


def test_context_aware_accessory_query():
    """If user specifically searches for 'седло для велосипеда', saddles are NOT unwanted accessories."""
    item = ParsedItem(
        id=301,
        title="Седло Selle Italia для велосипеда",
        price=3500,
        price_formatted="3 500 ₽",
        url="https://www.avito.ru/301",
        address="Москва",
        metro="",
        city="moskva",
        published_text="сегодня",
        sort_timestamp=None,
        seller_name="Иван",
        seller_type="частное лицо",
        seller_rating=5.0,
        closed_listings=2,
        badges=(),
        images=[],
        description="Отличное седло",
        phone_available=True,
    )
    classify_item(item, category_type="goods", search_query="седло для велосипеда")
    # Because query itself contains 'седло', it's the exact searched item
    assert item.is_accessory is False


def test_iphone_and_car_accessories_detection():
    """Verify phone cases/glass and car floor mats are recognized across non-bike products."""
    case = ParsedItem(
        id=401,
        title="Чехол на iPhone 15 Pro Max с MagSafe",
        price=1200,
        price_formatted="1 200 ₽",
        url="https://www.avito.ru/401",
        address="Москва",
        metro="",
        city="moskva",
        published_text="сегодня",
        sort_timestamp=None,
        seller_name="Магазин",
        seller_type="магазин",
        seller_rating=4.9,
        closed_listings=200,
        badges=(),
        images=[],
        description="Силиконовый чехол",
        phone_available=True,
    )
    classify_item(case, category_type="goods", search_query="iPhone 15 Pro Max")
    assert case.is_accessory is True
    assert any("Аксессуар" in t for t in case.tags)

    mats = ParsedItem(
        id=402,
        title="Коврики Eva в салон Lada Vesta",
        price=2200,
        price_formatted="2 200 ₽",
        url="https://www.avito.ru/402",
        address="Челябинск",
        metro="",
        city="chelyabinsk",
        published_text="сегодня",
        sort_timestamp=None,
        seller_name="Сергей",
        seller_type="частное лицо",
        seller_rating=5.0,
        closed_listings=10,
        badges=(),
        images=[],
        description="Комплект ковриков",
        phone_available=True,
    )
    classify_item(mats, category_type="goods", search_query="Lada Vesta")
    assert mats.is_accessory is True
    assert any("Автоаксессуар" in t for t in mats.tags)


def test_query_intent_parsing():
    """Verify that query intent parsing extracts brand, model, storage, and features."""
    from avito_radar.analysis.classifier import parse_query_intent

    # 1. iPhone generic
    i1 = parse_query_intent("iPhone 15")
    assert i1.brand == "apple_iphone"
    assert i1.model_number == "15"
    assert i1.sub_model == "any"
    assert i1.storage is None

    # 2. Russian syntax "15 айфон"
    i2 = parse_query_intent("15 айфон")
    assert i2.brand == "apple_iphone"
    assert i2.model_number == "15"
    assert i2.sub_model == "any"

    # 3. Exact specification "iphone 15 128 esim"
    i3 = parse_query_intent("iphone 15 128 esim")
    assert i3.brand == "apple_iphone"
    assert i3.model_number == "15"
    assert i3.sub_model == "base"
    assert i3.storage == "128gb"
    assert "esim" in i3.features

    # 4. Pro Max with storage
    i4 = parse_query_intent("айфон 15 про макс 256")
    assert i4.brand == "apple_iphone"
    assert i4.model_number == "15"
    assert i4.sub_model == "pro max"
    assert i4.storage == "256gb"

    # 5. GPU RTX 4070
    g1 = parse_query_intent("RTX 4070")
    assert g1.brand == "rtx"
    assert g1.model_number == "4070"

    # 6. PlayStation 5
    ps = parse_query_intent("PS5")
    assert ps.brand == "playstation"
    assert ps.model_number == "5"


def test_iphone_13_filtered_from_iphone_15_search():
    """User case: iPhone 13 Pro must be flagged as mismatched and NOT distort iPhone 15 market prices."""
    from avito_radar.analysis.classifier import classify_item, is_likely_fake_or_junk
    from avito_radar.analysis.market import annotate_market_prices

    wrong_item = ParsedItem(
        id=501,
        title="iPhone 13 Pro, 128 ГБ, SIM + eSIM",
        price=26990,
        price_formatted="26 990 ₽",
        url="https://www.avito.ru/501",
        address="Челябинск",
        metro="",
        city="chelyabinsk",
        published_text="сегодня",
        sort_timestamp=None,
        seller_name="Магазин",
        seller_type="магазин",
        seller_rating=4.8,
        closed_listings=80,
        badges=(),
        images=[],
        description="Отличный телефон iPhone 13 Pro",
        phone_available=True,
    )

    right_item1 = ParsedItem(
        id=502,
        title="iPhone 15, 128 ГБ, SIM + eSIM",
        price=54000,
        price_formatted="54 000 ₽",
        url="https://www.avito.ru/502",
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
        description="Новый iPhone 15 запечатан",
        phone_available=True,
    )

    right_item2 = ParsedItem(
        id=503,
        title="iPhone 15, 128 ГБ, SIM + eSIM",
        price=58000,
        price_formatted="58 000 ₽",
        url="https://www.avito.ru/503",
        address="Челябинск",
        metro="",
        city="chelyabinsk",
        published_text="сегодня",
        sort_timestamp=None,
        seller_name="Алексей",
        seller_type="частное лицо",
        seller_rating=5.0,
        closed_listings=1,
        badges=(),
        images=[],
        description="iPhone 15 в идеале",
        phone_available=True,
    )

    right_item3 = ParsedItem(
        id=504,
        title="iPhone 15, 128 ГБ, SIM + eSIM",
        price=56000,
        price_formatted="56 000 ₽",
        url="https://www.avito.ru/504",
        address="Челябинск",
        metro="",
        city="chelyabinsk",
        published_text="сегодня",
        sort_timestamp=None,
        seller_name="Дмитрий",
        seller_type="частное лицо",
        seller_rating=5.0,
        closed_listings=2,
        badges=(),
        images=[],
        description="iPhone 15 128gb",
        phone_available=True,
    )

    # Classify all items for query "iPhone 15 eSIM"
    classify_item(wrong_item, category_type="goods", search_query="iPhone 15 eSIM")
    classify_item(right_item1, category_type="goods", search_query="iPhone 15 eSIM")
    classify_item(right_item2, category_type="goods", search_query="iPhone 15 eSIM")
    classify_item(right_item3, category_type="goods", search_query="iPhone 15 eSIM")

    # The iPhone 13 Pro MUST be flagged as mismatched model
    assert wrong_item.is_mismatched_model is True
    assert any("Другая модель" in t for t in wrong_item.tags)
    assert is_likely_fake_or_junk(wrong_item) is True

    # The iPhone 15 items MUST NOT be flagged as mismatched
    assert right_item1.is_mismatched_model is False
    assert right_item2.is_mismatched_model is False
    assert right_item3.is_mismatched_model is False

    # Annotate prices
    items = [wrong_item, right_item1, right_item2, right_item3]
    annotate_market_prices(items)

    # iPhone 15 market price must be ~56 000 ₽ (clean median of 54k, 56k, 58k)
    assert right_item1.market_price == 56000

    # Wrong iPhone 13 must NOT receive iPhone 15's market price or deal tags
    assert wrong_item.market_price is None
    assert wrong_item.market_diff_percent is None
    assert not any("Супер-цена" in t for t in wrong_item.tags)
    assert not any("Выгодно" in t for t in wrong_item.tags)


def test_iphone_15_128_esim_vs_broad_iphone_15():
    """Verify difference between exact query (128 esim) and broad query (all 15 models)."""
    from avito_radar.analysis.classifier import is_item_matching_search

    exact_query = "iphone 15 128 esim"
    broad_query = "iphone 15"

    item_base_128_esim = ("iPhone 15, 128 ГБ, SIM + eSIM", "Новый телефон")
    item_base_256_esim = ("iPhone 15, 256 ГБ, SIM + eSIM", "Новый телефон")
    item_pro_128_esim = ("iPhone 15 Pro, 128 ГБ, SIM + eSIM", "Новый телефон")
    item_base_128_no_esim = ("iPhone 15, 128 ГБ", "Только физическая сим-карта")
    item_old_13_pro = ("iPhone 13 Pro, 128 ГБ, SIM + eSIM", "Отличный телефон")

    # 1. Exact query: "iphone 15 128 esim"
    assert is_item_matching_search(item_base_128_esim[0], item_base_128_esim[1], exact_query) is True
    assert is_item_matching_search(item_base_256_esim[0], item_base_256_esim[1], exact_query) is False  # capacity mismatch
    assert is_item_matching_search(item_pro_128_esim[0], item_pro_128_esim[1], exact_query) is False   # pro mismatch
    assert is_item_matching_search(item_base_128_no_esim[0], item_base_128_no_esim[1], exact_query) is False  # esim mismatch
    assert is_item_matching_search(item_old_13_pro[0], item_old_13_pro[1], exact_query) is False      # generation mismatch

    # 2. Broad query: "iphone 15" (accepts all 15 models & configurations)
    assert is_item_matching_search(item_base_128_esim[0], item_base_128_esim[1], broad_query) is True
    assert is_item_matching_search(item_base_256_esim[0], item_base_256_esim[1], broad_query) is True
    assert is_item_matching_search(item_pro_128_esim[0], item_pro_128_esim[1], broad_query) is True
    assert is_item_matching_search(item_base_128_no_esim[0], item_base_128_no_esim[1], broad_query) is True
    assert is_item_matching_search(item_old_13_pro[0], item_old_13_pro[1], broad_query) is False  # generation mismatch



