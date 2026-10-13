"""High-resilience HTTP client for Avito with TLS fingerprinting and anti-bot bypass.

Features:
- curl_cffi with realistic browser fingerprinting (Firefox / Chrome).
- Automatic SHA-256 Proof-of-Work solver for firewallPow challenges.
- Automatic Qrator cookie sequence reproduction.
- Smart session rotation upon captchas.
- Polite rate-limiting with random jitter.
"""

from __future__ import annotations

import logging
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlencode

from curl_cffi import requests
from curl_cffi.requests.exceptions import (
    ConnectionError as CurlConnectionError,
    IncompleteRead,
    Timeout as CurlTimeout,
)

from avito_radar.core import pow_solver, qrator

logger = logging.getLogger(__name__)

BASE_URL = "https://www.avito.ru"
ITEMS_API_URL = f"{BASE_URL}/web/1/js/items"
POW_GET_URL = f"{BASE_URL}/web/3/firewallPow/get"
POW_VERIFY_URL = f"{BASE_URL}/web/3/firewallPow/verify"

DEFAULT_DELAY_SECONDS = 3.0
IP_BLOCK_WAIT_SECONDS = 15
MAX_POW_RETRIES = 3
MAX_SESSION_RESETS = 3
PAGE_SIZE = 50

TRANSPORT_ERRORS = (IncompleteRead, CurlConnectionError, CurlTimeout)


def get_platform_user_agent() -> str:
    if sys.platform.startswith("win"):
        plat = "Windows NT 10.0; Win64; x64"
    elif sys.platform == "darwin":
        plat = "Macintosh; Intel Mac OS X 10.15"
    else:
        plat = "X11; Linux x86_64"
    return f"Mozilla/5.0 ({plat}; rv:135.0) Gecko/20100101 Firefox/135.0"


def default_headers(referer: str = BASE_URL) -> dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Origin": BASE_URL,
        "Referer": referer,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Sec-GPC": "1",
        "User-Agent": get_platform_user_agent(),
        "X-Requested-With": "XMLHttpRequest",
        "X-Source": "client-browser",
    }


def document_headers(referer: str = BASE_URL) -> dict[str, str]:
    return {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Referer": referer,
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": get_platform_user_agent(),
    }


@dataclass(frozen=True)
class CatalogPage:
    page_number: int
    items: tuple[dict[str, Any], ...]
    total_count: int
    items_on_page: int

    @property
    def is_last(self) -> bool:
        return (
            not self.items
            or self.items_on_page < PAGE_SIZE
            or self.page_number * PAGE_SIZE >= self.total_count
        )


