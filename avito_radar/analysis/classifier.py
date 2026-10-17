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

# Specific Defect Patterns
ICLOUD_LOCK_RE = re.compile(
    r"\b(?:"
    r"icloud|айклауд|аклауд|activation\s*lock|заблокирован(?:\s+на\s+icloud|\s+apple|\s+экран|\s+телефон|\s+айфон)?|"
    r"забыли\s+(?:пароль|код|apple\s*id|айклауд)|apple\s*id|lock\b|лоченый|залочен\w*|"
    r"mdm\b|корпоративн\w*\s+профиль|bypass|байпас|демо\b|demo\b"
    r")\b",
    re.I,
)

DONOR_DEAD_RE = re.compile(
    r"\b(?:"
    r"на\s+запчаст\w*|на\s+разбор\w*|под\s+восстановлен\w*|не\s+включается|не\s+включ\w*|"
    r"труп\b|донор\w*|плата\s+мертв\w*|кирпич\b|после\s+воды|утоплен\w*|залит\w*|"
    r"условно\s*рабоч\w*|отвал\b|артефакт\w*|"
    r"после\s+дтп|битый|битая|битое|битые|перевертыш|не\s+на\s+ходу|без\s+двигателя|без\s+мотора|"
    r"запрет(?:\s+рег\w*|\s+регистрац\w*)?|без\s+документов|без\s+птс|в\s+разбор|авторазбор\w*|утиль\b"
    r")\b",
    re.I,
)

SCREEN_DEFECT_RE = re.compile(
    r"\b(?:"
    r"разбит\w*\s+экран|треснут\w*\s+экран|черн\w*\s+экран|полос\w*\s+на\s+экран|"
    r"экран\s+под\s+замену|битый\s+экран|пятн\w*\s+на\s+диспле\w*|пятно\s+на\s+экран\w*"
    r")\b",
    re.I,
)

