"""Qrator anti-bot challenge handler and fingerprint codec.

Qrator periodically issues an HTTP 302 or 429 challenge with an HTML page containing
a meta-refresh and a dynamic fingerprint script.
This module executes the exact challenge sequence:
1. Loads the script and favicon.
2. Generates XTEA-encrypted browser fingerprint fields (`f` and `s`).
3. Sends multipart form to `/web/2/ft`.
4. Saves session cookies and fires the tracking pixel `/web/1/u?<id>`.
"""

from __future__ import annotations

import json
import re
import secrets
import struct
import time
from collections.abc import Sequence
from typing import Any
from urllib.parse import urljoin, urlsplit

DELTA = 0x9E3779B9
ROUNDS = 32
DEFAULT_KEY = (1901231474, 1081891380, 1433695566, 978402641)

CANVAS_HASH_INDEX = 106
UNIX_TIME_INDEX = 128
MIN_SYNTHETIC_HASH = 4
MAX_UINT32 = 0xFFFFFFFF

# Standard browser profile base (141 components)
BASE_F_TEMPLATE: tuple[int, ...] = (
    1920, 1080, 24, 24, 240, 180, 240, 180, 240, 180, 240, 180, 240, 240, 240,
    240, 240, 240, 240, 180, 180, 180, 180, 180, 1, 1, 1, 1, 1, 1, 0, 1, 0, 1,
    1, 1, 1, 1, 0, 1, 1, 1, 1, 0, 0, 8, 3021059336, 356363667, 1, 2, 2, 2, 0, 2,
    1, 1, 1, 1, 1, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0,
    0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 5,
    3641819743, 3577560136, 3669646833, 3469306551, 1394145034, 1320192270,
    1964592505, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1785169951,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3517267889, 3369925510,
)

BASE_S_TEMPLATE = '{"monospace":false,"readOnly":false,"noLengthPlugins":false,"installedExtensions":[]}'


def _validate_key(key: Sequence[int]) -> tuple[int, int, int, int]:
    if len(key) != 4:
        raise ValueError("XTEA key must contain exactly 4 words")
    words = tuple(int(w) for w in key)
    if any(w < 0 or w > MAX_UINT32 for w in words):
        raise ValueError("XTEA key words must be within uint32 range")
    return words  # type: ignore[return-value]


def _encrypt_block(block: bytes, key: Sequence[int]) -> bytes:
    if len(block) != 8:
        raise ValueError("XTEA block must be exactly 8 bytes")
    key_words = _validate_key(key)
    left, right = struct.unpack("<2I", block)
    total = 0

    for _ in range(ROUNDS):
        left = (
            left
            + (
                ((((right << 4) & MAX_UINT32) ^ (right >> 5)) + right)
                ^ ((total + key_words[total & 3]) & MAX_UINT32)
            )
        ) & MAX_UINT32
        total = (total + DELTA) & MAX_UINT32
        right = (
            right
            + (
                ((((left << 4) & MAX_UINT32) ^ (left >> 5)) + left)
                ^ ((total + key_words[(total >> 11) & 3]) & MAX_UINT32)
            )
        ) & MAX_UINT32

    return struct.pack("<2I", left, right)


def encrypt_js_text(raw_text: str, key: Sequence[int] = DEFAULT_KEY) -> str:
    """Emulates JS charCodeAt/bit-shift packing and encrypts via XTEA."""
    utf16 = raw_text.encode("utf-16-le", errors="surrogatepass")
    code_units = [
        int.from_bytes(utf16[offset : offset + 2], "little")
        for offset in range(0, len(utf16), 2)
    ]
    if not code_units:
        return ""
    code_units.extend([0] * (-len(code_units) % 8))
    output: list[str] = []

    for offset in range(0, len(code_units), 8):
        words = []
        for word_offset in (0, 4):
            word = 0
            for index in range(4):
                word |= (
                    code_units[offset + word_offset + index] << (index * 8)
                ) & MAX_UINT32
            words.append(word & MAX_UINT32)
        block = struct.pack("<2I", *words)
        output.append(_encrypt_block(block, key).hex())

    return "".join(output)


def encode_field(raw_text: str, field: str, key: Sequence[int] = DEFAULT_KEY) -> str:
    encrypted = encrypt_js_text(raw_text, key)
    if field == "f":
        return f"5.{encrypted}"
    if field == "s":
        return encrypted
    raise ValueError("field must be 'f' or 's'")


