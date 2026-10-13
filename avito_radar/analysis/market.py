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

    # If high prices exist, ignore clickbaits / junk under 1000 ₽
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
        if not item.price:
            continue

        # If real price in description was identified, use it for genuine median calculation
        real_p = getattr(item, "real_price_in_desc", None)
        if real_p and real_p >= 1000:
            all_prices.append(real_p)
            key = group_key_fn(item) if group_key_fn else "all"
            groups.setdefault(key, []).append(real_p)
            continue

        # Exclude junk, parts, defects, accessories, and combo bait listings
        if is_likely_fake_or_junk(item):
            continue

        all_prices.append(item.price)
        key = group_key_fn(item) if group_key_fn else "all"
        groups.setdefault(key, []).append(item.price)

    # Fallback to all valid prices if filter removed everything
    if not all_prices:
        for item in items:
            if item.price and item.price > 0:
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
        key = group_key_fn(item) if group_key_fn else "all"
        stats = stats_map.get(key) or stats_map.get("_overall")
        if stats and item.price:
            item.market_price = stats.median_price
            diff = (item.price - stats.median_price) / stats.median_price * 100
            item.market_diff_percent = round(diff, 1)

            # Do not tag combo / bait listings as deals
            if not getattr(item, "is_combo_listing", False):
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
