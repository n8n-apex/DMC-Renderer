"""Tests for onboard contract models + the extended BrandProfile."""

from __future__ import annotations

from models import BrandDesignBrief, BrandProfile, ClientInput, ImageryGuidance
from models_onboard import (
    CaptureResult,
    DomSignals,
    FlatHexFallback,
    OnboardAccepted,
    OnboardDiagnostics,
    OnboardRequest,
    OnboardResult,
    PaletteColor,
    PixelPalette,
    VisionAxes,
    VisionReading,
    VisionRoleRefs,
)


def test_brand_profile_has_new_perceptual_axes() -> None:
    bp = BrandProfile(
        brand_primary="#1A2540",
        accent_mechanic="contrasting_hue",
        ground_mode="cool_light",
        texture="smooth",
        headline_type="sans",
    )
    assert bp.accent_mechanic == "contrasting_hue"
    assert bp.ground_mode == "cool_light"
    assert bp.texture == "smooth"
    assert bp.headline_type == "sans"


def test_brand_profile_axes_default_none() -> None:
    bp = BrandProfile()
    assert bp.accent_mechanic is None
    assert bp.texture is None


def test_onboard_request_flat_hex_optional() -> None:
    req = OnboardRequest(record_id="rec1", website_url="https://x.de")
    assert req.flat_hex_fallback is None
    assert req.callback_url is None


def test_onboard_request_with_fallback() -> None:
    req = OnboardRequest(
        record_id="rec1",
        website_url="https://x.de",
        flat_hex_fallback=FlatHexFallback(dark="#111", light="#EEE", accent="#F50"),
    )
    assert req.flat_hex_fallback.accent == "#F50"


def test_onboard_result_round_trip() -> None:
    result = OnboardResult(
        record_id="rec1",
        job_id="job1",
        status="success",
        brand_profile=BrandProfile(brand_primary="#1A2540"),
        field_confidence={"brand_primary": 0.9},
        provenance={"brand_primary": "vision_role+pixel"},
        needs_review=False,
        review_reasons=[],
        diagnostics=OnboardDiagnostics(render_mode="ok", palette_size=6),
    )
    dumped = result.model_dump()
    assert dumped["brand_profile"]["brand_primary"] == "#1A2540"
    assert dumped["diagnostics"]["render_mode"] == "ok"


def test_client_input_accepts_design_brief() -> None:
    """ClientInput carries an optional BrandDesignBrief that round-trips."""
    ci = ClientInput(
        name="n", company="c", website_url="u",
        brand_hex_dark="#111", brand_hex_light="#eee", brand_hex_accent="#f50",
        design_brief=BrandDesignBrief(
            visual_style_summary="x",
            imagery=ImageryGuidance(style="x", subjects="x", treatment="x",
                                    lighting="x"),
            color_usage="x",
            shape_language="x",
            texture_material="x",
            typography_character="x",
            composition="x",
            iconography="x",
            image_style_prompt="STYLE-DNA-XYZ",
            negative_prompt="warm tones",
        ),
    )
    assert ci.design_brief is not None
    assert ci.design_brief.image_style_prompt == "STYLE-DNA-XYZ"


def test_client_input_design_brief_optional() -> None:
    """design_brief defaults to None when omitted."""
    ci = ClientInput(
        name="n", company="c", website_url="u",
        brand_hex_dark="#111", brand_hex_light="#eee", brand_hex_accent="#f50",
    )
    assert ci.design_brief is None


def test_internal_contracts_construct() -> None:
    cap = CaptureResult(hero_png="a.png", fullpage_png="b.png",
                         raw_dom_eval={}, status="ok", notes=[])
    dom = DomSignals(css_color_vars={}, font_head=None, font_body=None,
                     sampled_colors=[], logo_url=None)
    pal = PixelPalette(
        colors=[PaletteColor(hex="#1A2540", coverage_pct=70.0, region="hero")],
        lightest_idx=0, darkest_idx=0,
    )
    vr = VisionReading(
        role_refs=VisionRoleRefs(primary=0, accent=None, neutral_dark=None,
                                 neutral_mid=None, neutral_light=None),
        axes=VisionAxes(accent_mechanic="contrasting_hue", ground_mode=None,
                        texture=None, headline_type="sans"),
        confidence={"primary": 0.9}, notes=None,
    )
    assert cap.status == "ok"
    assert dom.font_head is None
    assert pal.colors[0].hex == "#1A2540"
    assert vr.role_refs.primary == 0
