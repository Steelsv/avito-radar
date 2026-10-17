"""Freemium user accounts, plans, limits, trials and referrals."""

from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta
from typing import Any

from avito_radar.storage.db import DATA_DIR, load_json, save_json

USERS_PATH = DATA_DIR / "users.json"

TRIAL_DAYS = 1
REFERRAL_PRO_DAYS = 3

PLANS_LIMITS: dict[str, dict[str, Any]] = {
    "free": {"max_searches": 1, "analysis_per_day": 3, "notify_delay_min": 15},
    "pro": {"max_searches": 15, "analysis_per_day": -1, "notify_delay_min": 0},
}

_LOCK = threading.RLock()


def _owner_id() -> str:
    return str(os.environ.get("TELEGRAM_CHAT_ID", "")).strip()


def _now() -> datetime:
    return datetime.now()


def _default_user(user_id: str) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "plan": "free",
        "pro_expires_at": None,
        "trial_used": False,
        "analysis_used_today": 0,
        "analysis_date": _now().strftime("%Y-%m-%d"),
        "referrals": 0,
        "referred_by": None,
        "created_at": _now().isoformat(),
        "username": "",
        "home_address": None,
        "home_lat": None,
        "home_lon": None,
        "quiet_enabled": False,
        "quiet_start": 23,
        "quiet_end": 8,
    }


def all_users() -> list[dict[str, Any]]:
    data = load_json(USERS_PATH)
    return [v for v in data.values() if isinstance(v, dict) and v.get("user_id")]


def get_user(user_id: str | int) -> dict[str, Any]:
    uid = str(user_id).strip()
    with _LOCK:
        data = load_json(USERS_PATH)
        user = data.get(uid)
        if not isinstance(user, dict):
            user = _default_user(uid)
            data[uid] = user
            save_json(USERS_PATH, data)
        user.setdefault("user_id", uid)
        for k, v in _default_user(uid).items():
            user.setdefault(k, v)
        return user


def save_user(user: dict[str, Any]) -> None:
    uid = str(user.get("user_id") or "").strip()
    if not uid:
        return
    with _LOCK:
        data = load_json(USERS_PATH)
        data[uid] = user
        save_json(USERS_PATH, data)


def _is_expired(user: dict[str, Any]) -> bool:
    exp = user.get("pro_expires_at")
    if not exp:
        return True
    if str(exp) == "forever":
        return False
    try:
        return _now() >= datetime.fromisoformat(str(exp))
    except ValueError:
        return True


def is_pro(user_id: str | int) -> bool:
    uid = str(user_id).strip()
    if uid and uid == _owner_id():
        return True
    user = get_user(uid)
    if user.get("plan") == "pro" and not _is_expired(user):
        return True
    if user.get("plan") == "pro" and _is_expired(user):
        user["plan"] = "free"
        user["pro_expires_at"] = None
        save_user(user)
    return False


def grant_pro(user_id: str | int, days: int) -> dict[str, Any]:
    uid = str(user_id).strip()
    user = get_user(uid)
    base = _now()
    if user.get("plan") == "pro" and user.get("pro_expires_at") and not _is_expired(user):
        try:
            base = datetime.fromisoformat(str(user["pro_expires_at"]))
        except ValueError:
            base = _now()
    user["plan"] = "pro"
    user["pro_expires_at"] = (base + timedelta(days=days)).isoformat()
    save_user(user)
    return user


def grant_pro_forever(user_id: str | int) -> dict[str, Any]:
    uid = str(user_id).strip()
    user = get_user(uid)
    user["plan"] = "pro"
    user["pro_expires_at"] = "forever"
    save_user(user)
    return user


def revoke_pro(user_id: str | int) -> dict[str, Any]:
    uid = str(user_id).strip()
    user = get_user(uid)
    user["plan"] = "free"
    user["pro_expires_at"] = None
    save_user(user)
    return user


def grant_trial(user_id: str | int) -> dict[str, Any]:
    """24h PRO trial, once per user. Returns {"ok": bool, "reason": str, "user": dict}."""
    uid = str(user_id).strip()
    user = get_user(uid)
    if user.get("trial_used"):
        return {"ok": False, "reason": "already_used", "user": user}
    user["trial_used"] = True
    user["plan"] = "pro"
    user["pro_expires_at"] = (_now() + timedelta(days=TRIAL_DAYS)).isoformat()
    save_user(user)
    return {"ok": True, "reason": "granted", "user": user}