# Exchange / Trade / WTB (Want To Buy) patterns
EXCHANGE_WTB_RE = re.compile(
    r"\b(?:"
    r"обмен\s+(?:на|с\s+доплатой)|обменяю\s+(?:на|с\s+доплатой)|обменял\s+бы\s+на|"
    r"рассмотрю\s+обмен\s+на|только\s+обмен|обмен\b|обменяю\b|"
    r"куплю\b|ищу\b|приму\s+в\s+дар|скупка\b|выкуп\b|спрос\b"
    r")\b",
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

# Detailed auto and motorcycle accessories & spare parts
AUTO_ACCESSORIES_RE = re.compile(
    r"\b(?:"
    r"коврик\w*|автоковрик\w*|авточехл\w*|накидк\w*\s+на\s+сидень\w*|брызговик\w*|дворник\w*|"
    r"щетк\w*\s+стеклоочистител\w*|дефлектор\w*|ветровик\w*|колпак\w*\s+на\s+колес\w*|колпачки\s+на\s+ниппел\w*|"
    r"подлокотник\w*|видеорегистратор\w*|радар-детектор\w*|ароматизатор\w*|пахучк\w*|шильдик\w*|спойлер\w*|"
    r"оплетк\w*\s+на\s+руль|органайзер\s+в\s+багажник|фаркоп\w*|автобокс\w*|"
    r"бампер\w*|капот\w*|дверь\w*|двери|крыло\w*|фара\w*|фары|фонарь\w*|фонари|лобовое(?:\s+стекло)?|"
    r"стеклоподъемник\w*|генератор\w*|стартер\w*|мкпп|акпп|двигатель\w*|глушитель\w*|радиатор\w*|"
    r"амортизатор\w*|стойк\w*|рычаг\w*|рулев\w*\s+рейк\w*|суппорт\w*|сцеплени\w*|тормозн\w*\s+диск\w*|авторазбор\w*"
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

    # 4. CPU detection (Ryzen, Core i, Xeon)
    ryzen_m = re.search(r"(?<!\w)(?:ryzen|райзен|r)\s*([3579])\s*[-]?\s*(\d{4}[a-z0-9]*)?(?!\w)", q, re.I)
    if ryzen_m:
        intent.brand = "amd_ryzen"
        intent.sub_model = f"r{ryzen_m.group(1)}"
        if ryzen_m.group(2):
            intent.model_number = ryzen_m.group(2).lower()
        return intent

    intel_m = re.search(r"(?<!\w)(?:intel\s+)?(?:core\s+)?i([3579])\s*[-]?\s*(\d{4,5}[a-z0-9]*)?(?!\w)", q, re.I)
    if intel_m:
        intent.brand = "intel_core"
        intent.sub_model = f"i{intel_m.group(1)}"
        if intel_m.group(2):
            intent.model_number = intel_m.group(2).lower()
        return intent

    xeon_m = re.search(r"(?<!\w)xeon\s*(?:e[357]\s*)?(\d{4}[a-z0-9\s]*v\d|\d{4}[a-z0-9]*)(?!\w)", q, re.I)
    if xeon_m:
        intent.brand = "intel_xeon"
        intent.model_number = xeon_m.group(1).lower().replace(" ", "")
        return intent

    # 5. GPU detection (RTX 4070, RX 6700 XT, etc.)
    gpu_m = re.search(r"(?<!\w)(rtx|gtx|rx)\s*(\d{3,4})\s*(ti\s*super|super|ti|xtx|xt)?(?!\w)", q, re.I)
    if gpu_m:
        intent.brand = gpu_m.group(1).lower()
        intent.model_number = gpu_m.group(2)
        sub = re.sub(r"\s+", " ", gpu_m.group(3) or "").strip().lower()
        intent.sub_model = sub if sub else "any"
        return intent

    # 6. Console detection (PS5, PlayStation 5)
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

    # 7. Generic brand + model number (e.g. Format 5222, BMW 3, Camry 70)
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

    # RAM (12/256 style or explicit "8GB RAM / 8 ГБ ОЗУ")
    ram_m = re.search(
        r"(?<![\d/])(\d{1,2})\s*/\s*(?:64|128|256|512|1024)\b|"
        r"(?<!\w)(\d{1,2})\s*(?:gb|гб)\s*(?:ram|ozu|озу|оператив\w*)",
        t, re.I,
    )
    if ram_m:
        ram_val = ram_m.group(1) or ram_m.group(2)
        if ram_val and int(ram_val) <= 24:
            item["ram"] = f"{ram_val}gb"

    # --- Apple Watch / AirPods / iPad / MacBook (MUST be checked before iPhone:
    # --- bare "11"/"13" in their titles would otherwise trigger the loose iPhone pattern)
    watch_m = re.search(r"(?<!\w)(?:apple\s*watch|iwatch|апл\s*вотч|watch\s+(?:series|ultra|se))(?!\w)", t)
    if watch_m:
        item["brand"] = "apple_watch"
        if re.search(r"(?<!\w)ultra(?!\w)", t):
            item["sub_model"] = "ultra"
        elif re.search(r"(?<!\w)se(?!\w)", t):
            item["sub_model"] = "se"
        else:
            item["sub_model"] = "series"
        gen_m = (
            re.search(r"(?<!\w)(?:series|серия|серии)\s*(\d{1,2})(?!\d)", t)
            or re.search(r"(?<!\w)(?:ultra|se)\s*(\d)(?!\d)", t)
        )
        if gen_m:
            item["model_number"] = gen_m.group(1)
        size_m = re.search(r"(?<!\w)(3[89]|4[0-9]|5[0-9])\s*(?:mm|мм)(?!\w)", t)
        if size_m:
            item["size"] = f"{size_m.group(1)}mm"
        return item

    if re.search(r"(?<!\w)(?:air\s*pods|аирподс\w*)(?!\w)", t):
        item["brand"] = "apple_airpods"
        if re.search(r"(?<!\w)max(?!\w)", t):
            item["sub_model"] = "max"
        elif re.search(r"(?<!\w)pro(?!\w)", t):
            item["sub_model"] = "pro"
        else:
            item["sub_model"] = "base"
        gen_m = (
            re.search(r"(?<!\w)(?:pro|max)\s*(\d)(?!\d)", t)
            or re.search(r"(?<!\w)(?:air\s*pods|аирподс\w*)\s*(\d{1,2})(?!\d)", t)
            or re.search(r"(?<!\w)(\d)(?:st|nd|rd|th)\s*(?:gen|поколение)", t)
        )
        if gen_m:
            item["model_number"] = gen_m.group(1)
        return item

    if re.search(r"(?<!\w)(?:ipad|i-pad|айпад|ипад)(?!\w)", t):
        item["brand"] = "apple_ipad"
        if re.search(r"(?<!\w)(?:pro|про)(?!\w)", t):
            item["sub_model"] = "pro"
        elif re.search(r"(?<!\w)air(?!\w)", t):
            item["sub_model"] = "air"
        elif re.search(r"(?<!\w)(?:mini|мини)(?!\w)", t):
            item["sub_model"] = "mini"
        else:
            item["sub_model"] = "base"
        chip_m = re.search(r"(?<!\w)m([1-4])(?!\w)", t)
        if chip_m:
            item["model_number"] = f"m{chip_m.group(1)}"
        else:
            gen_m = (
                re.search(r"(?<!\w)(?:air|mini|мини)\s+(\d{1,2})(?!\d)", t)
                or re.search(r"(?<!\w)(?:ipad|айпад|ипад)\s+(\d{1,2})(?![\.\d])", t)
            )
            if gen_m:
                gen_val = int(gen_m.group(1))
                if gen_val > 10:
                    item["size"] = gen_m.group(1)
                else:
                    item["model_number"] = gen_m.group(1)
        size_m = (
            re.search(r"(?<!\w)(8\.3|9\.7|10\.2|10\.5|10\.9|12\.9)(?!\d)", t)
            or (re.search(r"(?<!\w)(?:pro|про)\s*(11|13)(?!\d)", t) if item["sub_model"] == "pro" else None)
        )
        if size_m and not item.get("size"):
            item["size"] = size_m.group(1)
        return item

    if re.search(r"(?<!\w)(?:macbook|mac\s*book|макбук)(?!\w)", t):
        item["brand"] = "apple_macbook"
        if re.search(r"(?<!\w)(?:pro|про)(?!\w)", t):
            item["sub_model"] = "pro"
        elif re.search(r"(?<!\w)air(?!\w)", t):
            item["sub_model"] = "air"
        else:
            item["sub_model"] = "base"
        chip_m = re.search(r"(?<!\w)m([1-4])\s*(pro|max)?(?!\w)", t)
        if chip_m:
            item["model_number"] = f"m{chip_m.group(1)}" + (f" {chip_m.group(2)}" if chip_m.group(2) else "")
        size_m = re.search(r"(?<!\w)(13\.3|13\.6|14\.2|15\.3|13|14|15|16)(?=[\s\"”]|$|,)", t)
        if size_m:
            item["size"] = size_m.group(1)
        return item

    # --- Android phones (before iPhone: "Redmi Note 13" contains bare "13") ---
    galaxy_m = re.search(r"(?<!\w)(?:samsung|galaxy|самсунг|галакси)(?!\w)", t)
    if galaxy_m and not re.search(r"(?<!\w)(?:tab|buds|watch|book|tabom|часы)(?!\w)", t):
        item["brand"] = "samsung_galaxy"
        note_m = re.search(r"(?<!\w)note\s*(\d{1,2})\s*(pro\s*\+|pro\s*plus|pro|ultra|plus|\+)?", t)
        s_m = re.search(r"(?<!\w)[sс](\d{1,2})\s*(ultra|plus|\+|fe)?(?!\w)", t)
        am_m = re.search(r"(?<!\w)([amам])(\d{2,3})\s*[a-z]?(?!\w)", t)
        sub_tokens: list[str] = []
        if note_m:
            item["model_number"] = f"note {note_m.group(1)}"
            sub_raw = note_m.group(2) or ""
        elif s_m:
            item["model_number"] = f"s{s_m.group(1)}"
            sub_raw = s_m.group(2) or ""
        elif am_m:
            letter = "a" if am_m.group(1) in ("a", "а") else "m"
            item["model_number"] = f"{letter}{am_m.group(2)}"
            sub_raw = ""
        else:
            sub_raw = ""
        if sub_raw:
            if "pro" in sub_raw:
                sub_tokens.append("pro")
            if "ultra" in sub_raw:
                sub_tokens.append("ultra")
            if "+" in sub_raw or "plus" in sub_raw:
                sub_tokens.append("plus")
            if "fe" in sub_raw:
                sub_tokens.append("fe")
        if re.search(r"(?<!\w)(?:ultra|ультра)(?!\w)", t):
            if "ultra" not in sub_tokens:
                sub_tokens.append("ultra")
        item["sub_model"] = " ".join(sub_tokens) if sub_tokens else "base"
        return item

    mi_m = re.search(r"(?<!\w)(?:xiaomi|redmi|poco|сяоми|редми|поко)(?!\w)", t)
    if mi_m:
        if re.search(r"(?<!\w)(?:poco|поко)(?!\w)", t):
            item["brand"] = "poco"
        elif re.search(r"(?<!\w)(?:redmi|редми)(?!\w)", t):
            item["brand"] = "redmi"
        else:
            item["brand"] = "xiaomi"
        note_m = re.search(r"(?<!\w)note\s*(\d{1,2})\s*(pro\s*\+|pro\s*plus|pro|ultra|plus|\+|s)?", t)
        poco_m = re.search(r"(?<!\w)(?:poco|поко)\s*([xfmc])(\d{1,2})\s*(pro|gt|plus|\+)?", t)
        redmi_m = re.search(r"(?<!\w)(?:redmi|редми)\s*(\d{1,2})\s*([a-c])?(?!\w)", t)
        mi_m2 = re.search(r"(?<!\w)(?:xiaomi|сяоми)\s*(?:mi\s*)?(\d{1,2})\s*(t\s*pro|t|pro|ultra|lite)?", t)
        sub_raw = ""
        if note_m:
            item["model_number"] = f"note {note_m.group(1)}"
            sub_raw = note_m.group(2) or ""
        elif poco_m:
            item["model_number"] = f"{poco_m.group(1)}{poco_m.group(2)}"
            sub_raw = poco_m.group(3) or ""
        elif mi_m2 and item["brand"] == "xiaomi":
            item["model_number"] = mi_m2.group(1)
            sub_raw = mi_m2.group(2) or ""
        elif redmi_m:
            item["model_number"] = f"{redmi_m.group(1)}{redmi_m.group(2) or ''}"
        sub_raw = sub_raw.replace("+", " plus").replace("  ", " ").strip()
        item["sub_model"] = re.sub(r"\s+", " ", sub_raw) if sub_raw else "base"
        return item

    pixel_m = re.search(r"(?<!\w)(?:google\s+)?pixel\s*(\d{1,2})\s*(pro\s*xl|pro|fold|a)?(?!\w)", t)
    if pixel_m and re.search(r"(?<!\w)(?:google|pixel\s*\d|пиксел)(?!\w)", t):
        item["brand"] = "google_pixel"
        item["model_number"] = pixel_m.group(1)
        item["sub_model"] = re.sub(r"\s+", " ", pixel_m.group(2) or "").strip() or "base"
        return item

    # --- RAM kits (DDR4/DDR5) ---
    ddr_m = re.search(r"(?<!\w)(?:ddr|ддр)\s*([2345])(?!\w)", t)
    if ddr_m and (re.search(r"(?<!\w)\d{1,3}\s*(?:gb|гб)(?!\w)", t) or re.search(r"(?<!\w)\d{3,4}\s*(?:mhz|мгц)(?!\w)", t)):
        item["brand"] = f"ram_ddr{ddr_m.group(1)}"
        cap_m = re.search(r"(?<!\w)(\d{1,3})\s*(?:gb|гб)(?!\w)", t)
        if cap_m and not item.get("storage"):
            item["storage"] = f"{cap_m.group(1)}gb"
        speed_m = re.search(r"(?<!\w)(\d{3,4})\s*(?:mhz|мгц)(?!\w)", t)
        if speed_m:
            item["model_number"] = speed_m.group(1)
        if re.search(r"(?<!\w)sodimm|со-?димм(?!\w)", t):
            item["sub_model"] = "sodimm"
        return item

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

    # CPU
    ryzen_m = re.search(r"(?<!\w)(?:ryzen|райзен|r)\s*([3579])\s*[-]?\s*(\d{4}[a-z0-9]*)?(?!\w)", t, re.I)
    if ryzen_m:
        item["brand"] = "amd_ryzen"
        item["sub_model"] = f"r{ryzen_m.group(1)}"
        if ryzen_m.group(2):
            item["model_number"] = ryzen_m.group(2).lower()
        return item

    intel_m = re.search(r"(?<!\w)(?:intel\s+)?(?:core\s+)?i([3579])\s*[-]?\s*(\d{4,5}[a-z0-9]*)?(?!\w)", t, re.I)
    if intel_m:
        item["brand"] = "intel_core"
        item["sub_model"] = f"i{intel_m.group(1)}"
        if intel_m.group(2):
            item["model_number"] = intel_m.group(2).lower()
        return item

    xeon_m = re.search(r"(?<!\w)xeon\s*(?:e[357]\s*)?(\d{4}[a-z0-9\s]*v\d|\d{4}[a-z0-9]*)(?!\w)", t, re.I)
    if xeon_m:
        item["brand"] = "intel_xeon"
        item["model_number"] = xeon_m.group(1).lower().replace(" ", "")
        return item

    # GPU
    gpu_m = re.search(r"(?<!\w)(rtx|gtx|rx)\s*(\d{3,4})\s*(ti\s*super|super|ti|xtx|xt)?(?!\w)", t, re.I)
    if gpu_m:
        item["brand"] = gpu_m.group(1).lower()
        item["model_number"] = gpu_m.group(2)
        sub = re.sub(r"\s+", " ", gpu_m.group(3) or "").strip().lower()
        item["sub_model"] = sub if sub else "base"
        if not item.get("storage"):
            vram_m = re.search(r"(?<!\w)(4|6|8|12|16|24|32)\s*(?:gb|гб)(?!\w)", t, re.I)
            if vram_m:
                item["storage"] = f"{vram_m.group(1)}gb"
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
        if re.search(r"(?<!\w)(?:digital|диджитал|цифров\w*)(?!\w)|без\s+(?:диска|дисковода)", t, re.I):
            item["features"].append("digital")
        return item

    # Xbox
    if re.search(r"(?<!\w)(?:xbox|иксбокс|x-box)(?!\w)", t, re.I):
        item["brand"] = "xbox"
        if re.search(r"(?<!\w)series(?!\w)", t, re.I):
            item["sub_model"] = "series"
        elif re.search(r"(?<!\w)one(?!\w)", t, re.I):
            item["sub_model"] = "one"
        elif re.search(r"(?<!\w)360(?!\w)", t, re.I):
            item["sub_model"] = "360"
        else:
            item["sub_model"] = "base"
        rev_m = re.search(r"(?<!\w)(?:series|one)\s*([xs])(?!\w)", t, re.I)
        if rev_m:
            item["model_number"] = rev_m.group(1).lower()
        return item

    # Nintendo Switch
    if re.search(r"(?<!\w)(?:nintendo|нинтендо)(?!\w)", t, re.I) or (
        re.search(r"(?<!\w)switch(?!\w)", t, re.I)
        and re.search(r"(?<!\w)(?:oled|lite|neon|joy-?con|консоль|приставк\w*)(?!\w)", t, re.I)
        and not re.search(r"(?<!\w)(?:коммутатор|cisco|ethernet|сетев\w*)(?!\w)", t, re.I)
    ):
        item["brand"] = "nintendo_switch"
        if re.search(r"(?<!\w)oled(?!\w)", t, re.I):
            item["sub_model"] = "oled"
        elif re.search(r"(?<!\w)lite(?!\w)", t, re.I):
            item["sub_model"] = "lite"
        else:
            item["sub_model"] = "base"
        return item

    # Steam Deck
    if re.search(r"(?<!\w)steam\s*deck(?!\w)|стим\s*дек", t, re.I):
        item["brand"] = "steam_deck"
        if re.search(r"(?<!\w)oled(?!\w)", t, re.I):
            item["sub_model"] = "oled"
        elif re.search(r"(?<!\w)lcd(?!\w)", t, re.I):
            item["sub_model"] = "lcd"
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


def _fmt_storage(storage: str | None) -> str:
    if not storage:
        return ""
    return storage.replace("gb", "GB").replace("tb", "TB")


_SUB_DISPLAY = {
    "pro": "Pro", "max": "Max", "plus": "Plus", "ultra": "Ultra", "mini": "mini",
    "fe": "FE", "xl": "XL", "se": "SE", "ti": "Ti", "super": "Super",
    "xt": "XT", "xtx": "XTX", "gt": "GT", "lite": "Lite", "oled": "OLED",
    "lcd": "LCD", "t": "T", "s": "S", "x": "X", "fold": "Fold",
}


def _display_sub(sub: str | None) -> str:
    if not sub or sub == "base":
        return ""
    return " ".join(_SUB_DISPLAY.get(tok, tok.capitalize()) for tok in sub.split())


def _display_chip(chip: str) -> str:
    return " ".join(w.capitalize() for w in chip.split())


def _build_variant_key(parsed: dict[str, Any]) -> str | None:
    """Build a normalized variant group key from parse_item_model output.

    Returns None when the product family is not recognized (caller falls back).
    """
    brand = parsed.get("brand")
    model = parsed.get("model_number")
    sub = parsed.get("sub_model")
    storage = _fmt_storage(parsed.get("storage"))
    size = parsed.get("size")
    features = parsed.get("features") or []

    if not brand:
        return None

    if brand == "apple_iphone":
        if not model:
            return None
        model_disp = model.upper() if model.isalpha() else model
        sub_disp = _display_sub(sub)
        key = f"iPhone {model_disp}" + (f" {sub_disp}" if sub_disp else "")
        return f"{key}, {storage}" if storage else key

    if brand in ("rtx", "gtx", "rx"):
        if not model:
            return None
        sub_disp = _display_sub(sub)
        key = f"{brand.upper()} {model}" + (f" {sub_disp}" if sub_disp else "")
        return f"{key} {storage}" if storage else key

    if brand == "playstation":
        if not model:
            return None
        sub_disp = _display_sub(sub)
        key = f"PlayStation {model}" + (f" {sub_disp}" if sub_disp else "")
        if "digital" in features:
            key += " Digital"
        return key

    if brand == "apple_watch":
        line = {"series": "Series", "ultra": "Ultra", "se": "SE"}.get(sub or "series", "Series")
        key = f"Apple Watch {line}" + (f" {model}" if model else "")
        if size:
            key += f", {size}"
        return key

    if brand == "apple_airpods":
        sub_disp = _display_sub(sub)
        key = "AirPods" + (f" {sub_disp}" if sub_disp else "") + (f" {model}" if model else "")
        return key.strip()

    if brand == "apple_ipad":
        parts = ["iPad"]
        line = {"pro": "Pro", "air": "Air", "mini": "mini"}.get(sub or "")
        if line:
            parts.append(line)
        if size:
            parts.append(size)
        if model:
            parts.append(model.upper() if re.fullmatch(r"m\d", model) else model)
        key = " ".join(parts)
        return f"{key}, {storage}" if storage else key

    if brand == "apple_macbook":
        parts = ["MacBook"]
        line = {"pro": "Pro", "air": "Air"}.get(sub or "")
        if line:
            parts.append(line)
        if model:
            parts.append(_display_chip(model))
        elif size:
            parts.append(size)
        key = " ".join(parts)
        return f"{key}, {storage}" if storage else key

    if brand == "samsung_galaxy":
        if not model:
            return None
        sub_disp = _display_sub(sub)
        key = f"Samsung Galaxy {model.capitalize()}" + (f" {sub_disp}" if sub_disp else "")
        return f"{key}, {storage}" if storage else key

    if brand in ("xiaomi", "redmi", "poco"):
        if not model:
            return None
        disp = {"xiaomi": "Xiaomi", "redmi": "Redmi", "poco": "POCO"}[brand]
        sub_disp = _display_sub(sub)
        key = f"{disp} {model.capitalize()}" + (f" {sub_disp}" if sub_disp else "")
        return f"{key}, {storage}" if storage else key

    if brand == "google_pixel":
        if not model:
            return None
        if sub == "a":
            key = f"Google Pixel {model}a"
        else:
            sub_disp = _display_sub(sub)
            key = f"Google Pixel {model}" + (f" {sub_disp}" if sub_disp else "")
        return f"{key}, {storage}" if storage else key

    if brand == "xbox":
        if sub == "360":
            return "Xbox 360"
        if sub in ("series", "one"):
            key = f"Xbox {sub.capitalize()}" + (f" {model.upper()}" if model else "")
            return key
        return None

    if brand == "nintendo_switch":
        sub_disp = _display_sub(sub)
        return f"Nintendo Switch {sub_disp}".strip()

    if brand == "steam_deck":
        sub_disp = _display_sub(sub)
        key = f"Steam Deck {sub_disp}".strip()
        return f"{key}, {storage}" if storage else key

    if brand == "amd_ryzen":
        if not model or not sub:
            return None
        return f"Ryzen {sub[1:]} {model.upper()}"

    if brand == "intel_core":
        if not model or not sub:
            return None
        return f"Core {sub}-{model.upper()}"

    if brand == "intel_xeon":
        if not model:
            return None
        return f"Xeon {model.upper()}"

    if brand.startswith("ram_ddr"):
        gen = brand.split("ddr")[-1]
        parts = [f"DDR{gen}"]
        if storage:
            parts.append(storage)
        if model:
            parts.append(f"{model}MHz")
        if len(parts) == 1:
            return None
        return " ".join(parts)

    return None


def detect_variant(title: str) -> str | None:
    """Recognized variant key (e.g. 'iPhone 15 Pro, 256GB') or None if family unknown."""
    try:
        parsed = parse_item_model(title or "", "")
        if parsed.get("brand") == "apple_iphone":
            # Guard against the loose bare-number iPhone pattern ("16 клапанов" etc.):
            t_low = (title or "").lower()
            has_kw = bool(re.search(r"(?<!\w)(?:iphone|айфон\w*|i\s*phone)(?!\w)", t_low))
            if not has_kw and parsed.get("sub_model") in (None, "base"):
                return None
        return _build_variant_key(parsed)
    except Exception:
        return None


def extract_goods_group(title: str) -> str:
    key = detect_variant(title)
    if key:
        return key

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

    tokens = [t.lower() for t in re.findall(r"[a-zA-Z0-9]{3,}", query)]
    num_matches = re.findall(r"\d{3,5}", query)
    found_prices: list[int] = []

    for line in description.split("\n"):
        line_clean = line.strip()
        if not line_clean:
            continue
        line_low = line_clean.lower()

        matches_model = False
        if num_matches and any(num in line_low for num in num_matches):
            matches_model = True
        elif tokens and any(tok in line_low for tok in tokens):
            matches_model = True

        if matches_model:
            for p_str in PRICE_IN_TEXT_RE.findall(line_clean):
                clean_num = int(re.sub(r"\s+", "", p_str))
                if clean_num >= 1000:
                    found_prices.append(clean_num)

            for m in re.finditer(r"(?:[-:=—–]\s*|\bот\s+)(\d[\d\s]{2,6})(?!\d)", line_clean):
                val_str = re.sub(r"\s+", "", m.group(1))
                if val_str.isdigit():
                    num = int(val_str)
                    if 1000 <= num <= 500000:
                        found_prices.append(num)

    return found_prices


def classify_item(item: ParsedItem, category_type: str = "goods", search_query: str = "") -> None:
    """Analyze item and attach classification tags."""
    seller_label_low = item.seller_type.lower()
    full_text = f"{item.title} {item.description}".lower()
    title_low = item.title.lower()

    if category_type != "realty" and getattr(item, "variant", None) is None:
        item.variant = detect_variant(item.title)

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

        # 1. Defect & iCloud Lock Detection
        if ICLOUD_LOCK_RE.search(full_text):
            item.is_defect = True
            item.defect_type = "icloud"
            item.tags.append("🔒 Заблокирован iCloud / MDM")
            item.tags.append("⚠️ Дефект (iCloud / блокировка)")
        elif DONOR_DEAD_RE.search(full_text):
            item.is_defect = True
            item.defect_type = "dead"
            item.tags.append("⚡ На запчасти / Не включается")
            item.tags.append("⚠️ Дефект / Неисправность")
        elif SCREEN_DEFECT_RE.search(full_text):
            item.is_defect = True
            item.defect_type = "screen"
            item.tags.append("💔 Разбит экран / Дефект")
        elif DEFECT_RE.search(full_text):
            item.is_defect = True
            item.defect_type = "general"
            item.tags.append("⚠️ Дефект / Неисправность")

        # 2. Exchange & WTB (Trade/Purchase) Detection
        is_exchange_title = bool(re.search(r"\b(?:обмен|обменяю|обменял\s+бы|куплю|ищу|скупка|выкуп|спрос)\b", title_low, re.I))
        is_exchange_desc = bool(re.search(r"\b(?:обмен\s+(?:на|с\s+доплатой)|обменяю\s+(?:на|с\s+доплатой)|обменял\s+бы\s+на|рассмотрю\s+обмен\s+на|только\s+обмен)\b", full_text, re.I))

        if is_exchange_title or (is_exchange_desc and (item.price is None or item.price <= 1000)):
            item.is_exchange_or_wtb = True
            if re.search(r"\b(?:куплю|ищу|скупка|выкуп|спрос)\b", title_low, re.I):
                item.tags.append("🔍 Спрос / Покупка")
            else:
                item.tags.append("🔄 Обмен / Не продажа")

        if not is_acc:
            # Не помечать мусором, если пользователь сам ищет эту запчасть (DDR5, SSD, блок питания)
            q_low = (search_query or "").lower()
            parts_matches = [m.group(0) for m in PARTS_AND_ACCESSORIES_RE.finditer(title_low)]
            mentioned_in_query = any(
                len(mm) >= 3 and mm[:4] in q_low for mm in parts_matches
            ) if q_low else False
            if parts_matches and not mentioned_in_query:
                item.tags.append("🔧 Запчасти / Комплектующие")

        if PC_BUILD_RE.search(item.title.lower()):
            item.tags.append("🖥 ПК в сборе")
        elif LAPTOP_RE.search(item.title.lower()):
            item.tags.append("💻 Ноутбук")

        # Clickbait price detection (< 1000 ₽ for high-tech goods)
        if item.price and item.price < 1000 and not item.is_exchange_or_wtb:
            item.tags.append("⚠️ Подозрительная цена (кликбейт / запчасть)")

        # 3. Check combo / multi-item listing / hardware pool in title
        is_combo = False
        numbered_matches = NUMBERED_PRICE_LIST_RE.findall(item.description)
        if len(numbered_matches) >= 2 or COMBO_KEYWORDS_RE.search(full_text):
            is_combo = True
        elif PLURAL_CATEGORIES_RE.search(item.title.lower()):
            is_combo = True

        # Multi-model hardware in title (e.g. "Xeon E3 1241v3, 1240v2, R7 5700x, R5 5600X")
        cpu_gpu_matches = re.findall(r"\b(?:xeon|ryzen|r[3579]|core|i[3579]|rtx|gtx|rx)\b", title_low)
        has_multi_hardware_title = len(cpu_gpu_matches) >= 2 or len(re.findall(r"\b\d{4}[a-z0-9]*\b", title_low)) >= 3
        if has_multi_hardware_title and search_query:
            item.is_in_desc_or_list = True
            item.is_combo_listing = True
            if not any("Товар в списке" in t for t in item.tags):
                item.tags.append("📋 Товар в списке / описании")

        # Try extracting model-specific prices from description if search_query is available
        desc_prices = extract_desc_prices_for_query(item.description, search_query) if search_query else []

        if desc_prices and item.price:
            real_min_p = min(desc_prices)
            # If listing price is significantly lower than real model price in description (e.g. 2500 vs 13000)
            if item.price < real_min_p * 0.75 or has_multi_hardware_title:
                item.is_combo_listing = True
                item.is_in_desc_or_list = True
                item.real_price_in_desc = real_min_p
                item.tags.append("⚠️ Сборное объявление (в описании список)")
                p_fmt = f"{real_min_p:,}".replace(",", " ")
                ad_fmt = f"{item.price:,}".replace(",", " ")
                item.tags.append(f"⚠️ Реальная цена в описании: ~{p_fmt} ₽ (в заголовке от {ad_fmt} ₽)")
                if not any("Товар в списке" in t for t in item.tags):
                    item.tags.append("📋 Товар в списке / описании")
            elif is_combo:
                item.is_combo_listing = True
                item.tags.append("⚠️ Сборное объявление (в описании список)")
        elif is_combo or item.is_in_desc_or_list:
            item.is_combo_listing = True
            if not any("Товар в списке" in t for t in item.tags) and not any("Сборное объявление" in t for t in item.tags):
                item.tags.append("⚠️ Сборное объявление (в описании список цен)")

    if any("доставка" in b.lower() for b in item.badges):
        item.tags.append("📦 С доставкой")


def is_likely_fake_or_junk(item: ParsedItem, min_price: int | None = None) -> bool:
    """Check if item is junk, parts, accessories, defects, exchanges, or clickbait price."""
    if getattr(item, "is_mismatched_model", False):
        return True
    if getattr(item, "is_accessory", False):
        return True
    if getattr(item, "is_defect", False):
        return True
    if getattr(item, "is_exchange_or_wtb", False):
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
            "🔒 Заблокирован",
            "⚡ На запчасти",
            "💔 Разбит",
            "🔄 Обмен",
            "🔍 Спрос",
            "Подозрительная цена",
            "Сборное объявление",
            "Реальная цена в описании",
            "Аксессуар",
            "Велозапчасть",
            "Автоаксессуар",
        )):
            return True
    return False
