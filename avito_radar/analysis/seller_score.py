"""Seller reliability scoring: reseller vs private seller detection."""

from __future__ import annotations

from typing import Any

RESELLER_WORDS = ("магазин", "агентств", "компани")
RESELLER_CLOSED_THRESHOLD = 15
RELIABLE_RATING = 4.5
RELIABLE_CLOSED_THRESHOLD = 3


def score_seller(item: Any) -> dict[str, str]:
    seller_type = str(getattr(item, "seller_type", "") or "").lower()
    closed_raw = getattr(item, "closed_listings", None)
    closed = int(closed_raw) if isinstance(closed_raw, (int, float)) else 0
    rating_raw = getattr(item, "seller_rating", None)
    rating = float(rating_raw) if isinstance(rating_raw, (int, float)) else 0.0

    if any(word in seller_type for word in RESELLER_WORDS) or closed >= RESELLER_CLOSED_THRESHOLD:
        return {"level": "reseller", "label": "Перекуп/магазин"}
    if rating <= 0 and closed == 0:
        return {"level": "new", "label": "Свежий аккаунт - риск"}
    if rating >= RELIABLE_RATING and closed >= RELIABLE_CLOSED_THRESHOLD:
        return {"level": "reliable", "label": "Надежный продавец"}
    return {"level": "regular", "label": "Частный продавец"}