def use_analysis(user_id: str | int) -> dict[str, Any]:
    """Consume one analysis slot. Returns {"allowed": bool, "used": n, "limit": n}."""
    uid = str(user_id).strip()
    if is_pro(uid):
        user = get_user(uid)
        return {"allowed": True, "used": user.get("analysis_used_today", 0), "limit": -1}
    user = get_user(uid)
    today = _now().strftime("%Y-%m-%d")
    if user.get("analysis_date") != today:
        user["analysis_date"] = today
        user["analysis_used_today"] = 0
    limit = int(PLANS_LIMITS["free"]["analysis_per_day"])
    used = int(user.get("analysis_used_today", 0))
    if used >= limit:
        save_user(user)
        return {"allowed": False, "used": used, "limit": limit}
    user["analysis_used_today"] = used + 1
    save_user(user)
    return {"allowed": True, "used": used + 1, "limit": limit}


def count_user_searches(user_id: str | int) -> int:
    from avito_radar.storage.db import list_searches

    return len(list_searches(user_id=str(user_id).strip()))


def get_limits(user_id: str | int) -> dict[str, Any]:
    if is_pro(user_id):
        return dict(PLANS_LIMITS["pro"])
    return dict(PLANS_LIMITS["free"])


def add_referral(referrer_id: str | int, new_user_id: str | int) -> dict[str, Any]:
    """Register referral: referrer gets +3 days PRO. Returns {"ok": bool, "reason": str}."""
    ref_id = str(referrer_id).strip()
    new_id = str(new_user_id).strip()
    if not ref_id or not new_id or ref_id == new_id:
        return {"ok": False, "reason": "invalid"}
    with _LOCK:
        new_user = get_user(new_id)
        if new_user.get("referred_by"):
            return {"ok": False, "reason": "already_referred"}
        # only first-time users (created just now) can be attributed
        created = new_user.get("created_at") or ""
        try:
            is_fresh = _now() - datetime.fromisoformat(created) < timedelta(minutes=5)
        except ValueError:
            is_fresh = False
        if not is_fresh:
            return {"ok": False, "reason": "not_new"}
        new_user["referred_by"] = ref_id
        save_user(new_user)
    referrer = grant_pro(ref_id, REFERRAL_PRO_DAYS)
    referrer["referrals"] = int(referrer.get("referrals", 0)) + 1
    save_user(referrer)
    return {"ok": True, "reason": "granted"}


def set_home_address(user_id: str | int, address: str, lat: float, lon: float) -> dict[str, Any]:
    uid = str(user_id).strip()
    user = get_user(uid)
    user["home_address"] = str(address).strip()
    user["home_lat"] = float(lat)
    user["home_lon"] = float(lon)
    save_user(user)
    return user


def clear_home_address(user_id: str | int) -> dict[str, Any]:
    uid = str(user_id).strip()
    user = get_user(uid)
    user["home_address"] = None
    user["home_lat"] = None
    user["home_lon"] = None
    save_user(user)
    return user


def set_quiet_hours(user_id: str | int, enabled: bool, start: int, end: int) -> dict[str, Any]:
    uid = str(user_id).strip()
    if not isinstance(start, int) or not isinstance(end, int) or isinstance(start, bool) or isinstance(end, bool):
        raise ValueError("start and end must be integers")
    if not 0 <= start <= 23 or not 0 <= end <= 23:
        raise ValueError("start and end must be hours in 0-23")
    if start == end:
        raise ValueError("start and end must differ")
    user = get_user(uid)
    user["quiet_enabled"] = bool(enabled)
    user["quiet_start"] = start
    user["quiet_end"] = end
    save_user(user)
    return user


def is_quiet_now(user: dict[str, Any] | None, now: datetime | None = None) -> bool:
    if not isinstance(user, dict) or not user.get("quiet_enabled"):
        return False
    try:
        start = int(user.get("quiet_start", 23))
        end = int(user.get("quiet_end", 8))
    except (TypeError, ValueError):
        return False
    if start == end:
        return False
    hour = (now or _now()).hour
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def public_profile(user_id: str | int) -> dict[str, Any]:
    uid = str(user_id).strip()
    user = get_user(uid)
    pro = is_pro(uid)
    limits = get_limits(uid)
    used = int(user.get("analysis_used_today", 0))
    today = _now().strftime("%Y-%m-%d")
    if user.get("analysis_date") != today:
        used = 0
    radars_used = count_user_searches(uid)
    return {
        "user_id": uid,
        "plan": "pro" if pro else "free",
        "pro_expires_at": user.get("pro_expires_at") if pro else None,
        "radars_used": radars_used,
        "radars_limit": limits["max_searches"],
        "analysis_used_today": used,
        "analysis_limit": limits["analysis_per_day"],
        "trial_available": not bool(user.get("trial_used")),
        "home_address": user.get("home_address"),
        "quiet_hours": {
            "enabled": bool(user.get("quiet_enabled", False)),
            "start": int(user.get("quiet_start", 23)),
            "end": int(user.get("quiet_end", 8)),
        },
    }
