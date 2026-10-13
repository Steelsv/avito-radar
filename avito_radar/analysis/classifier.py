"""Smart item classification: owners vs agencies, defects, and reseller detection."""

from __future__ import annotations

import re
from typing import Any

from avito_radar.parsers.item_parser import ParsedItem

# Real estate keywords
AGENCY_LABELS = ("агентство", "компания", "застройщик")
MANY_CLOSED_THRESHOLD = 50

NO_AGENTS_RE = re.compile(
    r"не\s+беспоко|не\s+звонит|не\s+звоните|не\s+предл[ао]г|не\s+нужн|"
    r"без\s+(?:агент|риелтор|риэлтор|посредник)|просьб|прошу|не\s+агентств|"
    r"при\s+наличии\s+(?:покупател|клиент)|риелторам\s+не",
    re.I,
)

AGENCY_TEXT_RE = re.compile(
    r"агентств\w*\s+недвижимост|наш\w*\s+(?:агентств|компани|офис|специалист)|"
    r"эксклюзивн\w*\s+(?:прав|договор)|комисси\w*\s+(?:нашего\s+)?агентства|"
    r"бесплатн\w*\s+(?:юридическ|сопровождени|подбор|консультац)|трейд[\s-]?ин|"
    r"(?:показ\w*|просмотр\w*)\s+проводит\s+(?:наш|специалист|агент|риелтор)|"
    r"номер\s+объекта|лот\s*№",
    re.I,
)

OWNER_TEXT_RE = re.compile(
    r"я\s+собственник|от\s+собственник|без\s+посредник|продаю\s+(?:свою|собственную|нашу)",
    re.I,
)

# Electronics defects
DEFECT_RE = re.compile(
    r"(?<!не\s)бит(?:ый|ая|ое|ые)\b|заблок|блокировк|icloud|айклауд|аклауд|"
    r"на\s+запчаст|на\s+разбор|под\s+восстановл|не\s+включ|не\s+работает|"
    r"разбит|треснут|утоплен|после\s+воды|залит|не\s+ловит|плата\s+мертв|донор|"
    r"условно\s*рабоч|проблем\w*\s+с\s+драйвер|кернел|kernel(?:\s*141)?|отвал|артефакт|"
    r"полос\w*\s+на\s+экран|черн\w*\s+экран|не\s+выводит|прогрет|после\s+майнинг\w*\s+не\s+работ|"
    r"вылетает|код\s*43|ошибк\w*\s+43",
    re.I,
)

# Parts & accessories
PARTS_AND_ACCESSORIES_RE = re.compile(
    r"\b(?:запчаст\w*|видеопамят\w*|чип\w*|чипы|распайк\w*|донор\w*|на\s+донор|кулер\w*|"
    r"вентилятор\w*|охлажден\w*|радиатор\w*|бэкплейт\w*|райзер\w*|кронштейн\w*|"
    r"болтик\w*|винтик\w*|винты|коробк\w*\s+от|коробка|чехол|термопрокладк\w*|термопаст\w*|"
    r"подставк\w*|кабел\w*|переходник\w*|текстолит|плата\s+без|"
    r"оперативн\w*\s+памят\w*|память\s+ddr\d|ddr[2345]|блок\w*\s+питания|материнск\w*\s+плат\w*|корпус\w*|ssd|hdd|жестк\w*\s+диск)\b",
    re.I,
)

# Multi-item listing / price list patterns
COMBO_KEYWORDS_RE = re.compile(
    r"\b(?:цена\s+от|цены\s+от|стоимость\s+от|цены?\s+в\s+описании|прайс|список\s+(?:в\s+описании|ниже)|"
    r"цена\s+указана\s+за|цена\s+за\s+(?:самый|минимальн|штук)|в\s+наличии\s+разны|в\s+наличии\s+список)\b",
    re.I,
)
NUMBERED_PRICE_LIST_RE = re.compile(
    r"(?:^|\n)\s*(?:\d+[\.\)]|[-•*])\s+[^\n]+?(?:\d[\d\s]{2,7})\s*(?:руб|р\b|₽)",
    re.I,
)
PLURAL_CATEGORIES_RE = re.compile(
    r"\b(?:видеокарты|телефоны|ноутбуки|процессоры|комплектующие)\b",
    re.I,
)
PRICE_IN_TEXT_RE = re.compile(r"(\d[\d\s]{2,7})\s*(?:руб|р\b|₽)", re.I)

# PC & Laptop vs Standalone GPU/Phone
PC_BUILD_RE = re.compile(
    r"\b(?:игров(?:ой|ые)\s+пк|системн(?:ый|ые)\s+блок|компьютер|сборк\w*\s+пк|пк\s+в\s+сборе)\b",
    re.I,
)
LAPTOP_RE = re.compile(
    r"\b(?:ноутбук|ноут|laptop|macbook|макбук)\b",
    re.I,
)

MEMORY_RE = re.compile(r"^\d+\s*(?:ГБ|ТБ|GB|TB)$", re.I)