def generate_qrator_payload(timestamp: int | None = None) -> dict[str, str]:
    """Generate fresh `f` and `s` tokens for Qrator verification."""
    ts = timestamp if timestamp is not None else int(time.time())
    canvas_hash = MIN_SYNTHETIC_HASH + secrets.randbelow(
        MAX_UINT32 - MIN_SYNTHETIC_HASH + 1
    )

    values = list(BASE_F_TEMPLATE)
    values[CANVAS_HASH_INDEX] = canvas_hash
    values[UNIX_TIME_INDEX] = ts
    raw_f = ";".join(str(v) for v in values)

    return {
        "f": encode_field(raw_f, "f"),
        "s": encode_field(BASE_S_TEMPLATE, "s"),
    }


def build_qrator_multipart(
    f_value: str, s_value: str, boundary: str | None = None
) -> tuple[str, bytes]:
    """Create multipart form payload for /web/2/ft."""
    boundary = boundary or f"{secrets.randbelow(10**16):016d}"
    body = (
        f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="f"'
        f"\r\n\r\n{f_value}"
        f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="s"'
        f"\r\n\r\n{s_value}"
        f"\r\n--{boundary}--\r\n"
    ).encode("ascii")
    return f'multipart/form-data;boundary="{boundary}"', body


def is_qrator_challenge(response: Any) -> bool:
    """Check if the response is a Qrator bot-check page."""
    if response.status_code not in (302, 429):
        return False
    if response.headers.get("server", "").strip().upper() != "QRATOR":
        return False
    text = getattr(response, "text", "") or ""
    has_meta_refresh = bool(re.search(r"<meta\b[^>]*\bhttp-equiv\s*=\s*[\"']refresh[\"']", text, re.I))
    has_script = bool(re.search(r"<script\b[^>]*\bsrc\s*=\s*[\"']/[0-9a-f]{20}\.js[\"']", text, re.I))
    return has_meta_refresh and has_script


def extract_script_url(html: str, base_url: str) -> str:
    matches = re.findall(r"<script\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)[\"']", html, re.I)
    for src in matches:
        full = urljoin(base_url, src)
        parsed = urlsplit(full)
        if re.fullmatch(r"/[0-9a-f]{20}\.js", parsed.path):
            return full
    raise RuntimeError("Qrator fingerprint script not found in HTML")


def run_qrator_flow(session: Any, html: str, page_url: str, base_origin: str = "https://www.avito.ru") -> None:
    """Execute the complete Qrator verification chain."""
    script_url = extract_script_url(html, page_url)
    favicon_url = f"{base_origin}/favicon.ico"
    ft_url = f"{base_origin}/web/2/ft"
    pixel_url = f"{base_origin}/web/1/u"

    start_time = time.monotonic()

    # 1. Load JS script
    session.headers.update({"Referer": page_url, "Sec-Fetch-Dest": "script", "Sec-Fetch-Mode": "no-cors"})
    session.get(script_url, timeout=10)

    # 2. Load favicon
    session.headers.update({"Sec-Fetch-Dest": "image"})
    session.get(favicon_url, timeout=10)

    # 3. Wait meta-refresh delay (~1s)
    remaining = 1.0 - (time.monotonic() - start_time)
    if remaining > 0:
        time.sleep(remaining)

    # 4. Generate payload and post to /ft
    tokens = generate_qrator_payload()
    f_val, s_val = tokens["f"], tokens["s"]

    session.cookies.set("f", f_val, domain=".avito.ru", path="/")
    content_type, body = build_qrator_multipart(f_val, s_val)

    session.headers.update({
        "Origin": base_origin,
        "Referer": page_url,
        "Content-Type": content_type,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
    })
    ft_res = session.post(ft_url, data=body, timeout=10)
    if ft_res.status_code == 200:
        ft_token = ft_res.json()
        if isinstance(ft_token, str):
            session.cookies.set("ft", f'"{ft_token}"', domain=".avito.ru", path="/")

    # 5. Pixel ping
    pixel_id = secrets.randbelow(MAX_UINT32)
    session.headers.update({
        "Content-Type": None,
        "Sec-Fetch-Dest": "image",
        "Sec-Fetch-Mode": "no-cors",
    })
    session.get(f"{pixel_url}?{pixel_id}", timeout=10)
    time.sleep(2.0)
