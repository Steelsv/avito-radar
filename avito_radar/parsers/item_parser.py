"""Parser for Avito item objects and detailed ad pages.

Extracts structured data from items API and inspects ad pages
for view counts (total vs today) to filter out re-published old ads.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from avito_radar.core.client import AvitoClient, BASE_URL

MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

DATE_MARKER = re.compile(r'data-marker="item-view/item-date"[^>]*>(.*?)</span>', re.S)
TOTAL_VIEWS = re.compile(r'data-marker="item-view/total-views"[^>]*>(.*?)</span>', re.S)
TODAY_VIEWS = re.compile(r'data-marker="item-view/today-views"[^>]*>(.*?)</span>', re.S)
CLOSED_ITEMS_PATTERN = re.compile(r"(\d+)\s+заверш", re.I)


@dataclass
class ParsedItem:
    id: int
    title: str
    price: int | None
    price_formatted: str
    url: str
    address: str
    metro: str
    city: str
    published_text: str
    sort_timestamp: datetime | None
    seller_name: str
    seller_type: str
    seller_rating: float | None
    closed_listings: int | None
    badges: tuple[str, ...]
    images: list[str]
    description: str
    phone_available: bool

    # Enriched on inspection
    total_views: int | None = None
    today_views: int | None = None
    is_republished: bool = False
    market_price: int | None = None
    market_diff_percent: float | None = None
    tags: list[str] = field(default_factory=list)


def format_price(value: int | None) -> str:
    if value is None:
        return "Цена не указана"
    return f"{value:,} ₽".replace(",", " ")


def _extract_iva_payloads(item: dict[str, Any], step: str) -> list[dict[str, Any]]:
    steps = (item.get("iva") or {}).get(step) or []
    return [e.get("payload") or {} for e in steps if isinstance(e, dict)]


def parse_catalog_item(item: dict[str, Any]) -> ParsedItem:
    item_id = int(item["id"])
    title = str(item.get("title") or "").strip()

    price_val = (item.get("priceDetailed") or {}).get("value")
    price = int(price_val) if isinstance(price_val, (int, float)) else None

    url_path = str(item.get("urlPath") or "")
    url = BASE_URL + urlsplit(url_path).path

    city = url_path.strip("/").split("/")[0] if url_path else ""

    geo = item.get("geo") or {}
    coords = item.get("coords") or {}
    address = str(coords.get("address_user") or geo.get("formattedAddress") or "").strip()

    metro = ""
    refs = geo.get("geoReferences") or []
    if refs and isinstance(refs[0], dict):
        metro = f"{refs[0].get('content', '')}{refs[0].get('after', '')}".strip()

    # Published text
    published = ""
    for p in _extract_iva_payloads(item, "DateInfoStep"):
        rel = p.get("relative") or p.get("absolute")
        if rel:
            published = str(rel).strip()
            break

    # Timestamp
    stamp = item.get("sortTimeStamp")
    sort_ts = datetime.fromtimestamp(stamp / 1000) if isinstance(stamp, (int, float)) and stamp > 0 else None

    # Seller info
    seller_label_parts = [
        str(p["value"]).strip()
        for p in _extract_iva_payloads(item, "SecondLineStep")
        if p.get("value")
    ]
    seller_label = ", ".join(seller_label_parts)

    seller_name = ""
    seller_type = "частное лицо"
    for part in seller_label_parts:
        low = part.lower()
        if any(w in low for w in ("агентство", "компания", "застройщик", "магазин")):
            seller_type = part
        else:
            seller_name = part

    # Rating
    rating_val = (item.get("rating") or {}).get("value")
    seller_rating = float(rating_val) if isinstance(rating_val, (int, float)) else None

    # Closed listings
    closed_text = str(item.get("closedItemsText") or "")
    closed_match = CLOSED_ITEMS_PATTERN.search(closed_text)
    closed_listings = int(closed_match.group(1)) if closed_match else (0 if "нет" in closed_text.lower() else None)

    # Badges
    badges = tuple(
        str(badge.get("title"))
        for p in _extract_iva_payloads(item, "BadgeBarStep")
        for badge in p.get("badges") or []
        if isinstance(badge, dict) and badge.get("title")
    )

    # Images
    images: list[str] = []
    for img in item.get("images") or []:
        if isinstance(img, dict):
            # Prefer largest
            urls = [v for k, v in img.items() if isinstance(v, str) and v.startswith("http")]
            if urls:
                images.append(urls[-1])

    description = str(item.get("description") or "").strip()
    phone_available = bool((item.get("contacts") or {}).get("phone"))

    return ParsedItem(
        id=item_id,
        title=title,
        price=price,
        price_formatted=format_price(price),
        url=url,
        address=address,
        metro=metro,
        city=city,
        published_text=published,
        sort_timestamp=sort_ts,
        seller_name=seller_name or seller_type,
        seller_type=seller_type,
        seller_rating=seller_rating,
        closed_listings=closed_listings,
        badges=badges,
        images=images,
        description=description,
        phone_available=phone_available,
    )


def _clean_html(fragment: str) -> str:
    return re.sub(r"<[^>]+>|·", " ", fragment).replace("\xa0", " ").strip()


def _parse_views(html: str) -> tuple[int | None, int | None]:
    total_m = TOTAL_VIEWS.search(html)
    today_m = TODAY_VIEWS.search(html)

    def to_num(m: Any) -> int | None:
        if not m:
            return None
        digits = re.sub(r"\D", "", _clean_html(m.group(1)))
        return int(digits) if digits else None

    total = to_num(total_m)
    today = to_num(today_m)
    return total, today


def inspect_item_views(
    client: AvitoClient, item_url: str, catalog_url: str
) -> tuple[int | None, int | None, bool]:
    """Fetch item page and return (total_views, today_views, is_republished).

    If earlier views (total - today) exceed threshold, ad is an old republished listing.
    """
    html = client.get_html(item_url, catalog_url=catalog_url)
    if not html:
        return None, None, False

    total, today = _parse_views(html)
    if total is None:
        return None, None, False

    earlier = total - (today or 0)
    now = datetime.now()
    threshold = 100 if now.hour < 3 else 15
    is_republished = earlier > threshold

    return total, today, is_republished
