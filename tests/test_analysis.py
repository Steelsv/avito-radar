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


def test_icloud_defect_segregation_and_median():
    """Verify that an iCloud-locked iPhone is flagged as defect and excluded from depressing market median."""
    from avito_radar.notifications.telegram import format_ad_message

    def make_iphone(pid: int, title: str, price: int, desc: str):
        return ParsedItem(
            id=pid,
            title=title,
            price=price,
            price_formatted=f"{price:,} ₽".replace(",", " "),
            url=f"https://www.avito.ru/{pid}",
            address="Москва",
            metro="",
            city="moskva",
            published_text="сегодня",
            sort_timestamp=None,
            seller_name="Продавец",
            seller_type="частное лицо",
            seller_rating=5.0,
            closed_listings=3,
            badges=(),
            images=[],
            description=desc,
            phone_available=True,
        )

    locked_item = make_iphone(101, "iPhone 15, 128 ГБ", 20000, "Телефон в идеале внешне, но iCloud заблокирован, продается на запчасти или под байпас.")
    working1 = make_iphone(102, "iPhone 15, 128 ГБ", 60000, "Отличное состояние, полный комплект, все функции работают.")
    working2 = make_iphone(103, "iPhone 15, 128 ГБ", 62000, "Идеальное состояние, АКБ 100%, без ремонтов.")
    working3 = make_iphone(104, "iPhone 15, 128 ГБ", 59000, "Хорошее состояние, чек, коробка.")

    classify_item(locked_item, category_type="goods", search_query="iphone 15")
    classify_item(working1, category_type="goods", search_query="iphone 15")
    classify_item(working2, category_type="goods", search_query="iphone 15")
    classify_item(working3, category_type="goods", search_query="iphone 15")

    # 1. Defect flags
    assert locked_item.is_defect is True
    assert locked_item.defect_type == "icloud"
    assert any("iCloud" in t for t in locked_item.tags)
    assert working1.is_defect is False

    # 2. Annotate market prices
    items = [locked_item, working1, working2, working3]
    annotate_market_prices(items)

    # 3. Market median must be around ~60 000 ₽ for working phones, NOT depressed by the 20 000 ₽ locked item
    assert working1.market_price == 60000
    assert working1.market_diff_percent == 0.0  # (60000 - 60000) / 60000 = 0% (NOT +73% higher!)

    # 4. Locked item must NOT get a false super-deal discount
    assert locked_item.market_diff_percent is None
    assert not any("Супер-цена" in t for t in locked_item.tags)
    assert not any("Выгодно" in t for t in locked_item.tags)

    # 5. Telegram alert for locked item must warn about iCloud, not say "НАЙДЕН ВЫГОДНЫЙ ЛОТ"
    alert_msg = format_ad_message("iphone 15", locked_item)
    assert "ICLOUD ЗАБЛОКИРОВАН" in alert_msg
    assert "НАЙДЕН ВЫГОДНЫЙ ЛОТ" not in alert_msg


def test_exchange_wtb_detection_and_median_exclusion():
    """Verify that exchange/trade listings are detected, excluded from median, and don't distort pricing."""
    item_exchange = ParsedItem(
        id=201,
        title="Обменяю R5 5600 на R7 5700X с доплатой",
        price=100,
        price_formatted="100 ₽",
        url="https://www.avito.ru/201",
        address="Челябинск",
        metro="",
        city="chelyabinsk",
        published_text="сегодня",
        sort_timestamp=None,
        seller_name="Продавец",
        seller_type="частное лицо",
        seller_rating=5.0,
        closed_listings=2,
        badges=(),
        images=[],
        description="Хочу обменять свой процессор Ryzen 5 5600 на R7 5700x с моей доплатой. Не продаю, только обмен!",
        phone_available=True,
    )
    def make_cpu(pid: int, price: int):
        return ParsedItem(
            id=pid,
            title="Процессор AMD Ryzen 7 5700X",
            price=price,
            price_formatted=f"{price:,} ₽".replace(",", " "),
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
            description="Отличный рабочий процессор.",
            phone_available=True,
        )

    c1 = make_cpu(202, 13500)
    c2 = make_cpu(203, 14000)
    c3 = make_cpu(204, 13000)

    classify_item(item_exchange, category_type="goods", search_query="r7 5700x")
    classify_item(c1, category_type="goods", search_query="r7 5700x")
    classify_item(c2, category_type="goods", search_query="r7 5700x")
    classify_item(c3, category_type="goods", search_query="r7 5700x")

    assert item_exchange.is_exchange_or_wtb is True
    assert any("Обмен" in t for t in item_exchange.tags)

    items = [item_exchange, c1, c2, c3]
    annotate_market_prices(items)

    # Median must be ~13 500 ₽, NOT distorted by the 100 ₽ exchange listing
    assert c1.market_price == 13500
    assert c1.market_diff_percent == 0.0

    assert item_exchange.market_price is None
    assert item_exchange.market_diff_percent is None