class AvitoClient:
    """Robust Avito client with anti-bot challenge solving and session rotation."""

    def __init__(
        self,
        *,
        delay: float = DEFAULT_DELAY_SECONDS,
        log_callback: Callable[[str, dict[str, Any]], None] | None = None,
        impersonate_profile: str = "firefox147",
    ) -> None:
        self.delay = delay
        self.log = log_callback or (lambda event, data: None)
        self.impersonate_profile = impersonate_profile
        self.session: requests.Session | None = None
        self.last_request_time = 0.0
        self.current_referer = BASE_URL
        self.sessions_created = 0

    def _sleep_jitter(self) -> None:
        elapsed = time.monotonic() - self.last_request_time
        target_wait = self.delay * random.uniform(0.75, 1.25)
        remaining = target_wait - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _new_session(self, referer: str) -> requests.Session:
        session = requests.Session(
            impersonate=self.impersonate_profile,
            trust_env=False,
        )
        session.headers.update(default_headers(referer))
        self.current_referer = referer
        self.sessions_created += 1
        return session

    def _ensure_session(self, referer: str) -> None:
        if self.session is None:
            self.session = self._new_session(referer)

    def _classify_response(self, response: Any) -> str:
        status = response.status_code
        if status == 200:
            return "ok"
        if status == 439 or (status == 429 and self._has_pow(response)):
            return "pow"
        if (
            status in (429, 439)
            and self.session is not None
            and self.session.cookies.get("pow_challenge")
        ):
            return "pow"
        if qrator.is_qrator_challenge(response):
            return "qrator"
        if status in (403, 429):
            # Captcha or rate limit
            return "captcha"
        return f"status_{status}"

    def _has_pow(self, response: Any) -> bool:
        try:
            data = response.json()
            return isinstance(data, dict) and bool(data.get("pow_challenge"))
        except Exception:
            return False

    def _solve_pow(self, response: Any) -> bool:
        if self.session is None:
            return False
        try:
            # Extract challenge
            pow_challenge_str = ""
            if self._has_pow(response):
                pow_challenge_str = response.json().get("pow_challenge", "")
            if not pow_challenge_str and self.session.cookies.get("pow_challenge"):
                pow_challenge_str = self.session.cookies.get("pow_challenge", "")
            if not pow_challenge_str:
                return False

            self.log("POW_SOLVING", {"challenge": pow_challenge_str[:15] + "..."})
            self.session.headers.update({"Referer": self.current_referer, "Content-Type": "application/json"})

            # 1. Get challenge JWT
            get_res = self.session.post(
                POW_GET_URL,
                json=pow_solver.build_get_payload(pow_challenge_str),
                timeout=10,
            )
            get_data = get_res.json()
            get_result = get_data.get("success", {}).get("result") or get_data.get("result") or {}
            jwt_token = get_result.get("challenge_jwt")
            if not jwt_token:
                return False

            # 2. Compute verify nonce
            verify_payload = pow_solver.build_verify_payload(jwt_token)

            # 3. Submit verify
            verify_res = self.session.post(POW_VERIFY_URL, json=verify_payload, timeout=10)
            verify_data = verify_res.json()
            verify_result = verify_data.get("success", {}).get("result") or verify_data.get("result") or {}
            verified = verify_result.get("verified")
            if verified:
                self.log("POW_SUCCESS", {})
                return True
        except Exception as exc:
            self.log("POW_FAILED", {"error": str(exc)})
        return False

    def _request(self, url: str, *, is_document: bool = False, custom_headers: dict[str, str] | None = None) -> tuple[str, Any]:
        if self.session is None:
            raise RuntimeError("Session is not initialized")

        headers = document_headers(self.current_referer) if is_document else default_headers(self.current_referer)
        if custom_headers:
            headers.update(custom_headers)
        self.session.headers.update(headers)

        for _ in range(MAX_POW_RETRIES + 1):
            self._sleep_jitter()
            try:
                response = self.session.get(url, timeout=15, allow_redirects=False)
            except TRANSPORT_ERRORS as exc:
                self.log("TRANSPORT_ERROR", {"error": type(exc).__name__})
                raise

            self.last_request_time = time.monotonic()
            kind = self._classify_response(response)

            if kind == "ok":
                return "ok", response

            if kind == "qrator":
                self.log("QRATOR_CHALLENGE", {})
                try:
                    qrator.run_qrator_flow(self.session, response.text, url, base_origin=BASE_URL)
                    continue
                except Exception as exc:
                    self.log("QRATOR_FAILED", {"error": str(exc)})
                    return "qrator_fail", response

            if kind == "pow":
                if self._solve_pow(response):
                    continue
                return "pow_fail", response

            return kind, response

        return "max_retries_exceeded", None

    def get_json(self, url: str, *, catalog_url: str, custom_headers: dict[str, str] | None = None) -> dict[str, Any]:
        """Fetch JSON endpoint with automatic recovery and session rotation."""
        for attempt in range(MAX_SESSION_RESETS + 1):
            self._ensure_session(catalog_url)
            self.current_referer = catalog_url
            try:
                kind, response = self._request(url, is_document=False, custom_headers=custom_headers)
            except TRANSPORT_ERRORS:
                self.session = None
                continue

            if kind == "ok":
                try:
                    payload = response.json()
                    if isinstance(payload, dict):
                        return payload
                except Exception:
                    pass

            self.log("SESSION_RESET", {"reason": kind, "attempt": attempt + 1})
            self.session = None

        raise RuntimeError(f"Unable to fetch JSON from {url} after {MAX_SESSION_RESETS} attempts")

    def get_html(self, url: str, *, catalog_url: str) -> str | None:
        """Fetch HTML document (e.g. item page) with automatic recovery."""
        for attempt in range(MAX_SESSION_RESETS + 1):
            self._ensure_session(catalog_url)
            self.current_referer = catalog_url
            try:
                kind, response = self._request(url, is_document=True)
            except TRANSPORT_ERRORS:
                self.session = None
                continue

            if kind == "ok":
                return response.text
            if kind.startswith("status_404"):
                return None  # Deleted item

            self.log("SESSION_RESET", {"reason": kind, "context": "html"})
            self.session = None

        return None

    def fetch_catalog_page(self, *, catalog_url: str, params: dict[str, str], page_number: int) -> CatalogPage:
        """Fetch one catalog page via items API."""
        query_items = [(k, str(v)) for k, v in params.items()]
        query_items.extend([("p", str(page_number)), ("updateListOnly", "true")])
        url = f"{ITEMS_API_URL}?{urlencode(query_items)}"

        headers = {
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "X-Source": "client-browser",
        }
        payload = self.get_json(url, catalog_url=catalog_url, custom_headers=headers)
        catalog = payload.get("catalog") if isinstance(payload.get("catalog"), dict) else {}
        items = catalog.get("items") if isinstance(catalog.get("items"), list) else []

        valid_items = tuple(
            item for item in items
            if isinstance(item, dict) and item.get("type", "item") == "item"
        )
        total_count = payload.get("totalCount") if isinstance(payload.get("totalCount"), int) else 0
        items_on_page = payload.get("itemsOnPage") if isinstance(payload.get("itemsOnPage"), int) else len(valid_items)

        return CatalogPage(
            page_number=page_number,
            items=valid_items,
            total_count=total_count,
            items_on_page=items_on_page,
        )
