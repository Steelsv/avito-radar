"""Proof-of-Work challenge solver for Avito firewall protection.

Avito uses an SHA-256 Proof-of-Work challenge on HTTP 439 / security checks:
1. Server returns `pow_challenge` (in JSON body or `pow_challenge` cookie).
2. Client POSTs to `/web/3/firewallPow/get` with `{"challenge": pow_challenge}`.
3. Server returns a challenge JWT containing `id` and `compl` (complexity).
4. Client finds a `nonce` integer such that SHA-256(f"{id}:{nonce}") starts with `compl` zeros.
5. Client POSTs to `/web/3/firewallPow/verify` with `{"challenge": challenge_jwt, "nonce": nonce}`.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PowChallenge:
    challenge_id: str
    complexity: int


def build_get_payload(pow_challenge: str) -> dict[str, str]:
    if not isinstance(pow_challenge, str) or not pow_challenge.strip():
        raise ValueError("pow_challenge must be a non-empty string")
    return {"challenge": pow_challenge.strip()}


def decode_challenge_jwt(challenge_jwt: str) -> PowChallenge:
    parts = challenge_jwt.split(".")
    if len(parts) < 2:
        raise ValueError("Invalid JWT: expected at least header and payload segments")

    encoded_payload = parts[1]
    padded_payload = encoded_payload + "=" * (-len(encoded_payload) % 4)
    try:
        raw_payload = base64.urlsafe_b64decode(padded_payload)
        payload: dict[str, Any] = json.loads(raw_payload)
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid JWT payload") from exc

    challenge_id = payload.get("id")
    complexity = payload.get("compl")
    if not isinstance(challenge_id, str) or not isinstance(complexity, int) or complexity < 0:
        raise ValueError("Invalid JWT payload: expected string 'id' and non-negative integer 'compl'")

    return PowChallenge(challenge_id=challenge_id, complexity=complexity)


def sha256_hex(challenge_id: str, nonce: int) -> str:
    candidate = f"{challenge_id}:{nonce}".encode("utf-8")
    return hashlib.sha256(candidate).hexdigest()


def find_nonce(challenge: PowChallenge, *, start: int = 0) -> int:
    target_prefix = "0" * challenge.complexity
    nonce = start
    while not sha256_hex(challenge.challenge_id, nonce).startswith(target_prefix):
        nonce += 1
    return nonce


def build_verify_payload(challenge_jwt: str) -> dict[str, Any]:
    challenge = decode_challenge_jwt(challenge_jwt)
    nonce = find_nonce(challenge)
    return {"challenge": challenge_jwt, "nonce": nonce}
