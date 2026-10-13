import pytest
from avito_radar.parsers.url_resolver import (
    parse_link,
    decode_filter_blob,
    transliterate,
    ResolverError,
)


def test_transliterate():
    assert transliterate("Москва") == "moskva"
    assert transliterate("Санкт-Петербург") == "sankt-peterburg"
    assert transliterate("Казань") == "kazan"


def test_parse_link():
    url = "https://www.avito.ru/moskva/telefony/apple/iphone_15-ASgBAgICA0SywA2SoO0RtMANzqs5sMENiPw3"
    parsed = parse_link(url)
    assert parsed.city_slug == "moskva"
    assert parsed.category_slug == "telefony"
    assert parsed.blob.startswith("ASg")


def test_parse_link_invalid():
    with pytest.raises(ResolverError):
        parse_link("https://google.com/search")


def test_decode_filter_blob():
    blob = "ASgBAgICAkSSA8YQygiCWQ"
    pairs = decode_filter_blob(blob)
    assert isinstance(pairs, list)
    assert len(pairs) > 0
    assert all(isinstance(a, int) and isinstance(v, int) for a, v in pairs)