def test_cpu_combo_pool_price_in_description():
    """Verify that multi-item CPU pool listings extract genuine price from description and don't calculate fake -81.5%."""
    item_combo = ParsedItem(
        id=301,
        title="Xeon E3 1241v3, 1240v2, R7 5700x, R5 5600X",
        price=2500,
        price_formatted="2 500 ₽",
        url="https://www.avito.ru/301",
        address="Челябинск",
        metro="",
        city="chelyabinsk",
        published_text="сегодня",
        sort_timestamp=None,
        seller_name="Продавец",
        seller_type="частное лицо",
        seller_rating=5.0,
        closed_listings=25,
        badges=(),
        images=[],
        description=(
            "Продам процессоры:\n"
            "1. Xeon E3 1241v3 — 2 500 руб.\n"
            "2. Xeon 1240v2 — 2 200 руб.\n"
            "3. R5 5600X — 9 500 руб.\n"
            "4. R7 5700x — 13 000 руб."
        ),
        phone_available=True,
    )
    def make_cpu(pid: int, price: int):
        return ParsedItem(
            id=pid,
            title="AMD Ryzen 7 5700X OEM",
            price=price,
            price_formatted=f"{price:,} ₽".replace(",", " "),
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
            description="Процессор R7 5700X в отличном состоянии.",
            phone_available=True,
        )

    c1 = make_cpu(302, 13500)
    c2 = make_cpu(303, 14000)
    c3 = make_cpu(304, 13000)

    classify_item(item_combo, category_type="goods", search_query="r7 5700x")
    classify_item(c1, category_type="goods", search_query="r7 5700x")
    classify_item(c2, category_type="goods", search_query="r7 5700x")
    classify_item(c3, category_type="goods", search_query="r7 5700x")

    assert item_combo.is_combo_listing is True
    assert item_combo.is_in_desc_or_list is True
    assert item_combo.real_price_in_desc == 13000
    assert any("Товар в списке" in t for t in item_combo.tags)

    items = [item_combo, c1, c2, c3]
    annotate_market_prices(items)

    # Market median must be ~13 250 - 13 500 ₽ (based on 13000, 13500, 14000, 13000, NOT 2500 ₽)
    assert 13000 <= c1.market_price <= 13500

    # Combo diff percent must be computed using real price 13000, NOT the 2500 ₽ bait price!
    assert item_combo.market_diff_percent is not None
    # (13000 - 13250) / 13250 * 100 is approx -1.9% to -3.7%, NEVER -81.5%!
    assert -10.0 <= item_combo.market_diff_percent <= 5.0


def test_daewoo_matiz_auto_filtering():
    """Verify that auto parts (doors, bumpers) and crashed/dead cars are excluded from Daewoo Matiz median."""
    def make_car_lot(pid: int, title: str, price: int, desc: str = ""):
        return ParsedItem(
            id=pid,
            title=title,
            price=price,
            price_formatted=f"{price:,} ₽".replace(",", " "),
            url=f"https://www.avito.ru/{pid}",
            address="Челябинск",
            metro="",
            city="chelyabinsk",
            published_text="сегодня",
            sort_timestamp=None,
            seller_name="Продавец",
            seller_type="частное лицо",
            seller_rating=5.0,
            closed_listings=3,
            badges=(),
            images=[],
            description=desc,
            phone_available=True,
        )

    door_lot = make_car_lot(401, "Дверь передняя левая Daewoo Matiz", 3000, "В хорошем состоянии, цвет серебристый.")
    bumper_lot = make_car_lot(402, "Бампер передний на Daewoo Matiz", 2500, "Новый грунтованный.")
    crashed_lot = make_car_lot(403, "Daewoo Matiz, 2008 битый после ДТП не на ходу", 35000, "После серьезного ДТП, кузов повело, не на ходу, под разбор.")

    car1 = make_car_lot(404, "Daewoo Matiz 0.8 MT, 2008, 120 000 км", 190000, "Отличный городской авто, двигатель шепчет.")
    car2 = make_car_lot(405, "Daewoo Matiz 0.8 MT, 2010, 95 000 км", 210000, "Без ДТП, кондиционер, ГУР.")
    car3 = make_car_lot(406, "Daewoo Matiz 0.8 MT, 2011, 80 000 км", 230000, "Один хозяин, ухоженный автомобиль.")

    q = "daewoo matiz"
    classify_item(door_lot, category_type="auto", search_query=q)
    classify_item(bumper_lot, category_type="auto", search_query=q)
    classify_item(crashed_lot, category_type="auto", search_query=q)
    classify_item(car1, category_type="auto", search_query=q)
    classify_item(car2, category_type="auto", search_query=q)
    classify_item(car3, category_type="auto", search_query=q)

    # 1. Door and Bumper must be identified as accessories / parts
    assert door_lot.is_accessory is True
    assert bumper_lot.is_accessory is True

    # 2. Crashed car must be identified as defect / dead
    assert crashed_lot.is_defect is True

    # 3. Running whole cars must NOT be flagged as accessory or defect
    assert car1.is_accessory is False
    assert car1.is_defect is False

    # 4. Annotate market prices
    items = [door_lot, bumper_lot, crashed_lot, car1, car2, car3]
    annotate_market_prices(items)

    # 5. Market median must be ~210 000 ₽, NOT depressed by 3 000 ₽ door or 35 000 ₽ crash
    assert car2.market_price == 210000
    assert car2.market_diff_percent == 0.0
    assert car1.market_diff_percent == -9.5  # (190000 - 210000) / 210000 = -9.5%
    assert crashed_lot.market_diff_percent is None  # no false super deal tag on wrecked car!





