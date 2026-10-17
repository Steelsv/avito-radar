"""Global market price database keyed by product variant group.

Local per-search medians are unreliable when a search yields only a couple of
listings for a concrete variant (e.g. a generic "iphone" search with 2 listings
of "iPhone 15 Pro, 256GB"). This module accumulates variant-level price stats
across ALL searches in data/market_db.json and backfills items whose local
group stats are too weak.

Format:
    {variant_key: {"median": int, "count": int, "min": int, "max": int, "updated_at": iso}}
"""

from __future__ import annotations

import logging
import statistics
import threading
from datetime import datetime, timedelta
from typing import Any, Iterable

from avito_radar.analysis.classifier import extract_broad_group, extract_goods_group, is_likely_fake_or_junk
from avito_radar.analysis.market import (
    RECOMMENDED_BUY_FACTOR,
    PriceStats,
    apply_deal_fields,
    calculate_group_stats,
)
from avito_radar.parsers.item_parser import ParsedItem
from avito_radar.storage.db import DATA_DIR, load_json, save_json

logger = logging.getLogger(__name__)

MARKET_DB_PATH = DATA_DIR / "market_db.json"

SMOOTHING_OLD = 0.7
SMOOTHING_NEW = 0.3
MAX_COUNT = 500
STALE_DAYS = 30
MIN_LOCAL_SAMPLES = 3

_DB_LOCK = threading.RLock()


def _valid_price(item: ParsedItem) -> int | None:
    """Price of a listing that is allowed to feed the market median.

    Mirrors the per-item selection logic of annotate_market_prices.
    """
    if getattr(item, "is_defect", False) or getattr(item, "is_exchange_or_wtb", False):
        return None

    real_p = getattr(item, "real_price_in_desc", None)
    if real_p and real_p >= 1000:
        return real_p

    if getattr(item, "is_accessory", False) or getattr(item, "is_mismatched_model", False):
        return None
    if is_likely_fake_or_junk(item):
        return None
    if not item.price:
        return None
    return item.price


def _is_stale(rec: dict[str, Any], now: datetime | None = None) -> bool:
    updated = rec.get("updated_at")
    if not updated:
        return True
    try:
        ts = datetime.fromisoformat(str(updated))
    except (ValueError, TypeError):
        return True
    return ts < (now or datetime.now()) - timedelta(days=STALE_DAYS)


