"""Payments: Telegram Stars invoices, YooKassa payments, pre-checkout handling."""

from __future__ import annotations

import base64
import logging
import os
import secrets
import urllib.parse
from typing import Any

import requests

from avito_radar.storage import users

logger = logging.getLogger(__name__)

PLANS: dict[str, dict[str, Any]] = {
    "pro_month": {"title": "PRO Sniper - 30 дней", "stars": 299, "days": 30},
    "pro_year": {"title": "PRO Sniper - 12 месяцев", "stars": 1999, "days": 365},
}


def get_plan(plan_id: str) -> dict[str, Any] | None:
    return PLANS.get(plan_id)


def create_stars_invoice_link(bot_token: str, user_id: str | int, plan_id: str) -> str | None:
    plan = get_plan(plan_id)
    if not plan or not bot_token:
        return None
    nonce = secrets.token_hex(8)
    payload = f"pro:{plan_id}:{user_id}:{nonce}"
    url = f"https://api.telegram.org/bot{bot_token}/createInvoiceLink"
    body = {
        "title": plan["title"],
        "description": "PRO Sniper: 15 радаров, мгновенные уведомления, безлимитная аналитика рынка.",
        "payload": payload,
        "provider_token": "",
        "currency": "XTR",
        "prices": [{"label": plan["title"], "amount": plan["stars"]}],
    }
    try:
        resp = requests.post(url, json=body, timeout=20)
        data = resp.json()
        if data.get("ok"):
            return str(data.get("result") or "") or None
        logger.warning("createInvoiceLink failed: %s", data.get("description"))
    except Exception as exc:
        logger.error("createInvoiceLink error: %s", exc)
    return None


def get_yookassa_payment_url(user_id: str | int, plan_id: str) -> str | None:
    shop_id = os.environ.get("YOOKASSA_SHOP_ID", "").strip()
    secret = os.environ.get("YOOKASSA_SECRET", "").strip()
    plan = get_plan(plan_id)
    if not shop_id or not secret or not plan:
        return None
    return_url = (os.environ.get("MINI_APP_URL") or "https://t.me").rstrip("/")
    amount_rub = plan["stars"] * 2  # условная конвертация Stars в рубли
    body = {
        "amount": {"value": f"{amount_rub}.00", "currency": "RUB"},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": return_url},
        "description": plan["title"],
        "metadata": {"user_id": str(user_id), "plan_id": plan_id},
    }
    try:
        auth = base64.b64encode(f"{shop_id}:{secret}".encode()).decode()
        resp = requests.post(
            "https://api.yookassa.ru/v3/payments",
            json=body,
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/json",
                "Idempotence-Key": secrets.token_hex(16),
            },
            timeout=25,
        )
        data = resp.json()
        confirmation = (data.get("confirmation") or {})
        if confirmation.get("type") == "redirect" and confirmation.get("confirmation_url"):
            return str(confirmation["confirmation_url"])
        logger.warning("YooKassa payment creation failed: %s", data)
    except Exception as exc:
        logger.error("YooKassa payment error: %s", exc)
    return None


def handle_pre_checkout(bot_token: str, pre_checkout_query: dict[str, Any]) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/answerPreCheckoutQuery"
    try:
        requests.post(url, json={"pre_checkout_query_id": pre_checkout_query.get("id"), "ok": True}, timeout=20)
    except Exception as exc:
        logger.error("answerPreCheckoutQuery error: %s", exc)


def handle_successful_payment(bot_token: str, message: dict[str, Any]) -> None:
    """Parse Stars payment payload, grant PRO, confirm to the user."""
    payment = message.get("successful_payment") or {}
    payload = str(payment.get("invoice_payload") or "")
    parts = payload.split(":")
    if len(parts) < 3 or parts[0] != "pro":
        logger.warning("Unexpected successful_payment payload: %r", payload)
        return
    plan_id = parts[1]
    try:
        user_id = parts[2]
    except ValueError:
        return
    plan = get_plan(plan_id)
    if not plan:
        logger.warning("Unknown plan in payload: %s", plan_id)
        return
    user = users.grant_pro(user_id, int(plan["days"]))
    text = (
        f"👑 <b>PRO Sniper активирован!</b>\n\n"
        f"Тариф: <b>{plan['title']}</b>\n"
        f"Действует до: <code>{user.get('pro_expires_at')}</code>\n\n"
        f"⚡ 15 радаров · мгновенные уведомления · безлимитная аналитика рынка."
    )
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": user_id, "text": text, "parse_mode": "HTML"}, timeout=20)
    except Exception as exc:
        logger.error("sendMessage after payment error: %s", exc)


def verify_yookassa_payment(payment_id: str) -> dict[str, Any] | None:
    """Fetch payment from YooKassa API and return it if succeeded and trusted."""
    shop_id = os.environ.get("YOOKASSA_SHOP_ID", "").strip()
    secret = os.environ.get("YOOKASSA_SECRET", "").strip()
    if not shop_id or not secret or not payment_id:
        return None
    try:
        auth = base64.b64encode(f"{shop_id}:{secret}".encode()).decode()
        resp = requests.get(
            f"https://api.yookassa.ru/v3/payments/{urllib.parse.quote(payment_id)}",
            headers={"Authorization": f"Basic {auth}"},
            timeout=25,
        )
        if resp.status_code != 200:
            return None
        payment = resp.json()
        if payment.get("status") == "succeeded" and payment.get("paid"):
            return payment
    except Exception as exc:
        logger.error("YooKassa payment verify error: %s", exc)
    return None


def process_yookassa_webhook(body: dict[str, Any]) -> dict[str, Any]:
    """Verify webhook via API, grant PRO by metadata. Returns {"ok": bool, "message": str}."""
    event = body.get("event") or ""
    obj = body.get("object") or {}
    payment_id = str(obj.get("id") or "")
    if event != "payment.succeeded" or not payment_id:
        return {"ok": False, "message": "ignored"}
    payment = verify_yookassa_payment(payment_id)
    if not payment:
        return {"ok": False, "message": "verification failed"}
    meta = payment.get("metadata") or {}
    user_id = str(meta.get("user_id") or "")
    plan_id = str(meta.get("plan_id") or "")
    plan = get_plan(plan_id)
    if not user_id or not plan:
        return {"ok": False, "message": "unknown user or plan"}
    users.grant_pro(user_id, int(plan["days"]))
    return {"ok": True, "message": "pro granted"}
