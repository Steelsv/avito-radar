"""Local storage and database manager for searches and listings."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from avito_radar.parsers.item_parser import ParsedItem

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
SEARCHES_DIR = DATA_DIR / "searches"
LOCATIONS_CACHE_PATH = DATA_DIR / "locations_cache.json"


@dataclass
class SearchRecord:
    name: str
    title: str
    category_type: str
    catalog_url: str
    city: str
    params: dict[str, str]
    watch_pages: int = 1
    fresh_hours: float = 3.0
    private_only: bool = True
    new_only: bool = True
    min_price: int | None = None
    max_price: int | None = None
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    @property
    def folder(self) -> Path:
        return SEARCHES_DIR / self.name

    def file_path(self, filename: str) -> Path:
        return self.folder / filename


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SEARCHES_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_locations_cache() -> dict[str, Any]:
    return load_json(LOCATIONS_CACHE_PATH)


def save_locations_cache(cache: dict[str, Any]) -> None:
    save_json(LOCATIONS_CACHE_PATH, cache)


def save_search(search: SearchRecord) -> None:
    ensure_dirs()
    search.folder.mkdir(parents=True, exist_ok=True)
    config_path = search.folder / "config.json"
    save_json(config_path, asdict(search))


def load_search(name: str) -> SearchRecord | None:
    config_path = SEARCHES_DIR / name / "config.json"
    if not config_path.exists():
        return None
    data = load_json(config_path)
    return SearchRecord(**data)


def list_searches() -> list[SearchRecord]:
    ensure_dirs()
    results = []
    for p in sorted(SEARCHES_DIR.iterdir()):
        if p.is_dir():
            rec = load_search(p.name)
            if rec:
                results.append(rec)
    return results


def delete_search(name: str) -> bool:
    import shutil
    folder = SEARCHES_DIR / name
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)
        return True
    return False


def load_listings(search: SearchRecord) -> dict[str, dict[str, Any]]:
    return load_json(search.file_path("listings.json"))


def save_listings(search: SearchRecord, listings: dict[str, dict[str, Any]]) -> None:
    save_json(search.file_path("listings.json"), listings)


def load_seen(search: SearchRecord) -> dict[str, str]:
    return load_json(search.file_path("seen.json"))


def save_seen(search: SearchRecord, seen: dict[str, str]) -> None:
    save_json(search.file_path("seen.json"), seen)


def load_scan_state(search: SearchRecord) -> dict[str, Any]:
    return load_json(search.file_path("state.json"))


def save_scan_state(search: SearchRecord, state: dict[str, Any]) -> None:
    save_json(search.file_path("state.json"), state)


def append_alert(search: SearchRecord, item: ParsedItem) -> None:
    path = search.file_path("alerts.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "timestamp": datetime.now().isoformat(),
        "id": item.id,
        "title": item.title,
        "price": item.price,
        "url": item.url,
        "address": item.address,
        "seller": item.seller_name,
        "tags": item.tags,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
