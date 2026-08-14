"""Tests for Stage Onboard-1 — dom_extract (pure parser)."""

from __future__ import annotations

from stages.onboard.dom_extract import parse, _to_hex, _first_family


def test_to_hex_rgb() -> None:
    assert _to_hex("rgb(26, 37, 64)") == "#1a2540"


def test_to_hex_rgba() -> None:
    assert _to_hex("rgba(233, 126, 71, 0.8)") == "#e97e47"


def test_to_hex_already_hex() -> None:
    assert _to_hex("#1A2540") == "#1a2540"
    assert _to_hex("#abc") == "#aabbcc"


def test_to_hex_unparseable_returns_none() -> None:
    assert _to_hex("transparent") is None
    assert _to_hex("inherit") is None
    assert _to_hex("") is None


def test_first_family_strips_quotes_and_generics() -> None:
    assert _first_family('"Montserrat", Arial, sans-serif') == "Montserrat"
    assert _first_family("'Source Sans Pro', sans-serif") == "Source Sans Pro"
    assert _first_family("sans-serif") is None
    assert _first_family("") is None


def test_parse_full_signal() -> None:
    raw = {
        "cssVars": {"--brand": "rgb(26,37,64)", "--gap": "16px", "--accent": "#E97E47"},
        "fontHead": '"Montserrat", sans-serif',
        "fontBody": "'Source Sans Pro', Arial, sans-serif",
        "sampledColors": ["rgb(26,37,64)", "#E97E47", "not-a-color"],
        "logoUrl": "https://x.de/logo.svg",
    }
    dom = parse(raw)
    assert dom.css_color_vars == {"--brand": "#1a2540", "--accent": "#e97e47"}
    assert dom.font_head == "Montserrat"
    assert dom.font_body == "Source Sans Pro"
    assert dom.sampled_colors == ["#1a2540", "#e97e47"]
    assert dom.logo_url == "https://x.de/logo.svg"


def test_parse_empty_dict_is_safe() -> None:
    dom = parse({})
    assert dom.font_head is None
    assert dom.css_color_vars == {}
    assert dom.sampled_colors == []
    assert dom.logo_url is None
