"""Tests for package_loader axes handling (addition B: fail loud on the contract
fork). The v2.0 contract carries the 7-field top-level ``axes``; the legacy
4-field ``brand_axes`` is a transitional duplicate. The renderer must NOT silently
fall back to brand_axes (that would default palette/qr_enabled/density and change
the render) -- a brand_axes-only package must fail loud.
"""
import json

import pytest

from package_loader import load_package

# The 10-field brand block parse_brand_tokens requires (values are arbitrary; the
# loader only checks presence/shape, never a client identity).
_BRAND = {
    "brand_primary": "#1A2540",
    "brand_accent": "#E97E47",
    "brand_neutral_dark": "#0F0F1F",
    "brand_neutral_mid": "#7A7A8C",
    "brand_neutral_light": "#F5EFE3",
    "font_heading": "Montserrat",
    "font_body": "Source Sans 3",
    "qr_target_url": "https://example.test",
    "company_name_short": "Example GmbH",
    "company_url_display": "example.test",
}

_AXES7 = {
    "headline_type": "serif", "ground_mode": "light", "texture": "smooth",
    "accent_mechanic": "contrasting_hue", "palette": "dual_contrasting",
    "qr_enabled": False, "density": "balanced",
}
_BRAND_AXES4 = {
    "headline_type": "serif", "ground_mode": "light", "texture": "smooth",
    "accent_mechanic": "contrasting_hue",
}


def _pkg(tmp_path, *, axes=None, brand_axes=None):
    d = tmp_path / "pkg"
    d.mkdir()
    m = {"version": "2.0", "brand": _BRAND, "pages": [],
         "report_assets": [], "fonts": {}}
    if axes is not None:
        m["axes"] = axes
    if brand_axes is not None:
        m["brand_axes"] = brand_axes
    (d / "resolved_package.json").write_text(json.dumps(m), encoding="utf-8")
    return d


def test_loads_seven_field_axes(tmp_path):
    lp = load_package(_pkg(tmp_path, axes=_AXES7))
    assert lp.axes.palette == "dual_contrasting"
    assert lp.axes.density == "balanced"


def test_warns_loud_on_brand_axes_only(tmp_path):
    # Legacy package: 4-field brand_axes, NO v2.0 axes. It still LOADS (v1
    # back-compat is intentional, see test_axes.py), but the silent defaulting of
    # palette/qr_enabled/density is made LOUD via a warning (addition B).
    d = _pkg(tmp_path, brand_axes=_BRAND_AXES4)
    with pytest.warns(UserWarning, match="brand_axes"):
        lp = load_package(d)
    assert lp.axes.headline_type == "serif"   # the 4 fields load
    assert lp.axes.density == "balanced"       # the 3 new fields default


def test_no_axes_block_uses_defaults(tmp_path):
    # A minimal package with no axes info at all keeps the default-axes behavior
    # (the fork fix targets brand_axes-only, not the empty case).
    lp = load_package(_pkg(tmp_path))
    assert lp.axes is not None
