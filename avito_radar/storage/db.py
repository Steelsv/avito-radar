"""Local storage and database manager for searches and listings."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
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
    user_id: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if self.user_id is not None:
            self.user_id = str(self.user_id).strip()
        else:
            self.user_id = ""

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


DEFAULT_CITIES: dict[str, dict[str, Any]] = {
    "chelyabinsk": {"id": 661420, "name": "Челябинск"},
    "moskva": {"id": 637640, "name": "Москва"},
    "sankt-peterburg": {"id": 653240, "name": "Санкт-Петербург"},
    "ekaterinburg": {"id": 626600, "name": "Екатеринбург"},
    "novosibirsk": {"id": 645250, "name": "Новосибирск"},
    "kazan": {"id": 632660, "name": "Казань"},
    "nizhniy_novgorod": {"id": 641780, "name": "Нижний Новгород"},
    "samara": {"id": 651440, "name": "Самара"},
    "omsk": {"id": 646190, "name": "Омск"},
    "rostov-na-donu": {"id": 649980, "name": "Ростов-на-Дону"},
    "ufa": {"id": 658600, "name": "Уфа"},
    "krasnoyarsk": {"id": 635840, "name": "Красноярск"},
    "voronezh": {"id": 625880, "name": "Воронеж"},
    "perm": {"id": 647680, "name": "Пермь"},
    "volgograd": {"id": 624560, "name": "Волгоград"},
    "krasnodar": {"id": 634810, "name": "Краснодар"},
    "tyumen": {"id": 657410, "name": "Тюмень"},
    "sochi": {"id": 635240, "name": "Сочи"},
    "rossiya": {"id": 621540, "name": "Вся Россия"},
}


def load_locations_cache() -> dict[str, Any]:
    data = load_json(LOCATIONS_CACHE_PATH)
    if "cities" not in data or not data["cities"]:
        data["cities"] = DEFAULT_CITIES.copy()
    else:
        for k, v in DEFAULT_CITIES.items():
            if k not in data["cities"]:
                data["cities"][k] = v
    return data


def save_locations_cache(cache: dict[str, Any]) -> None:
    save_json(LOCATIONS_CACHE_PATH, cache)


SEEDS_PATH = ROOT_DIR / "searches_seeds.json"


def save_search(search: SearchRecord) -> None:
    ensure_dirs()
    search.folder.mkdir(parents=True, exist_ok=True)
    config_path = search.folder / "config.json"
    save_json(config_path, asdict(search))
    try:
        seeds = load_json(SEEDS_PATH)
        seeds[search.name] = asdict(search)
        save_json(SEEDS_PATH, seeds)
    except Exception:
        pass


def load_search(name: str) -> SearchRecord | None:
    config_path = SEARCHES_DIR / name / "config.json"
    if not config_path.exists():
        return None
    data = load_json(config_path)
    known_fields = {f.name for f in fields(SearchRecord)}
    filtered_data = {k: v for k, v in data.items() if k in known_fields}
    return SearchRecord(**filtered_data)


def list_searches(user_id: str | int | None = None) -> list[SearchRecord]:
    ensure_dirs()
    if SEEDS_PATH.exists():
        try:
            seeds = load_json(SEEDS_PATH)
            for s_name, s_data in seeds.items():
                target_folder = SEARCHES_DIR / s_name
                cfg_path = target_folder / "config.json"
                if not cfg_path.exists():
                    target_folder.mkdir(parents=True, exist_ok=True)
                    save_json(cfg_path, s_data)
        except Exception:
            pass

    results = []
    for p in sorted(SEARCHES_DIR.iterdir()):
        if p.is_dir():
            rec = load_search(p.name)
            if rec:
                results.append(rec)

    if user_id is not None:
        uid_str = str(user_id).strip()
        owner_id = str(os.environ.get("TELEGRAM_CHAT_ID", "")).strip()

        filtered = []
        for r in results:
            r_uid = str(r.user_id or "").strip()
            # Direct match
            if r_uid and r_uid == uid_str:
                filtered.append(r)
            # If request is from owner, also include legacy searches that had no user_id
            elif uid_str and owner_id and uid_str == owner_id and r_uid in ("", "0", "None"):
                filtered.append(r)
        return filtered

    return results


def delete_search(name: str, user_id: str | int | None = None) -> bool:
    import shutil
    rec = load_search(name)
    if rec and user_id is not None:
        uid_str = str(user_id).strip()
        owner_id = str(os.environ.get("TELEGRAM_CHAT_ID", "")).strip()
        r_uid = str(rec.user_id or "").strip()
        # Verify ownership unless admin/owner
        if r_uid and r_uid != uid_str and not (owner_id and uid_str == owner_id):
            return False

    folder = SEARCHES_DIR / name
    deleted = False
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)
        deleted = True
    try:
        seeds = load_json(SEEDS_PATH)
        if name in seeds:
            del seeds[name]
            save_json(SEEDS_PATH, seeds)
            deleted = True
    except Exception:
        pass
    return deleted


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
