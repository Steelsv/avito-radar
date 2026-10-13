"""User settings and application configuration manager."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from avito_radar.storage.db import DATA_DIR, load_json, save_json

SETTINGS_FILE = DATA_DIR / "settings.json"


@dataclass
class AppSettings:
    request_delay: float = 15.0          # Delay between page requests (seconds)
    watch_interval: float = 120.0        # Delay between watch check loops (seconds)
    max_scan_pages: int = 30             # Maximum pages per scan run (up to Avito's 30/100 cap)
    fresh_hours_threshold: float = 3.0   # Ads published within N hours are considered fresh
    alert_private_only: bool = True      # Send alerts only for private individuals
    alert_filter_junk: bool = True       # Filter out junk, parts and clickbait prices
    alert_no_republished: bool = True    # Filter out republished old ads
    impersonate_profile: str = "firefox147"


def load_settings() -> AppSettings:
    data = load_json(SETTINGS_FILE)
    if not data:
        return AppSettings()
    try:
        return AppSettings(**data)
    except Exception:
        return AppSettings()


def save_settings(settings: AppSettings) -> None:
    save_json(SETTINGS_FILE, asdict(settings))
