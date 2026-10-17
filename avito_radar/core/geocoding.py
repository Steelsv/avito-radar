"""Geocoding of the user's home address and distance helpers (Nominatim)."""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "avito-radar/1.0 (steelsv)"}
NOMINATIM_TIMEOUT = 10


def geocode_address(address: str, city: str | None = None) -> dict[str, Any] | None:
    """Resolve an address to coordinates via Nominatim. Returns None on failure."""
    query = address.strip()
    if not query:
        return None
    if city and city.strip():
        query = f"{query}, {city.strip()}"
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": "1",
        "countrycodes": "ru",
        "accept-language": "ru",
    }
    try:
        resp = requests.get(
            NOMINATIM_URL, params=params, headers=NOMINATIM_HEADERS, timeout=NOMINATIM_TIMEOUT
        )
        resp.raise_for_status()
        results = resp.json()
    except Exception:
        return None
    if not isinstance(results, list) or not results:
        return None
    first = results[0]
    if not isinstance(first, dict):
        return None
    try:
        lat = float(first["lat"])
        lon = float(first["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    display_name = str(first.get("display_name") or query)
    return {"lat": lat, "lon": lon, "display_name": display_name}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, rounded to 0.1 km."""
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return round(2 * r * math.asin(math.sqrt(a)), 1)


def format_distance(km: float) -> str:
    """Human-friendly distance from the user."""
    if km < 1:
        return "<1 км от вас"
    km = float(Decimal(str(km)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
    return f"~{km:.1f} км от вас"


def lot_distance_km(home: dict[str, Any] | None, geo_lat: float | None, geo_lon: float | None) -> float | None:
    """Distance from the user's saved home coords to a lot, or None."""
    if not home:
        return None
    try:
        h_lat = float(home["home_lat"])
        h_lon = float(home["home_lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if geo_lat is None or geo_lon is None:
        return None
    return haversine_km(h_lat, h_lon, float(geo_lat), float(geo_lon))
