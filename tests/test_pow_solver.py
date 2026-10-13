import base64
import json
import pytest
from avito_radar.core.pow_solver import (
    PowChallenge,
    build_get_payload,
    decode_challenge_jwt,
    find_nonce,
    sha256_hex,
    build_verify_payload,
)


def make_test_jwt(challenge_id: str, complexity: int) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode("ascii").rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"id": challenge_id, "compl": complexity}).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"{header}.{payload}."


def test_decode_challenge_jwt():
    jwt = make_test_jwt("test_ch_123", 2)
    parsed = decode_challenge_jwt(jwt)
    assert parsed.challenge_id == "test_ch_123"
    assert parsed.complexity == 2


def test_find_nonce():
    challenge = PowChallenge(challenge_id="abc", complexity=2)
    nonce = find_nonce(challenge)
    digest = sha256_hex("abc", nonce)
    assert digest.startswith("00")


def test_build_get_payload():
    payload = build_get_payload("my_pow_challenge")
    assert payload == {"challenge": "my_pow_challenge"}


def test_build_verify_payload():
    jwt = make_test_jwt("xyz", 1)
    res = build_verify_payload(jwt)
    assert res["challenge"] == jwt
    assert isinstance(res["nonce"], int)