def extract_goods_group(title: str) -> str:
    parts = [p.strip() for p in title.split(",") if p.strip()]
    if not parts:
        return title
    model = parts[0]
    mem = next((p for p in parts[1:] if MEMORY_RE.match(p)), "")
    return f"{model}, {mem}" if mem else model


def extract_desc_prices_for_query(description: str, query: str) -> list[int]:
    """Extract specific prices associated with the target model from the description."""
    if not description or not query:
        return []

    num_matches = re.findall(r"\d{2,5}", query)
    found_prices: list[int] = []

    for line in description.split("\n"):
        line_clean = line.strip()
        if not line_clean:
            continue

        matches_model = False
        if num_matches:
            if any(num in line_clean for num in num_matches):
                matches_model = True
        else:
            words = [w for w in re.split(r"[\s_-]+", query.lower()) if len(w) >= 3]
            if words and any(w in line_clean.lower() for w in words):
                matches_model = True

        if matches_model:
            for p_str in PRICE_IN_TEXT_RE.findall(line_clean):
                clean_num = int(re.sub(r"\s+", "", p_str))
                if clean_num >= 1000:
                    found_prices.append(clean_num)

    return found_prices


def classify_item(item: ParsedItem, category_type: str = "goods", search_query: str = "") -> None:
    """Analyze item and attach classification tags."""
    seller_label_low = item.seller_type.lower()
    full_text = f"{item.title} {item.description}".lower()

    if category_type == "realty":
        # Check agency vs owner
        is_agency = any(lab in seller_label_low for lab in AGENCY_LABELS)

        if is_agency or AGENCY_TEXT_RE.search(full_text):
            item.tags.append("🏢 Агентство / Риелтор")
        elif (item.closed_listings or 0) >= MANY_CLOSED_THRESHOLD:
            item.tags.append("❓ Проверить продавца (много сделок)")
        elif OWNER_TEXT_RE.search(full_text):
            item.tags.append("👤 Собственник")
        else:
            item.tags.append("👤 Частное лицо")

        if NO_AGENTS_RE.search(full_text):
            item.tags.append("🚫 Без агентов")

    else:
        # Goods / Electronics / Auto
        if (item.closed_listings or 0) >= MANY_CLOSED_THRESHOLD or any(lab in seller_label_low for lab in ("магазин", "компания")):
            item.tags.append("🏬 Магазин / Перекупщик")
        else:
            item.tags.append("👤 Частный продавец")

        if DEFECT_RE.search(full_text):
            item.tags.append("⚠️ Дефект / На запчасти")

        if PARTS_AND_ACCESSORIES_RE.search(item.title.lower()):
            item.tags.append("🔧 Запчасти / Комплектующие")

        if PC_BUILD_RE.search(item.title.lower()):
            item.tags.append("🖥 ПК в сборе")
        elif LAPTOP_RE.search(item.title.lower()):
            item.tags.append("💻 Ноутбук")

        # Clickbait price detection (< 1000 ₽ for high-tech goods)
        if item.price and item.price < 1000:
            item.tags.append("⚠️ Подозрительная цена (кликбейт / запчасть)")

        # Check combo / multi-item listing / price discrepancies in description
        is_combo = False
        numbered_matches = NUMBERED_PRICE_LIST_RE.findall(item.description)
        if len(numbered_matches) >= 2 or COMBO_KEYWORDS_RE.search(full_text):
            is_combo = True
        elif PLURAL_CATEGORIES_RE.search(item.title.lower()):
            is_combo = True

        # Try extracting model-specific prices from description if search_query is available
        desc_prices = extract_desc_prices_for_query(item.description, search_query) if search_query else []

        if desc_prices and item.price:
            real_min_p = min(desc_prices)
            # If listing price is significantly lower than real model price in description (e.g. 8000 vs 29000-32500)
            if item.price < real_min_p * 0.75:
                item.is_combo_listing = True
                item.real_price_in_desc = real_min_p
                item.tags.append("⚠️ Сборное объявление (в описании список)")
                p_fmt = f"{real_min_p:,}".replace(",", " ")
                ad_fmt = f"{item.price:,}".replace(",", " ")
                item.tags.append(f"⚠️ Реальная цена в описании: ~{p_fmt} ₽ (в объявлении {ad_fmt} ₽)")
            elif is_combo:
                item.is_combo_listing = True
                item.tags.append("⚠️ Сборное объявление (в описании список)")
        elif is_combo:
            item.is_combo_listing = True
            item.tags.append("⚠️ Сборное объявление (в описании список цен)")

    if any("доставка" in b.lower() for b in item.badges):
        item.tags.append("📦 С доставкой")


def is_likely_fake_or_junk(item: ParsedItem, min_price: int | None = None) -> bool:
    """Check if item is junk, parts, or clickbait price."""
    if min_price and item.price and item.price < min_price:
        return True
    if item.price and item.price < 500:
        return True
    if getattr(item, "is_combo_listing", False):
        return True
    for tag in item.tags:
        if any(bad in tag for bad in (
            "🔧 Запчасти",
            "⚠️ Дефект",
            "Подозрительная цена",
            "Сборное объявление",
            "Реальная цена в описании",
        )):
            return True
    return False
