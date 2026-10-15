"""Smart item classification: owners vs agencies, defects, and reseller detection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
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

# Detailed bicycle accessories, parts and gear (gravel, mtb, road bikes)
BIKE_PARTS_AND_ACCESSORIES_RE = re.compile(
    r"\b(?:"
    r"покрышк\w*|покрышка|покрышки|велопокрышк\w*|шины\s+для\s+вело\w*|"
    r"велокамер\w*|бескамерк\w*|герметик\s+для\s+шин|"
    r"сидушк\w*|сидень\w*\s+для|седл\w*|седло|подседел\w*|подседельный\s+(?:штырь|хомут|зажим)|"
    r"педал\w*|педали|контактн\w*\s+педал\w*|топталк\w*|"
    r"дропбар\w*|вынос\s+руля|вынос\w*|грипс\w*|обмотк\w*\s+руля|манетк\w*|шифтер\w*|рулев\w*\s+колонк\w*|"
    r"велоцепь\w*|цепь\s+для\s+вело\w*|кассет\w*\s+(?:shimano|sram|для)|трещотк\w*|"
    r"ротор\w*\s+(?:тормозной|shimano|sram|160|180)|калипер\w*|тормозн\w*\s+колодк\w*|"
    r"байкпакинг\w*|велосумк\w*|подседельн\w*\s+сумк\w*|сумк\w*\s+(?:на\s+раму|на\s+руль|под\s+раму)|"
    r"багажник\s+(?:для\s+вело|на\s+вело|велосипедн)|велокрыл\w*|крылья\s+(?:для\s+вело|на\s+вело)|"
    r"флягодержател\w*|велокомпьютер\w*|велофара\w*|велофонар\w*|велошлем\w*|велотуфл\w*|велоформ\w*|"
    r"джерси\s+(?:вело|для)|велоперчатк\w*|велозамок\w*|велонасос\w*|насос\s+(?:высокого\s+давления|для\s+вело)|"
    r"велостанок\w*|подножк\w*\s+для\s+вело|фреймсет\w*|веловилк\w*"
    r")\b",
    re.I,
)

# Detailed electronics, gadgets, and PC accessories
ELECTRONICS_ACCESSORIES_RE = re.compile(
    r"\b(?:"
    r"чехол\w*|чехлы|чехольчик\w*|бампер\s+(?:на|для)|"
    r"стекл\w*\s+(?:на|для|защитн\w*)|защитн\w*\s+стекл\w*|пленк\w*\s+(?:на|для|защитн\w*)|гидрогелев\w*|"
    r"ремешок\w*|браслет\s+(?:для|на)|стилус\w*|s-pen|spen|apple\s+pencil|наконечник\w*|амбушюр\w*|"
    r"кейс\s+(?:для|от)|коробк\w*\s+от|коробка\s+(?:от|для)|док-станци\w*|подставк\w*\s+(?:для|под)|"
    r"держатель\s+(?:для|в\s+авто)|magsafe\s+(?:кошелек|держатель|зарядка)|"
    r"зарядк\w*|зарядн\w*\s+устройств\w*|блок\w*\s+питания|сетев\w*\s+адаптер|кабел\w*|провод\w*|шнур\w*|"
    r"переходник\w*|кулер\w*|вентилятор\w*|радиатор\w*|термопаст\w*|термопрокладк\w*|райзер\w*|"
    r"бэкплейт\w*|кронштейн\w*|болтик\w*|винтик\w*|винты|шлейф\w*|заглушк\w*|кейкап\w*|свитч\w*|коврик\s+для\s+мыши"
    r")\b",
    re.I,
)

# Detailed auto and motorcycle accessories
AUTO_ACCESSORIES_RE = re.compile(
    r"\b(?:"
    r"коврик\w*|автоковрик\w*|авточехл\w*|накидк\w*\s+на\s+сидень\w*|брызговик\w*|дворник\w*|"
    r"щетк\w*\s+стеклоочистител\w*|дефлектор\w*|ветровик\w*|колпак\w*\s+на\s+колес\w*|колпачки\s+на\s+ниппел\w*|"
    r"подлокотник\w*|видеорегистратор\w*|радар-детектор\w*|ароматизатор\w*|пахучк\w*|шильдик\w*|спойлер\w*|"
    r"оплетк\w*\s+на\s+руль|органайзер\s+в\s+багажник|фаркоп\w*|автобокс\w*"
    r")\b",
    re.I,
)

# Generic accessories and spare parts keywords
GENERAL_ACCESSORIES_RE = re.compile(
    r"\b(?:"
    r"аксессуар\w*|запчаст\w*|комплектующ\w*|детал\w*|расходник\w*|креплени\w*|крепеж\w*|ремкомплект\w*|насадк\w*|сменн\w*"
    r")\b",
    re.I,
)

PREFIX_FOR_RE = re.compile(
    r"^(?:для|на|к|под)\s+",
    re.I,
)


def is_item_accessory(item: ParsedItem, search_query: str = "") -> tuple[bool, str]:
    """Detect if the listing is an accessory, spare part, tire, saddle, case, etc.
    Returns (is_accessory, reason_label).
    """
    title_low = item.title.lower()
    query_low = search_query.lower() if search_query else ""

    # Helper: If user's search query itself specifies this accessory, don't filter it out
    def query_mentions(stem: str) -> bool:
        if not query_low or len(stem) < 3:
            return False
        return stem.lower() in query_low

    # 1. Bike parts & accessories
    m_bike = BIKE_PARTS_AND_ACCESSORIES_RE.search(title_low)
    if m_bike:
        matched = m_bike.group(0)
        if not query_mentions(matched[:4]):
            return True, "Велозапчасть / Аксессуар"

    # Standalone bike handlebar (руль) when query is bike-related
    if re.search(r"\bруль\b", title_low, re.I) and not re.search(r"\bруль\b", query_low, re.I):
        if re.search(r"гравел|велосипед|шоссе|mtb|баран|дропбар", title_low + " " + query_low, re.I):
            return True, "Велозапчасть / Аксессуар"

    # Standalone bike tube/tire (камера)
    if re.search(r"\bкамер[аыеу]\b", title_low, re.I) and not re.search(r"\bкамер", query_low, re.I):
        if re.search(r"вело|700|28|29|26|27\.5|schwalbe|continental|maxxis|gravel|гравел", title_low, re.I):
            return True, "Велозапчасть / Аксессуар"

    # 2. Electronics accessories
    m_elec = ELECTRONICS_ACCESSORIES_RE.search(title_low)
    if m_elec:
        matched = m_elec.group(0)
        if not query_mentions(matched[:4]):
            return True, "Аксессуар / Расходник"

    # 3. Auto / Moto accessories
    m_auto = AUTO_ACCESSORIES_RE.search(title_low)
    if m_auto:
        matched = m_auto.group(0)
        if not query_mentions(matched[:4]):
            return True, "Автоаксессуар / Расходник"

    # 4. General accessories & parts
    m_gen = GENERAL_ACCESSORIES_RE.search(title_low)
    if m_gen:
        matched = m_gen.group(0)
        if not query_mentions(matched[:4]):
            return True, "Запчасти / Комплектующие"

    # 5. Starts with "Для..." or "На..." (e.g. "Для гравела...", "На iPhone...", "Для Lada...")
    if PREFIX_FOR_RE.match(title_low) and not PREFIX_FOR_RE.match(query_low):
        return True, "Аксессуар / Комплектующее"

    return False, ""


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


@dataclass
class QueryIntent:
    raw: str
    brand: str | None = None
    model_number: str | None = None
    sub_model: str | None = None
    storage: str | None = None
    features: list[str] = field(default_factory=list)


def parse_query_intent(query: str) -> QueryIntent | None:
    if not query or not query.strip():
        return None
    q = query.strip().lower()
    intent = QueryIntent(raw=query)

    # 1. Storage detection (64, 128, 256, 512, 1tb / 1тб)
    storage_match = re.search(r"(?<!\w)(64|128|256|512)\s*(?:gb|гб)?(?!\w)|(?<!\w)(1|2)\s*(?:tb|тб)(?!\w)", q, re.I)
    if storage_match:
        intent.storage = f"{storage_match.group(1)}gb" if storage_match.group(1) else f"{storage_match.group(2)}tb"

    # 2. Features (esim, etc.)
    if re.search(r"(?<!\w)(?:esim|есим|e-sim)(?!\w)", q, re.I):
        intent.features.append("esim")

    # 3. iPhone
    is_iphone = bool(re.search(r"(?<!\w)(?:iphone|айфон|айфончик)(?!\w)|(?<!\w)1[1-6]\s*(?:pro|max|plus|mini|про|макс|плюс|мини)?(?!\w)", q, re.I))
    if is_iphone:
        intent.brand = "apple_iphone"
        gen_m = re.search(r"(?<!\w)(1[1-6]|[78]|xr|xs|x|se)(?!\w)", q, re.I)
        if gen_m:
            intent.model_number = gen_m.group(1).lower()

        if re.search(r"(?<!\w)(?:pro\s*max|про\s*макс)(?!\w)", q, re.I):
            intent.sub_model = "pro max"
        elif re.search(r"(?<!\w)(?:pro|про)(?!\w)", q, re.I):
            intent.sub_model = "pro"
        elif re.search(r"(?<!\w)(?:plus|плюс)(?!\w)", q, re.I):
            intent.sub_model = "plus"
        elif re.search(r"(?<!\w)(?:mini|мини)(?!\w)", q, re.I):
            intent.sub_model = "mini"
        else:
            if intent.storage or intent.features:
                intent.sub_model = "base"
            else:
                intent.sub_model = "any"
        return intent

    # 4. GPU detection (RTX 4070, RX 6700 XT, etc.)
    gpu_m = re.search(r"(?<!\w)(rtx|gtx|rx)\s*(\d{3,4})\s*(ti\s*super|super|ti|xtx|xt)?(?!\w)", q, re.I)
    if gpu_m:
        intent.brand = gpu_m.group(1).lower()
        intent.model_number = gpu_m.group(2)
        sub = re.sub(r"\s+", " ", gpu_m.group(3) or "").strip().lower()
        intent.sub_model = sub if sub else "any"
        return intent

    # 5. Console detection (PS5, PlayStation 5)
    ps_m = re.search(r"(?<!\w)(?:playstation|ps|пс)\s*([345])(?!\w)", q, re.I)
    if ps_m:
        intent.brand = "playstation"
        intent.model_number = ps_m.group(1)
        if re.search(r"(?<!\w)(?:pro|про)(?!\w)", q, re.I):
            intent.sub_model = "pro"
        elif re.search(r"(?<!\w)(?:slim|слим)(?!\w)", q, re.I):
            intent.sub_model = "slim"
        else:
            intent.sub_model = "any"
        return intent

    # 6. Generic brand + model number (e.g. Format 5222, BMW 3, Camry 70)
    gen_m = re.search(r"(?<!\w)([a-zA-Zа-яА-ЯёЁ]{2,})\s+(\d{1,4}[a-zA-Zа-яА-ЯёЁ]?)(?!\w)", q, re.I)
    if gen_m:
        intent.brand = gen_m.group(1).lower()
        intent.model_number = gen_m.group(2).lower()
        return intent

    return intent


def parse_item_model(title: str, description: str = "") -> dict[str, Any]:
    t = (title or "").lower()
    full = f"{t} {description}".lower()
    item: dict[str, Any] = {
        "brand": None,
        "model_number": None,
        "sub_model": None,
        "storage": None,
        "features": [],
    }

    # Storage
    st_m = re.search(r"(?<!\w)(64|128|256|512)\s*(?:gb|гб)?(?!\w)|(?<!\w)(1|2)\s*(?:tb|тб)(?!\w)", t, re.I)
    if st_m:
        item["storage"] = f"{st_m.group(1)}gb" if st_m.group(1) else f"{st_m.group(2)}tb"

    # eSIM
    if re.search(r"(?<!\w)(?:esim|есим|e-sim)(?!\w)", full, re.I):
        item["features"].append("esim")

    # iPhone
    if re.search(r"(?<!\w)(?:iphone|айфон|айфончик)(?!\w)|(?<!\w)1[1-6]\s*(?:pro|max|plus|mini|про|макс|плюс|мини)?(?!\w)", t, re.I):
        item["brand"] = "apple_iphone"
        gen_m = re.search(r"(?<!\w)(1[1-6]|[78]|xr|xs|x|se)(?!\w)", t, re.I)
        if gen_m:
            item["model_number"] = gen_m.group(1).lower()
        if re.search(r"(?<!\w)(?:pro\s*max|про\s*макс)(?!\w)", t, re.I):
            item["sub_model"] = "pro max"
        elif re.search(r"(?<!\w)(?:pro|про)(?!\w)", t, re.I):
            item["sub_model"] = "pro"
        elif re.search(r"(?<!\w)(?:plus|плюс)(?!\w)", t, re.I):
            item["sub_model"] = "plus"
        elif re.search(r"(?<!\w)(?:mini|мини)(?!\w)", t, re.I):
            item["sub_model"] = "mini"
        else:
            item["sub_model"] = "base"
        return item

    # GPU
    gpu_m = re.search(r"(?<!\w)(rtx|gtx|rx)\s*(\d{3,4})\s*(ti\s*super|super|ti|xtx|xt)?(?!\w)", t, re.I)
    if gpu_m:
        item["brand"] = gpu_m.group(1).lower()
        item["model_number"] = gpu_m.group(2)
        sub = re.sub(r"\s+", " ", gpu_m.group(3) or "").strip().lower()
        item["sub_model"] = sub if sub else "base"
        return item

    # PlayStation
    ps_m = re.search(r"(?<!\w)(?:playstation|ps|пс)\s*([345])(?!\w)", t, re.I)
    if ps_m:
        item["brand"] = "playstation"
        item["model_number"] = ps_m.group(1)
        if re.search(r"(?<!\w)(?:pro|про)(?!\w)", t, re.I):
            item["sub_model"] = "pro"
        elif re.search(r"(?<!\w)(?:slim|слим)(?!\w)", t, re.I):
            item["sub_model"] = "slim"
        else:
            item["sub_model"] = "base"
        return item

    # Generic brand + model number
    gen_m = re.search(r"(?<!\w)([a-zA-Zа-яА-ЯёЁ]{2,})\s+(\d{1,4}[a-zA-Zа-яА-ЯёЁ]?)(?!\w)", t, re.I)
    if gen_m:
        item["brand"] = gen_m.group(1).lower()
        item["model_number"] = gen_m.group(2).lower()
        return item

    return item


def is_item_matching_search(title: str, description: str, query: str) -> bool:
    if not query or not query.strip():
        return True
    intent = parse_query_intent(query)
    if not intent or not intent.model_number:
        return True

    item = parse_item_model(title, description)

    # 1. Generation / Model number check: STRICT
    if intent.model_number and item.get("model_number"):
        if intent.model_number != item["model_number"]:
            return False
    elif intent.model_number and not item.get("model_number"):
        t = (title or "").lower()
        conflicting = re.search(r"(?<!\w)(1[1-6]|[78]|xr|xs|x)(?!\w)", t, re.I)
        if conflicting and conflicting.group(1).lower() != intent.model_number:
            return False

    # 2. Sub-model check
    if intent.sub_model and intent.sub_model != "any":
        if intent.sub_model == "base":
            if item.get("sub_model") and item["sub_model"] != "base":
                return False
        else:
            if item.get("sub_model") != intent.sub_model:
                return False

    # 3. Storage check
    if intent.storage and item.get("storage"):
        if intent.storage != item["storage"]:
            return False

    # 4. Feature check (e.g. esim)
    if intent.features:
        for feat in intent.features:
            if feat not in item.get("features", []):
                return False

    return True


def extract_goods_group(title: str) -> str:
    parsed = parse_item_model(title, "")
    if parsed.get("brand") == "apple_iphone" and parsed.get("model_number"):
        sub = f" {parsed['sub_model']}" if parsed.get("sub_model") and parsed["sub_model"] != "base" else ""
        mem = f", {parsed['storage']}" if parsed.get("storage") else ""
        return f"iPhone {parsed['model_number']}{sub}{mem}".strip()
    elif parsed.get("brand") in ("rtx", "gtx", "rx") and parsed.get("model_number"):
        sub = f" {parsed['sub_model']}" if parsed.get("sub_model") and parsed["sub_model"] != "base" else ""
        return f"{parsed['brand'].upper()} {parsed['model_number']}{sub}".strip()
    elif parsed.get("brand") == "playstation" and parsed.get("model_number"):
        sub = f" {parsed['sub_model']}" if parsed.get("sub_model") and parsed["sub_model"] != "base" else ""
        return f"PlayStation {parsed['model_number']}{sub}".strip()

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

        is_acc, acc_label = is_item_accessory(item, search_query)
        if is_acc:
            item.is_accessory = True
            item.tags.append(f"🛡️ {acc_label}")

        # Check model/generation mismatch against search query intent
        if search_query:
            if not is_item_matching_search(item.title, item.description, search_query):
                item.is_mismatched_model = True
                item.tags.append("⚠️ Другая модель / поколение")

        if DEFECT_RE.search(full_text):
            item.tags.append("⚠️ Дефект / На запчасти")

        if PARTS_AND_ACCESSORIES_RE.search(item.title.lower()) and not is_acc:
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
    """Check if item is junk, parts, accessories, or clickbait price."""
    if getattr(item, "is_mismatched_model", False):
        return True
    if getattr(item, "is_accessory", False):
        return True
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
            "Аксессуар",
            "Велозапчасть",
            "Автоаксессуар",
        )):
            return True
    return False
