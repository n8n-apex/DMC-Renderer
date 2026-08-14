"""Tests for Stage Onboard-4 — reconcile (pure resolution)."""

from __future__ import annotations

from models_onboard import (
    DomSignals,
    FlatHexFallback,
    OnboardRequest,
    PaletteColor,
    PixelPalette,
    VisionAxes,
    VisionReading,
    VisionRoleRefs,
)
from stages.onboard.reconcile import reconcile


def _palette() -> PixelPalette:
    return PixelPalette(
        colors=[
            PaletteColor(hex="#1a2540", coverage_pct=60.0, region="hero"),  # 0 navy
            PaletteColor(hex="#f5efe3", coverage_pct=25.0, region="hero"),  # 1 cream
            PaletteColor(hex="#e97e47", coverage_pct=15.0, region="hero"),  # 2 coral
        ],
        lightest_idx=1, darkest_idx=0,
    )


def _vision() -> VisionReading:
    return VisionReading(
        role_refs=VisionRoleRefs(primary=0, accent=2, neutral_dark=0,
                                 neutral_mid=None, neutral_light=1),
        axes=VisionAxes(accent_mechanic="contrasting_hue", ground_mode="cool_light",
                        texture="smooth", headline_type="sans"),
        confidence={"primary": 0.95, "accent": 0.9, "neutral_light": 0.8},
    )


def _dom() -> DomSignals:
    return DomSignals(font_head="Montserrat", font_body="Source Sans Pro")


def _req() -> OnboardRequest:
    return OnboardRequest(
        record_id="rec1", website_url="https://x.de",
        flat_hex_fallback=FlatHexFallback(dark="#000", light="#fff", accent="#f00"),
    )


def test_happy_path_uses_vision_plus_pixel() -> None:
    res = reconcile(dom=_dom(), palette=_palette(), vision=_vision(),
                    request=_req(), capture_status="ok")
    bp = res.brand_profile
    assert bp.brand_primary == "#1a2540"
    assert bp.brand_accent == "#e97e47"
    assert bp.brand_neutral_light == "#f5efe3"
    assert bp.font_head == "Montserrat"
    assert bp.font_body == "Source Sans Pro"
    assert bp.accent_mechanic == "contrasting_hue"
    assert bp.headline_type == "sans"
    assert res.provenance["brand_primary"] == "vision_role+pixel"
    assert res.provenance["font_head"] == "dom_token"
    assert res.status == "success"
    assert res.needs_review is False


def test_vision_none_falls_back_to_pixel_heuristics() -> None:
    res = reconcile(dom=_dom(), palette=_palette(), vision=None,
                    request=_req(), capture_status="ok")
    bp = res.brand_profile
    assert bp.brand_primary == "#1a2540"
    assert bp.brand_accent == "#e97e47"
    assert res.provenance["brand_primary"] == "pixel_sample"
    assert res.needs_review is True
    assert res.brand_profile.accent_mechanic is None


def test_no_palette_no_vision_uses_flat_hex() -> None:
    res = reconcile(dom=DomSignals(), palette=PixelPalette(), vision=None,
                    request=_req(), capture_status="spa_blank")
    bp = res.brand_profile
    assert bp.brand_primary == "#000"
    assert bp.brand_accent == "#f00"
    assert bp.brand_neutral_light == "#fff"
    assert res.provenance["brand_primary"] == "flat_hex_fallback"
    assert res.needs_review is True


def test_no_palette_no_flat_hex_uses_default_and_fails() -> None:
    req = OnboardRequest(record_id="r", website_url="https://x.de")
    res = reconcile(dom=DomSignals(), palette=PixelPalette(), vision=None,
                    request=req, capture_status="nav_error")
    assert res.provenance["brand_primary"] == "default"
    assert res.status == "failed"
    assert res.needs_review is True


def test_out_of_range_vision_index_ignored() -> None:
    bad_vision = VisionReading(
        role_refs=VisionRoleRefs(primary=99, accent=2),
        axes=VisionAxes(), confidence={"primary": 0.9, "accent": 0.9},
    )
    res = reconcile(dom=_dom(), palette=_palette(), vision=bad_vision,
                    request=_req(), capture_status="ok")
    assert res.brand_profile.brand_primary == "#1a2540"
    assert res.provenance["brand_primary"] == "pixel_sample"


def test_missing_body_font_flags_review() -> None:
    res = reconcile(dom=DomSignals(font_head="Montserrat", font_body=None),
                    palette=_palette(), vision=_vision(),
                    request=_req(), capture_status="ok")
    assert res.brand_profile.font_body is None
    assert res.needs_review is True
    assert any("font_body" in r for r in res.review_reasons)


def test_pixel_only_accent_differs_from_primary() -> None:
    """When vision is absent and the darkest color is ALSO the most
    saturated, primary and accent must not collide — the accent heuristic
    excludes the chosen primary.
    """
    palette = PixelPalette(
        colors=[
            # dark red: simultaneously darkest AND most saturated
            PaletteColor(hex="#8b0000", coverage_pct=70.0, region="hero"),
            PaletteColor(hex="#ffffff", coverage_pct=30.0, region="hero"),
        ],
        lightest_idx=1, darkest_idx=0,
    )
    res = reconcile(dom=DomSignals(), palette=palette, vision=None,
                    request=_req(), capture_status="ok")
    assert res.brand_profile.brand_primary == "#8b0000"
    assert res.brand_profile.brand_accent != res.brand_profile.brand_primary


def test_brand_axes_palette_qr_density_plumbed_through() -> None:
    """reconcile must pass palette/qr_enabled/density from VisionAxes into
    the resulting BrandProfile — these three §B axes were previously dropped.
    """
    vision = VisionReading(
        role_refs=VisionRoleRefs(primary=0, accent=2, neutral_light=1),
        axes=VisionAxes(
            accent_mechanic="contrasting_hue",
            ground_mode="cool_light",
            texture="smooth",
            headline_type="sans",
            palette="dual_contrasting",
            qr_enabled=True,
            density="packed",
        ),
        confidence={"primary": 0.95, "accent": 0.9, "neutral_light": 0.8},
    )
    res = reconcile(dom=_dom(), palette=_palette(), vision=vision,
                    request=_req(), capture_status="ok")
    bp = res.brand_profile
    assert bp.palette == "dual_contrasting"
    assert bp.qr_enabled is True
    assert bp.density == "packed"
