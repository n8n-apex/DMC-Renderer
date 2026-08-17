from __future__ import annotations
import json
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
CHASSIS_ROOT = HERE.parent
sys.path.insert(0, str(CHASSIS_ROOT))
from package_loader import load_package, LoadedPackage  # noqa: E402
from tokens.compile_tokens import BrandAxes  # noqa: E402

FIXTURE = CHASSIS_ROOT / "fixtures" / "apex"

_BRAND_BLOCK = {
    "brand_primary": "#111", "brand_accent": "#222", "brand_neutral_dark": "#333",
    "brand_neutral_mid": "#444", "brand_neutral_light": "#555", "font_heading": "M",
    "font_body": "S", "qr_target_url": "https://x.de", "company_name_short": "X",
    "company_url_display": "x.de",
}


def _axes_sample() -> dict:
    """A flat brand-token dict (all 10 required keys) for compile_tokens tests."""
    return {
        "brand_primary": "#123456", "brand_accent": "#abcdef",
        "brand_neutral_dark": "#0f0f1f", "brand_neutral_mid": "#7a7a8c",
        "brand_neutral_light": "#fdffff", "font_heading": "Source Sans 3",
        "font_body": "Source Sans 3", "qr_target_url": "https://x.de",
        "company_name_short": "X", "company_url_display": "x.de",
    }


def test_loaded_package_exposes_axes():
    pkg = load_package(FIXTURE)
    assert isinstance(pkg.axes, BrandAxes)
    assert pkg.axes.headline_type == "serif"   # apex's profile (after Task 4 regen)

def test_missing_axes_defaults(tmp_path):
    (tmp_path / "resolved_package.json").write_text(json.dumps({
        "brand": _BRAND_BLOCK, "pages": []}), encoding="utf-8")
    pkg = load_package(tmp_path)
    assert isinstance(pkg.axes, BrandAxes)   # defaults, no crash


# ── NEW: v2.0 7-field top-level axes ──────────────────────────────────────

def test_v2_axes_block_loads_new_fields(tmp_path):
    """A package with a 7-field top-level `axes` block carries palette/qr_enabled/density."""
    pkg_data = {
        "brand": _BRAND_BLOCK,
        "pages": [],
        "axes": {
            "headline_type": "serif",
            "palette": "dual_contrasting",
            "accent_mechanic": "contrasting_hue",
            "texture": "smooth",
            "ground_mode": "light",
            "qr_enabled": True,
            "density": "compact",
        },
    }
    (tmp_path / "resolved_package.json").write_text(json.dumps(pkg_data), encoding="utf-8")
    pkg = load_package(tmp_path)
    assert pkg.axes.palette == "dual_contrasting"
    assert pkg.axes.qr_enabled is True
    assert pkg.axes.density == "compact"


def test_v1_brand_axes_only_loads_with_new_field_defaults(tmp_path):
    """A package with only `brand_axes` (v1 shape) loads 4 fields; new 3 get defaults."""
    pkg_data = {
        "brand": _BRAND_BLOCK,
        "pages": [],
        "brand_axes": {
            "headline_type": "sans",
            "accent_mechanic": "tonal_same_hue",
            "texture": "marble_paper",
            "ground_mode": "dark",
        },
    }
    (tmp_path / "resolved_package.json").write_text(json.dumps(pkg_data), encoding="utf-8")
    pkg = load_package(tmp_path)
    # The 4 original fields are loaded correctly
    assert pkg.axes.headline_type == "sans"
    assert pkg.axes.ground_mode == "dark"
    # The 3 new fields get grammar-neutral defaults (no crash)
    assert pkg.axes.palette == "mono_tonal"
    assert pkg.axes.qr_enabled is False
    assert pkg.axes.density == "balanced"


def test_v2_axes_preferred_over_brand_axes(tmp_path):
    """When both `axes` and `brand_axes` are present, top-level `axes` wins."""
    pkg_data = {
        "brand": _BRAND_BLOCK,
        "pages": [],
        "axes": {
            "headline_type": "serif",
            "palette": "dual_contrasting",
            "accent_mechanic": "contrasting_hue",
            "texture": "smooth",
            "ground_mode": "light",
            "qr_enabled": False,
            "density": "spacious",
        },
        "brand_axes": {
            "headline_type": "sans",
            "accent_mechanic": "tonal_same_hue",
            "texture": "crumpled_paper",
            "ground_mode": "dark",
        },
    }
    (tmp_path / "resolved_package.json").write_text(json.dumps(pkg_data), encoding="utf-8")
    pkg = load_package(tmp_path)
    # top-level axes wins
    assert pkg.axes.headline_type == "serif"
    assert pkg.axes.ground_mode == "light"
    assert pkg.axes.density == "spacious"


def test_density_axis_emitted_as_data_attr():
    from tokens.compile_tokens import compile_tokens, BrandAxes
    from brand_tokens import parse_brand_tokens
    brand = parse_brand_tokens(_axes_sample())
    _, attrs = compile_tokens(brand, BrandAxes(density="compact"))
    assert attrs.get("data-density") == "compact"
