"""Tests for the 6 design axes: model extensions + the pure resolver."""
from __future__ import annotations

from models import BrandProfile
from models_onboard import VisionAxes


def test_brand_profile_carries_new_axes() -> None:
    bp = BrandProfile(palette="dual_contrasting", qr_enabled=True, density="packed")
    assert bp.palette == "dual_contrasting"
    assert bp.qr_enabled is True
    assert bp.density == "packed"
    assert BrandProfile().palette is None
    assert BrandProfile().qr_enabled is None
    assert BrandProfile().density is None


def test_vision_axes_carries_new_axes() -> None:
    va = VisionAxes(palette="mono_tonal", qr_enabled=False, density="airy")
    assert va.palette == "mono_tonal"
    assert va.qr_enabled is False
    assert va.density == "airy"
    assert VisionAxes().palette is None


from stages.resolve_axes import ResolvedAxes, resolve_axes

_HEADLINE = {"serif", "sans", "sans_allcaps"}
_PALETTE = {"mono_tonal", "dual_contrasting"}
_ACCENT = {"tonal_same_hue", "contrasting_hue"}
_TEXTURE = {"smooth", "marble_paper", "crumpled_paper", "paper_grain", "photo"}
_DENSITY = {"airy", "balanced", "packed"}


def test_defaults_when_no_profile_and_tonal_hexes() -> None:
    axes, prov = resolve_axes(brand_profile=None, brand_primary="#1B3A6B", brand_accent="#2E5BA6")
    assert axes.headline_type == "serif"
    assert axes.texture == "smooth"
    assert axes.density == "balanced"
    assert axes.qr_enabled is False
    assert axes.palette == "mono_tonal"
    assert axes.accent_mechanic == "tonal_same_hue"
    assert prov["headline_type"] == "default"
    assert prov["palette"] == "derived"
    assert prov["qr_enabled"] == "default"


def test_contrasting_hexes_derive_dual_contrasting() -> None:
    axes, prov = resolve_axes(brand_profile=None, brand_primary="#0A1F44", brand_accent="#C8A030")
    assert axes.palette == "dual_contrasting"
    assert axes.accent_mechanic == "contrasting_hue"
    assert prov["palette"] == "derived"


def test_explicit_profile_overrides_derivation() -> None:
    bp = BrandProfile(palette="mono_tonal", accent_mechanic="tonal_same_hue",
                      headline_type="sans_allcaps", texture="marble_paper",
                      density="packed", qr_enabled=True)
    axes, prov = resolve_axes(brand_profile=bp, brand_primary="#0A1F44", brand_accent="#C8A030")
    assert axes.palette == "mono_tonal"
    assert axes.accent_mechanic == "tonal_same_hue"
    assert axes.headline_type == "sans_allcaps"
    assert axes.texture == "marble_paper"
    assert axes.density == "packed"
    assert axes.qr_enabled is True
    assert prov["palette"] == "brand_profile"
    assert prov["headline_type"] == "brand_profile"
    assert prov["qr_enabled"] == "brand_profile"


def test_near_neutral_accent_reads_tonal() -> None:
    axes, _ = resolve_axes(brand_profile=None, brand_primary="#0A1F44", brand_accent="#9A9AA0")
    assert axes.palette == "mono_tonal"
    assert axes.accent_mechanic == "tonal_same_hue"


def test_invalid_profile_value_falls_through_to_default() -> None:
    bp = BrandProfile(headline_type="bogus", density="weird")
    axes, prov = resolve_axes(brand_profile=bp, brand_primary="#1B3A6B", brand_accent="#2E5BA6")
    assert axes.headline_type == "serif"
    assert axes.density == "balanced"
    assert prov["headline_type"] == "default"


def test_every_axis_is_a_valid_literal_for_data_profiles() -> None:
    fixtures = [
        (None, "#1B3A6B", "#2E5BA6"),
        (BrandProfile(headline_type="sans", texture="photo", qr_enabled=True), "#101418", "#2E6BFF"),
        (BrandProfile(headline_type="serif", texture="marble_paper"), "#0A1F44", "#C8A030"),
        (BrandProfile(palette="dual_contrasting", density="airy"), "#0E5C63", "#E0556B"),
    ]
    for bp, p, a in fixtures:
        axes, prov = resolve_axes(brand_profile=bp, brand_primary=p, brand_accent=a)
        assert axes.headline_type in _HEADLINE
        assert axes.palette in _PALETTE
        assert axes.accent_mechanic in _ACCENT
        assert axes.texture in _TEXTURE
        assert axes.density in _DENSITY
        assert isinstance(axes.qr_enabled, bool)
        assert set(prov) == {"headline_type", "palette", "accent_mechanic",
                             "texture", "qr_enabled", "density", "ground_mode"}


def test_ground_mode_resolves_and_defaults() -> None:
    from models import BrandProfile
    bp = BrandProfile(ground_mode="dark")
    axes, prov = resolve_axes(brand_profile=bp, brand_primary="#0A1F44", brand_accent="#C8A030")
    assert axes.ground_mode == "dark"
    assert prov["ground_mode"] == "brand_profile"
    axes2, prov2 = resolve_axes(brand_profile=None, brand_primary="#1B3A6B", brand_accent="#2E5BA6")
    assert axes2.ground_mode == "light"
    assert prov2["ground_mode"] == "default"
    bp3 = BrandProfile(ground_mode="weird")
    axes3, _ = resolve_axes(brand_profile=bp3, brand_primary="#1B3A6B", brand_accent="#2E5BA6")
    assert axes3.ground_mode == "light"
