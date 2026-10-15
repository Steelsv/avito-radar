"""Market price estimation and deal detection algorithms.

Calculates median market pricing for items, trims outliers (broken, typos, scams),
and tags underpriced listings.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Sequence

from avito_radar.parsers.item_parser import ParsedItem

OUTLIER_LOW_FACTOR = 0.5
OUTLIER_HIGH_FACTOR = 1.8
MIN_ITEMS_FOR_STATS = 3


@dataclass(frozen=True)
class PriceStats:
    count: int
    median_price: int
    min_price: int
    max_price: int


def calculate_group_stats(prices: Sequence[int]) -> PriceStats | None:
    valid_prices = [p for p in prices if isinstance(p, (int, float)) and p > 0]
    if len(valid_prices) < MIN_ITEMS_FOR_STATS:
        return None

    # Sort prices to detect clusters and distributions
    valid_prices.sort()

    # If high prices exist, detect lower-tail outlier gap (accessories/cheap parts distortion)
    # E.g., for bikes/electronics where prices are 25000-80000, 1000-2500 is an extreme lower outlier
    if len(valid_prices) >= 4:
        upper_half = valid_prices[len(valid_prices) // 2 :]
        upper_median = statistics.median(upper_half)
        if upper_median >= 15000:
            # Cut off items below 25% of upper median (e.g. < 10000 for 40k+ bikes)
            cutoff = max(1000, int(upper_median * 0.25))
            trimmed_low = [p for p in valid_prices if p >= cutoff]
            if len(trimmed_low) >= MIN_ITEMS_FOR_STATS:
                valid_prices = trimmed_low
        elif upper_median >= 5000:
            cutoff = max(500, int(upper_median * 0.20))
            trimmed_low = [p for p in valid_prices if p >= cutoff]
            if len(trimmed_low) >= MIN_ITEMS_FOR_STATS:
                valid_prices = trimmed_low

    max_p = max(valid_prices)
    if max_p >= 10000:
        valid_prices = [p for p in valid_prices if p >= 1000]

    if len(valid_prices) < MIN_ITEMS_FOR_STATS:
        return None

    raw_median = statistics.median(valid_prices)
    # Exclude extreme outliers
    filtered = [
        p for p in valid_prices
        if raw_median * OUTLIER_LOW_FACTOR <= p <= raw_median * OUTLIER_HIGH_FACTOR
    ]
    if len(filtered) < MIN_ITEMS_FOR_STATS:
        filtered = valid_prices

    return PriceStats(
        count=len(filtered),
        median_price=round(statistics.median(filtered)),
        min_price=min(filtered),
        max_price=max(filtered),
    )


def annotate_market_prices(items: list[ParsedItem], group_key_fn: Any = None) -> dict[str, PriceStats]:
    """Calculate market medians and annotate items with market price & diff %."""
    from avito_radar.analysis.classifier import is_likely_fake_or_junk

    groups: dict[str, list[int]] = {}
    all_prices: list[int] = []

    for item in items:
        # Strictly exclude defects and exchanges from market median
        if getattr(item, "is_defect", False) or getattr(item, "is_exchange_or_wtb", False):
            continue

        # If real price in description was identified, use it for genuine median calculation
        real_p = getattr(item, "real_price_in_desc", None)
        if real_p and real_p >= 1000:
            all_prices.append(real_p)
            key = group_key_fn(item) if group_key_fn else "all"
            groups.setdefault(key, []).append(real_p)
            continue

        # Exclude junk, parts, defects, accessories, mismatched models, and combo bait listings
        if getattr(item, "is_accessory", False) or getattr(item, "is_mismatched_model", False) or is_likely_fake_or_junk(item):
            continue

        if not item.price:
            continue

        all_prices.append(item.price)
        key = group_key_fn(item) if group_key_fn else "all"
        groups.setdefault(key, []).append(item.price)

    # Fallback to all valid prices if filter removed everything
    if not all_prices:
        for item in items:
            if getattr(item, "is_defect", False) or getattr(item, "is_exchange_or_wtb", False):
                continue
            if item.price and item.price >= 500 and not getattr(item, "is_mismatched_model", False):
                all_prices.append(item.price)
                key = group_key_fn(item) if group_key_fn else "all"
                groups.setdefault(key, []).append(item.price)

    stats_map: dict[str, PriceStats] = {}
    for key, prices in groups.items():
        stats = calculate_group_stats(prices)
        if stats:
            stats_map[key] = stats

    overall_stats = calculate_group_stats(all_prices)
    if overall_stats:
        stats_map["_overall"] = overall_stats

    for item in items:
        if getattr(item, "is_mismatched_model", False):
            item.market_price = None
            item.market_diff_percent = None
            continue

        if getattr(item, "is_exchange_or_wtb", False):
            item.market_price = None
            item.market_diff_percent = None
            continue

        key = group_key_fn(item) if group_key_fn else "all"
        stats = stats_map.get(key) or stats_map.get("_overall")
        if not stats:
            continue

        # If defective (e.g. iCloud lock):
        # Keep market_price for reference of working item cost, but never calculate false deal diff
        if getattr(item, "is_defect", False):
            item.market_price = stats.median_price
            item.market_diff_percent = None
            continue

        # If combo listing:
        # If real price in desc is known, compare against real price!
        real_p = getattr(item, "real_price_in_desc", None)
        if getattr(item, "is_combo_listing", False):
            item.market_price = stats.median_price
            if real_p and real_p >= 1000:
                diff = (real_p - stats.median_price) / stats.median_price * 100
                item.market_diff_percent = round(diff, 1)
                if diff <= -15 and not getattr(item, "is_accessory", False):
                    item.tags.append(f"🔥 Выгодно ({item.market_diff_percent}%)")
                elif diff >= 25:
                    item.tags.append(f"📈 Выше рынка (+{item.market_diff_percent}%)")
            else:
                # Bait price with unknown model price: do not calculate false diff!
                item.market_diff_percent = None
            continue

        # Normal working standalone item
        if item.price:
            item.market_price = stats.median_price
            diff = (item.price - stats.median_price) / stats.median_price * 100
            item.market_diff_percent = round(diff, 1)

            # Do not tag accessory listings as deals
            if not getattr(item, "is_accessory", False):
                if diff <= -50:
                    item.tags.append(f"🔥 Супер-цена / Проверить лот ({item.market_diff_percent}%)")
                elif diff <= -15:
                    item.tags.append(f"🔥 Выгодно ({item.market_diff_percent}%)")
                elif diff >= 25:
                    item.tags.append(f"📈 Выше рынка (+{item.market_diff_percent}%)")
            else:
                if diff >= 25:
                    item.tags.append(f"📈 Выше рынка (+{item.market_diff_percent}%)")

    return stats_map
