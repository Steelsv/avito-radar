"""Market price estimation and deal detection algorithms.

Calculates median market pricing for items, trims outliers (broken, typos, scams),
and tags underpriced listings.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any, Sequence

from avito_radar.parsers.item_parser import ParsedItem

OUTLIER_LOW_FACTOR = 0.5
OUTLIER_HIGH_FACTOR = 1.8
MIN_ITEMS_FOR_STATS = 3

RECOMMENDED_BUY_FACTOR = 0.88
DEAL_BADGE_THRESHOLD_PCT = -10.0


def format_money(value: int) -> str:
    """Форматирование суммы с пробелом-разделителем тысяч."""
    return f"{value:,}".replace(",", " ")


def compute_deal_fields(median: int, price: int | None) -> dict[str, Any]:
    """Profit analytics for a lot against its market median."""
    fields: dict[str, Any] = {
        "market_median": int(median),
        "recommended_buy": max(0, round(median * RECOMMENDED_BUY_FACTOR / 100) * 100),
        "profit_abs": None,
        "profit_pct": None,
        "deal_badge": None,
    }
    if not price or price <= 0 or median <= 0:
        return fields
    profit_abs = int(median - price)
    profit_pct = round((median - price) / median * 100, 1)
    fields["profit_abs"] = profit_abs
    fields["profit_pct"] = profit_pct
    if profit_pct >= abs(DEAL_BADGE_THRESHOLD_PCT):
        fields["deal_badge"] = f"Ниже рынка на {format_money(profit_abs)} руб. (-{profit_pct:g}%)"
    return fields


def apply_deal_fields(item: Any, median: int, price: int | None) -> None:
    for key, value in compute_deal_fields(median, price).items():
        setattr(item, key, value)


def clear_deal_fields(item: Any) -> None:
    item.market_median = None
    item.recommended_buy = None
    item.profit_abs = None
    item.profit_pct = None
    item.deal_badge = None
    item.market_min_price = None
    item.market_source = None
    item.overpriced = False


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


def collect_price_groups(items: list[ParsedItem], group_key_fn: Any) -> dict[str, PriceStats]:
    """Price stats per group key over the same valid prices annotate_market_prices uses."""
    from avito_radar.analysis.classifier import is_likely_fake_or_junk

    groups: dict[str, list[int]] = {}
    for item in items:
        if getattr(item, "is_defect", False) or getattr(item, "is_exchange_or_wtb", False):
            continue
        real_p = getattr(item, "real_price_in_desc", None)
        if real_p and real_p >= 1000:
            price = real_p
        else:
            if getattr(item, "is_accessory", False) or getattr(item, "is_mismatched_model", False):
                continue
            if is_likely_fake_or_junk(item):
                continue
            if not item.price:
                continue
            price = item.price
        groups.setdefault(group_key_fn(item), []).append(price)

    stats_map: dict[str, PriceStats] = {}
    for key, prices in groups.items():
        stats = calculate_group_stats(prices)
        if stats:
            stats_map[key] = stats
    return stats_map


def is_overpriced(item: Any, drop_overpriced_pct: float = 50) -> bool:
    """True when the lot costs more than market*(1+pct/100) and market is known."""
    market = getattr(item, "market_price", None)
    if not market or market <= 0:
        return False
    price = getattr(item, "real_price_in_desc", None) or getattr(item, "price", None)
    if not price or price <= 0:
        return False
    return price > market * (1 + float(drop_overpriced_pct) / 100.0)


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
        if getattr(item, "variant", None) is None:
            from avito_radar.analysis.classifier import detect_variant
            item.variant = detect_variant(item.title)

        clear_deal_fields(item)

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

        item.market_samples = stats.count
        item.market_min_price = stats.min_price if stats.min_price > 0 else None

        # If defective (e.g. iCloud lock):
        # Keep market_price for reference of working item cost, but never calculate false deal diff
        if getattr(item, "is_defect", False):
            item.market_price = stats.median_price
            item.market_diff_percent = None
            item.market_median = int(stats.median_price)
            item.recommended_buy = max(0, round(stats.median_price * RECOMMENDED_BUY_FACTOR / 100) * 100)
            continue

        # If combo listing:
        # If real price in desc is known, compare against real price!
        real_p = getattr(item, "real_price_in_desc", None)
        if getattr(item, "is_combo_listing", False):
            item.market_price = stats.median_price
            if real_p and real_p >= 1000:
                diff = (real_p - stats.median_price) / stats.median_price * 100
                item.market_diff_percent = round(diff, 1)
                apply_deal_fields(item, stats.median_price, real_p)
                if diff <= -15 and not getattr(item, "is_accessory", False):
                    item.tags.append(f"🔥 Выгодно ({item.market_diff_percent}%)")
                elif diff >= 25:
                    item.tags.append(f"📈 Выше рынка (+{item.market_diff_percent}%)")
            else:
                # Bait price with unknown model price: do not calculate false diff!
                item.market_diff_percent = None
                item.market_median = int(stats.median_price)
            continue

        # Normal working standalone item
        if item.price:
            item.market_price = stats.median_price
            diff = (item.price - stats.median_price) / stats.median_price * 100
            item.market_diff_percent = round(diff, 1)
            apply_deal_fields(item, stats.median_price, item.price)

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
