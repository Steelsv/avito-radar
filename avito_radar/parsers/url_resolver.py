"""Avito search URL parser and parameter resolver.

Converts full Avito web URLs into exact API parameters:
- Decodes Base64/zigzag varint filter blobs (`f=ASg...`) into `params[<id>]=<val>`.
- Transliterates city slugs and resolves location IDs via Avito suggestions.
- Discovers categories and active filters dynamically.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit

from avito_radar.core.client import AvitoClient, BASE_URL

LOCATION_SUGGEST_URL = f"{BASE_URL}/web/1/slocations"
ITEMS_URL = f"{BASE_URL}/web/1/js/items"
TREE_PROBE_CATEGORY = "84"
MAX_FILTER_ROUNDS = 4

REALTY_CATEGORY_IDS = {"23", "24", "25", "26", "42", "85", "86"}
ELECTRONICS_CATEGORY_IDS = {"84", "99", "101", "102", "103"}
AUTO_CATEGORY_IDS = {"9", "14", "15", "16", "17", "18"}

KNOWN_CATEGORIES = {
    "kvartiry": "24",
    "komnaty": "23",
    "doma_dachi_kottedzhi": "25",
    "zemelnye_uchastki": "26",
    "garazhi_i_mashinomesta": "85",
    "kommercheskaya_nedvizhimost": "42",
    "nedvizhimost_za_rubezhom": "86",
    "avtomobili": "9",
    "telefony": "84",
    "noutbuki": "99",
}

PASSTHROUGH_QUERY = {
    "q", "user", "pmin", "pmax", "d", "radius", "bt",
    "footWalkingMetro", "localPriority", "s",
}
MULTI_VALUE_TYPES = {"multiselect", "sectionedMultiselect", "checkboxGroup"}

CYR_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya", " ": "_", "-": "-",
}
LAT_TO_CYR = (
    ("sch", "щ"), ("zh", "ж"), ("ch", "ч"), ("sh", "ш"), ("ts", "ц"), ("yu", "ю"),
    ("ya", "я"), ("yo", "йо"), ("a", "а"), ("b", "б"), ("v", "в"), ("g", "г"),
    ("d", "д"), ("e", "е"), ("z", "з"), ("i", "и"), ("y", "й"), ("k", "к"), ("l", "л"),
    ("m", "м"), ("n", "н"), ("o", "о"), ("p", "п"), ("r", "р"), ("s", "с"), ("t", "т"),
    ("u", "у"), ("f", "ф"), ("h", "х"), ("c", "ц"),
)


class ResolverError(ValueError):
    """Raised when an Avito link cannot be parsed."""


def transliterate(name: str) -> str:
    return "".join(CYR_TO_LAT.get(char, char) for char in name.lower())


def slug_prefix_in_cyrillic(slug: str, letters: int) -> str:
    word = re.split(r"[_-]", slug)[0]
    result = ""
    pos = 0
    while pos < len(word) and len(result) < letters:
        for latin, cyrillic in LAT_TO_CYR:
            if word.startswith(latin, pos):
                result += cyrillic
                pos += len(latin)
                break
        else:
            pos += 1
    return result[:letters]


def decode_filter_blob(blob: str) -> list[tuple[int, int]]:
    """Decode Avito varint zigzag attribute/value pairs from base64 blob."""
    padded = blob.replace("~", "/").replace("-", "+").replace("_", "/")
    padded += "=" * (-len(padded) % 4)
    try:
        data = base64.b64decode(padded)
    except ValueError as exc:
        raise ResolverError(f"Ошибка декодирования фильтров в ссылке: {exc}") from None

    numbers = []
    pos = 0
    while pos < len(data):
        val = shift = 0
        while True:
            if pos >= len(data):
                raise ResolverError("Фильтры в ссылке повреждены или оборваны")
            byte = data[pos]
            pos += 1
            val |= (byte & 0x7F) << shift
            shift += 7
            if not byte & 0x80:
                break
        numbers.append(val)

    if len(numbers) < 8 or numbers[7] != 68:
        raise ResolverError("Неизвестный формат фильтров в ссылке")

    count = numbers[6]
    raw = numbers[8 : 8 + 2 * count]
    if len(raw) != 2 * count:
        raise ResolverError("Число фильтров в ссылке не совпадает с заголовком")

    return [(raw[i] // 2, raw[i + 1] // 2) for i in range(0, len(raw), 2)]


@dataclass
class ParsedLink:
    url: str
    city_slug: str
    category_slug: str
    blob: str
    query: dict[str, str]
    path_slugs: tuple[str, ...] = ()


def parse_link(url: str) -> ParsedLink:
    parts = urlsplit(url.strip())
    if not parts.netloc.endswith("avito.ru"):
        raise ResolverError("Указанный URL не относится к avito.ru")

    segments = [s for s in parts.path.split("/") if s]
    if not segments:
        raise ResolverError("В ссылке нет города (требуется страница каталога, напр. avito.ru/moskva/...)")

    query = dict(parse_qsl(parts.query))
    blob = query.get("f", "")
    if not blob and len(segments) > 1:
        tail = segments[-1].rsplit("-", 1)
        if len(tail) == 2 and tail[1].startswith("ASg"):
            blob = tail[1]

    category_slug = segments[1].split("-ASg")[0] if len(segments) > 1 else ""
    if re.fullmatch(r".*_\d{6,}", segments[-1]):
        raise ResolverError("Это ссылка на отдельное объявление, а требуется ссылка на каталог/поиск")

    return ParsedLink(
        url=url.strip(),
        city_slug=segments[0],
        category_slug=category_slug,
        blob=blob,
        query=query,
        path_slugs=tuple(s.split("-ASg")[0] for s in segments[1:]),
    )


def resolve_location(client: AvitoClient, slug: str, cache: dict[str, Any], *, referer: str) -> tuple[int, str]:
    if slug in cache:
        return int(cache[slug]["id"]), cache[slug]["name"]

    for letters in (5, 4, 3):
        prefix = slug_prefix_in_cyrillic(slug, letters)
        if not prefix:
            continue
        payload = client.get_json(
            f"{LOCATION_SUGGEST_URL}?limit=30&q={quote(prefix)}",
            catalog_url=referer,
        )
        locations = (payload.get("result") or {}).get("locations") or []
        for loc in locations:
            name = (loc.get("names") or {}).get("1") or ""
            if transliterate(name) == slug:
                cache[slug] = {"id": loc["id"], "name": name}
                return int(loc["id"]), name

    raise ResolverError(f"Не удалось определить город «{slug}». Укажите его вручную.")


def resolve_category(client: AvitoClient, slug: str, location_id: int, cache: dict[str, Any], *, referer: str) -> str:
    if slug in KNOWN_CATEGORIES:
        return KNOWN_CATEGORIES[slug]

    tree = cache.setdefault("categories", {})
    if slug not in tree:
        payload = client.get_json(
            f"{ITEMS_URL}?categoryId={TREE_PROBE_CATEGORY}&locationId={location_id}&p=1&updateListOnly=true",
            catalog_url=referer,
        )
        nodes = list((payload.get("rubricators") or {}).get("categoryTreeTop") or [])
        while nodes:
            node = nodes.pop()
            nodes.extend(node.get("subs") or [])
            node_url = node.get("url") or ""
            segs = [s for s in urlsplit(node_url).path.split("/") if s]
            if len(segs) >= 2 and node.get("categoryId"):
                tree.setdefault(segs[1].split("-ASg")[0], str(node["categoryId"]))

    if slug not in tree:
        raise ResolverError(f"Категория «{slug}» не найдена в рубрикаторе Авито")

    return tree[slug]


@dataclass
class FilterDef:
    id: str
    title: str
    type: str
    values: dict[str, str] = field(default_factory=dict)


def extract_filters_from_payload(payload: dict[str, Any]) -> dict[str, FilterDef]:
    filters: dict[str, FilterDef] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("id"), str) and "type" in node and node["id"] not in filters:
                vals = {
                    str(v.get("value")): str(v.get("name"))
                    for v in node.get("values") or []
                    if isinstance(v, dict)
                }
                filters[node["id"]] = FilterDef(
                    id=node["id"],
                    title=node.get("defaultTitle") or node.get("title") or node["id"],
                    type=str(node.get("type")),
                    values=vals,
                )
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(payload.get("filtersV2"))
    return filters


def map_filter_params(
    pairs: list[tuple[int, int]],
    filters: dict[str, FilterDef],
    slugs: tuple[str, ...],
) -> tuple[dict[str, str], list[str]]:
    by_val = {val: f for f in filters.values() for val in f.values}
    chosen: dict[str, list[str]] = {}
    warnings: list[str] = []

    for attr, val in pairs:
        direct = filters.get(f"params[{attr}]")
        if direct and (not direct.values or str(val) in direct.values):
            target, chosen_val = direct, str(val)
        elif str(val) in by_val:
            target, chosen_val = by_val[str(val)], str(val)
        elif direct:
            # Match by slug
            matched = None
            for v, name in direct.values.items():
                if transliterate(name) in slugs:
                    matched = v
                    break
            if matched:
                target, chosen_val = direct, matched
            else:
                warnings.append(f"Значение фильтра «{direct.title}» не распознано точно")
                continue
        else:
            target = FilterDef(id=f"params[{attr}]", title=f"params[{attr}]", type="select")
            chosen_val = str(val)

        chosen.setdefault(target.id, []).append(chosen_val)

    params: dict[str, str] = {}
    for fid, values in chosen.items():
        kind = filters[fid].type if fid in filters else "select"
        if kind in MULTI_VALUE_TYPES or len(values) > 1:
            for i, v in enumerate(values):
                params[f"{fid}[{i}]"] = v
        else:
            params[fid] = values[0]

    return params, warnings


def describe_active_filters(payload: dict[str, Any]) -> list[str]:
    active = []
    for f in extract_filters_from_payload(payload).values():
        curr = None

        def find(node: Any) -> None:
            nonlocal curr
            if isinstance(node, dict):
                if node.get("id") == f.id and "currentValue" in node:
                    curr = node["currentValue"]
                    return
                for val in node.values():
                    find(val)
            elif isinstance(node, list):
                for val in node:
                    find(val)

        find(payload.get("filtersV2"))
        if curr in (None, "", [], False, 0, "0", "default", "101") or curr == {"from": None, "to": None}:
            continue
        if f.id in ("categoryId", "locationId"):
            continue

        if isinstance(curr, dict):
            disp = f"от {curr.get('from') or '…'} до {curr.get('to') or '…'}"
        elif isinstance(curr, list):
            disp = ", ".join(f.values.get(str(x), str(x)) for x in curr)
        else:
            disp = f.values.get(str(curr), str(curr))

        active.append(f"{f.title}: {disp}")
    return active


@dataclass
class SearchConfig:
    name: str
    title: str
    category_type: str  # realty, goods, auto, general
    catalog_url: str
    city: str
    params: dict[str, str]
    total_count: int
    active_filters: list[str]
    sample_titles: list[str]
    warnings: list[str]


def resolve_url(
    client: AvitoClient,
    url: str,
    *,
    locations_cache: dict[str, Any] | None = None,
    city_override: str | None = None,
) -> SearchConfig:
    cache = locations_cache if locations_cache is not None else {}
    link = parse_link(url)
    referer = link.url

    cities_cache = cache.setdefault("cities", {})
    loc_id, city_name = resolve_location(client, link.city_slug, cities_cache, referer=referer)

    params: dict[str, str] = {"locationId": str(loc_id)}
    for k, v in link.query.items():
        if k in PASSTHROUGH_QUERY or k.startswith("params["):
            params[k] = v

    cat_id = None
    if link.category_slug:
        cat_id = resolve_category(client, link.category_slug, loc_id, cache, referer=referer)
        params["categoryId"] = cat_id

    warnings: list[str] = []
    payload: dict[str, Any] | None = None

    if link.blob:
        pairs = decode_filter_blob(link.blob)
        extra: dict[str, str] = {}
        for _ in range(MAX_FILTER_ROUNDS):
            test_query = [(k, str(v)) for k, v in {**params, **extra}.items()] + [("p", "1"), ("updateListOnly", "true")]
            payload = client.get_json(f"{ITEMS_URL}?{urlencode(test_query)}", catalog_url=referer)
            available = extract_filters_from_payload(payload)
            mapped, warns = map_filter_params(pairs, available, link.path_slugs)
            warnings = warns
            if mapped == extra:
                break
            extra = mapped
            payload = None
        params.update(extra)

    if payload is None:
        query_items = [(k, str(v)) for k, v in params.items()] + [("p", "1"), ("updateListOnly", "true")]
        payload = client.get_json(f"{ITEMS_URL}?{urlencode(query_items)}", catalog_url=referer)

    catalog = payload.get("catalog") if isinstance(payload.get("catalog"), dict) else {}
    items = catalog.get("items") or []
    total = payload.get("totalCount") if isinstance(payload.get("totalCount"), int) else len(items)

    seo = payload.get("seo") or {}
    title = str(seo.get("h1") or seo.get("title") or link.url).split("|")[0].strip()

    if cat_id in REALTY_CATEGORY_IDS:
        cat_type = "realty"
    elif cat_id in ELECTRONICS_CATEGORY_IDS:
        cat_type = "electronics"
    elif cat_id in AUTO_CATEGORY_IDS:
        cat_type = "auto"
    else:
        cat_type = "goods"

    # Default name from slug
    clean_tail = link.category_slug or ""
    if not clean_tail and link.query.get("q"):
        clean_tail = transliterate(link.query["q"])
    if not clean_tail:
        clean_tail = "search"
    clean_city = transliterate(city_name).replace(" ", "_")
    name = f"{clean_tail}_{clean_city}".lower()
    name = re.sub(r"[^a-z0-9_-]+", "_", name).strip("_")

    return SearchConfig(
        name=name,
        title=title,
        category_type=cat_type,
        catalog_url=link.url,
        city=city_name,
        params=params,
        total_count=total,
        active_filters=describe_active_filters(payload),
        sample_titles=[str(it.get("title") or "") for it in items[:5] if isinstance(it, dict)],
        warnings=warnings,
    )
