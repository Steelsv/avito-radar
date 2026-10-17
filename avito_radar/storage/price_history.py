"""Per-lot price history with drop detection."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

from avito_radar.storage.db import DATA_DIR, load_json, save_json

PRICE_HISTORY_PATH = DATA_DIR / "price_history.json"
MAX_ENTRIES_PER_LOT = 30
DROP_MIN_AGE_HOURS = 12.0

_LOCK = threading.RLock()


def _load() -> dict[str, list[dict[str, Any]]]:
    data = load_json(PRICE_HISTORY_PATH)
    return data if isinstance(data, dict) else {}


def record_price(lot_id: str | int, price: int | None, ts: str | None = None) -> bool:
    """Append a price point unless the last one is identical. Returns True if stored."""
    if price is None:
        return False
    try:
        price_int = int(price)
    except (TypeError, ValueError):
        return False
    if price_int <= 0:
        return False
    key = str(lot_id)
    ts_iso = ts or datetime.now().isoformat()
    with _LOCK:
        data = _load()
        entries = [e for e in (data.get(key) or []) if isinstance(e, dict)]
        if entries:
            try:
                last_price = int(entries[-1].get("price") or 0)
            except (TypeError, ValueError):
                last_price = -1
            if last_price == price_int:
                return False
        entries.append({"price": price_int, "ts": ts_iso})
        data[key] = entries[-MAX_ENTRIES_PER_LOT:]
        save_json(PRICE_HISTORY_PATH, data)
    return True


def get_history(lot_id: str | int) -> list[dict[str, Any]]:
    entries = _load().get(str(lot_id)) or []
    return [e for e in entries if isinstance(e, dict)]


def price_drop(lot_id: str | int, current_price: int | None, now: datetime | None = None) -> dict[str, Any] | None:
    """Detect a real price cut against the highest price recorded over 12h ago."""
    now_dt = now or datetime.now()
    if current_price is None:
        return None
    try:
        current = int(current_price)
    except (TypeError, ValueError):
        return None
    if current <= 0:
        return None

    candidates: list[tuple[int, datetime]] = []
    for entry in get_history(lot_id):
        price = entry.get("price")
        if not isinstance(price, int) or price <= 0:
            continue
        try:
            ts = datetime.fromisoformat(str(entry.get("ts")))
        except ValueError:
            continue
        if (now_dt - ts).total_seconds() >= DROP_MIN_AGE_HOURS * 3600:
            candidates.append((price, ts))

    if not candidates:
        return None
    max_price, max_ts = max(candidates, key=lambda pair: pair[0])
    if current >= max_price:
        return None
    days = max(0.0, (now_dt - max_ts).total_seconds() / 86400.0)
    return {"amount": int(max_price - current), "days": round(days, 2)}