def _prune(db: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now()
    return {k: v for k, v in db.items() if isinstance(v, dict) and not _is_stale(v, now)}


def update_market_db(items: Iterable[ParsedItem], category_type: str = "goods") -> dict[str, dict[str, Any]]:
    """Merge valid listing prices of this batch into the global variant DB.

    Returns the dict of updated records {variant_key: record}.
    """
    if category_type != "goods":
        return {}

    groups: dict[str, list[int]] = {}
    for item in items:
        price = _valid_price(item)
        if not price:
            continue
        key = extract_goods_group(item.title)
        if not key:
            continue
        groups.setdefault(key, []).append(price)

    if not groups:
        return {}

    updated: dict[str, dict[str, Any]] = {}
    now_iso = datetime.now().isoformat()
    with _DB_LOCK:
        db = _prune(load_json(MARKET_DB_PATH))
        for key, prices in groups.items():
            stats = calculate_group_stats(prices)
            if stats:
                batch_median = stats.median_price
                batch_min = stats.min_price
                batch_max = stats.max_price
                batch_count = stats.count
            else:
                batch_median = round(statistics.median(prices))
                batch_min = min(prices)
                batch_max = max(prices)
                batch_count = len(prices)

            old = db.get(key)
            if isinstance(old, dict) and isinstance(old.get("median"), (int, float)) and old["median"] > 0:
                new_median = round(SMOOTHING_OLD * float(old["median"]) + SMOOTHING_NEW * float(batch_median))
                new_count = min(int(old.get("count") or 0) + batch_count, MAX_COUNT)
                new_min = min(int(old.get("min") or batch_min), batch_min)
                new_max = max(int(old.get("max") or batch_max), batch_max)
            else:
                new_median = batch_median
                new_count = min(batch_count, MAX_COUNT)
                new_min = batch_min
                new_max = batch_max

            rec = {
                "median": int(new_median),
                "count": int(new_count),
                "min": int(new_min),
                "max": int(new_max),
                "updated_at": now_iso,
            }
            db[key] = rec
            updated[key] = rec

        # Также копим широкую товарную группу (без узкой комплектации):
        # узкий вариант при сотнях лотов редко набирает 3 образца
        groups2: dict[str, list[int]] = {}
        for item in items:
            price = _valid_price(item)
            if not price:
                continue
            broad = extract_broad_group(item.title)
            if broad and broad != extract_goods_group(item.title):
                groups2.setdefault(broad, []).append(price)
        for key, prices in groups2.items():
            stats = calculate_group_stats(prices)
            if not stats:
                continue
            old = db.get(key)
            if isinstance(old, dict) and isinstance(old.get("median"), (int, float)) and old["median"] > 0:
                new_median = round(SMOOTHING_OLD * float(old["median"]) + SMOOTHING_NEW * float(stats.median_price))
                new_count = min(int(old.get("count") or 0) + stats.count, MAX_COUNT)
                new_min = min(int(old.get("min") or stats.min_price), stats.min_price)
                new_max = max(int(old.get("max") or stats.max_price), stats.max_price)
            else:
                new_median = stats.median_price
                new_count = min(stats.count, MAX_COUNT)
                new_min = stats.min_price
                new_max = stats.max_price
            db[key] = {
                "median": int(new_median),
                "count": int(new_count),
                "min": int(new_min),
                "max": int(new_max),
                "updated_at": now_iso,
            }
        save_json(MARKET_DB_PATH, db)

    return updated


def get_variant_stats(variant_key: str | None) -> dict[str, Any] | None:
    """Fresh global stats for a variant key, or None (missing/stale)."""
    if not variant_key:
        return None
    with _DB_LOCK:
        db = load_json(MARKET_DB_PATH)
    rec = db.get(variant_key)
    if not isinstance(rec, dict) or not rec.get("median"):
        return None
    if _is_stale(rec):
        return None
    return rec


def get_group_stats(group_key: str | None) -> dict[str, Any] | None:
    """Fresh global stats for a broad goods group key, or None (missing/stale)."""
    if not group_key:
        return None
    with _DB_LOCK:
        db = load_json(MARKET_DB_PATH)
    rec = db.get(group_key)
    if not isinstance(rec, dict) or not rec.get("median"):
        return None
    if _is_stale(rec):
        return None
    return rec


def _apply_median_to_item(item: ParsedItem, median: int, count: int, gmin: int) -> None:
    """Fill market/deal fields on the item from a given median (shared backfill core)."""
    item.market_price = median
    item.market_samples = count
    item.market_min_price = gmin if gmin > 0 else None
    item.market_is_global = True

    # Market-based deal tags come from this median now: drop local ones
    item.tags = [t for t in item.tags if not t.startswith(("🔥", "📈"))]

    if getattr(item, "is_defect", False):
        item.market_diff_percent = None
        item.market_median = int(median)
        item.recommended_buy = max(0, round(median * RECOMMENDED_BUY_FACTOR / 100) * 100)
        item.profit_abs = None
        item.profit_pct = None
        item.deal_badge = None
        return

    price = getattr(item, "real_price_in_desc", None) or item.price
    if not price:
        item.market_median = int(median)
        item.recommended_buy = max(0, round(median * RECOMMENDED_BUY_FACTOR / 100) * 100)
        return

    diff = (price - median) / median * 100
    item.market_diff_percent = round(diff, 1)
    if getattr(item, "is_combo_listing", False) and not getattr(item, "real_price_in_desc", None):
        item.market_diff_percent = None
        item.market_median = int(median)
        item.recommended_buy = max(0, round(median * RECOMMENDED_BUY_FACTOR / 100) * 100)
        return

    apply_deal_fields(item, median, price)

    if not getattr(item, "is_accessory", False):
        if diff <= -50:
            item.tags.append(f"🔥 Супер-цена / Проверить лот ({item.market_diff_percent}%)")
        elif diff <= -15:
            item.tags.append(f"🔥 Выгодно ({item.market_diff_percent}%)")
        elif diff >= 25:
            item.tags.append(f"📈 Выше рынка (+{item.market_diff_percent}%)")
    elif diff >= 25:
        item.tags.append(f"📈 Выше рынка (+{item.market_diff_percent}%)")


def apply_global_market(item: ParsedItem, local_stats: PriceStats | None = None) -> bool:
    """Backfill item market price from the global DB when local data is weak.

    Applied when the local per-search variant group has < MIN_LOCAL_SAMPLES
    listings or the item got no market_price at all. Returns True if the
    global median was applied.
    """
    variant = getattr(item, "variant", None)
    if not variant:
        return False
    if getattr(item, "is_mismatched_model", False) or getattr(item, "is_exchange_or_wtb", False):
        return False
    if (
        item.market_price is not None
        and local_stats is not None
        and getattr(local_stats, "count", 0) >= MIN_LOCAL_SAMPLES
    ):
        return False

    gstats = get_variant_stats(variant)
    if not gstats:
        gstats = get_group_stats(extract_broad_group(item.title)) or None
    if not gstats:
        return False
    try:
        median = int(gstats["median"])
    except (KeyError, TypeError, ValueError):
        return False
    if median <= 0:
        return False

    try:
        gmin = int(gstats.get("min") or 0)
    except (TypeError, ValueError):
        gmin = 0
    _apply_median_to_item(item, median, int(gstats.get("count") or 0), gmin)
    if getattr(item, "market_source", None) is None:
        item.market_source = "global_variant"
    return True


def apply_market_cascade(
    item: ParsedItem,
    local_variant_stats: PriceStats | None = None,
    local_group_stats: PriceStats | None = None,
) -> str | None:
    """Cascading market price source for an item after local annotation.

    Level 1: local variant group (already applied by annotate_market_prices)
    Level 2: local broad goods group (>= MIN_LOCAL_SAMPLES)
    Level 3: global market_db by variant
    Level 4: global market_db by broad goods group
    Returns the applied market_source or None.
    """
    if getattr(item, "is_mismatched_model", False) or getattr(item, "is_exchange_or_wtb", False):
        return None

    if item.market_price is not None and local_variant_stats is not None and local_variant_stats.count >= MIN_LOCAL_SAMPLES:
        item.market_source = "local_variant"
        return "local_variant"

    # Level 2: local broad group (more specific than the mixed "_overall" fallback)
    if (
        local_group_stats is not None
        and local_group_stats.count >= MIN_LOCAL_SAMPLES
        and (local_variant_stats is None or local_variant_stats.count < MIN_LOCAL_SAMPLES)
    ):
        _apply_median_to_item(
            item,
            int(local_group_stats.median_price),
            int(local_group_stats.count),
            int(local_group_stats.min_price),
        )
        item.market_is_global = False
        item.market_source = "local_group"
        return "local_group"

    # Level 3/4: global db by variant, then by broad group
    for key, source in (
        (getattr(item, "variant", None), "global_variant"),
        (extract_broad_group(item.title), "global_group"),
    ):
        if not key:
            continue
        gstats = get_variant_stats(key) or get_group_stats(key)
        if not gstats:
            continue
        try:
            median = int(gstats["median"])
        except (KeyError, TypeError, ValueError):
            continue
        if median <= 0:
            continue
        try:
            gmin = int(gstats.get("min") or 0)
        except (TypeError, ValueError):
            gmin = 0
        _apply_median_to_item(item, median, int(gstats.get("count") or 0), gmin)
        item.market_source = source
        return source

    return None
