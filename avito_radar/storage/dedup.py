"""Photo-repost dedup: same first image + title + seller under a new lot id."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from avito_radar.storage.db import SearchRecord, load_json, save_json

SEEN_POSTS_FILE = "seen_posts.json"


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", str(title or "")).strip().lower()


def post_key(item: Any) -> str:
    images = list(getattr(item, "images", None) or [])
    first_image = str(images[0]) if images else ""
    seller = str(getattr(item, "seller_name", "") or "").strip().lower()
    raw = f"{first_image}|{normalize_title(getattr(item, 'title', ''))}|{seller}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _posts_path(search: SearchRecord):
    return search.file_path(SEEN_POSTS_FILE)


def load_seen_posts(search: SearchRecord) -> dict[str, str]:
    data = load_json(_posts_path(search))
    return data if isinstance(data, dict) else {}


def check_and_mark_post(search: SearchRecord, item: Any) -> bool:
    """Returns True when this exact post was already alerted under a different lot id."""
    key = post_key(item)
    lot_id = str(getattr(item, "id", ""))
    posts = load_seen_posts(search)
    known = posts.get(key)
    if known is not None and str(known) != lot_id:
        return True
    posts[key] = lot_id
    save_json(_posts_path(search), posts)
    return False


def is_repost(search: SearchRecord, item: Any) -> bool:
    posts = load_seen_posts(search)
    known = posts.get(post_key(item))
    return known is not None and str(known) != str(getattr(item, "id", ""))
