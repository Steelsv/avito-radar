import pytest
from avito_radar.core.qrator import (
    generate_qrator_payload,
    encode_field,
    build_qrator_multipart,
    is_qrator_challenge,
)


def test_encode_field():
    s_encoded = encode_field("{}", "s")
    assert isinstance(s_encoded, str)
    assert len(s_encoded) > 0

    f_encoded = encode_field("1;2;3", "f")
    assert f_encoded.startswith("5.")


def test_generate_qrator_payload():
    payload = generate_qrator_payload(1700000000)
    assert "f" in payload
    assert "s" in payload
    assert payload["f"].startswith("5.")


def test_build_qrator_multipart():
    content_type, body = build_qrator_multipart("5.abc", "def", boundary="1234567812345678")
    assert "boundary=" in content_type
    assert b"1234567812345678" in body
    assert b"5.abc" in body
    assert b"def" in body
