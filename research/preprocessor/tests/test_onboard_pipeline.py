"""Tests for the onboard pipeline orchestrator."""

from __future__ import annotations

import pytest

from stages.onboard import pipeline as pl
from models_onboard import (
    BrandDesignBrief, CaptureResult, DomSignals, ImageryGuidance,
    OnboardRequest, PaletteColor, PixelPalette,
    VisionAxes, VisionReading, VisionRoleRefs,
)


def _req() -> OnboardRequest:
    return OnboardRequest(record_id="rec1", website_url="https://x.de")


def _stub_brief() -> BrandDesignBrief:
    return BrandDesignBrief(
        visual_style_summary="s", mood=["calm"],
        imagery=ImageryGuidance(style="photographic", subjects="people",
                                treatment="full_bleed", lighting="soft"),
        color_usage="c", shape_language="r", texture_material="m",
        typography_character="t", composition="comp", iconography="ico",
        image_style_prompt="prompt", negative_prompt="neg", confidence=0.8,
    )


@pytest.mark.anyio
async def test_pipeline_happy_path(tmp_path, monkeypatch) -> None:
    async def fake_capture(request, *, output_dir, timeout_ms=30000):
        return CaptureResult(hero_png="h.png", fullpage_png="f.png",
                             raw_dom_eval={"fontHead": "Montserrat"}, status="ok")
    def fake_parse(raw):
        return DomSignals(font_head="Montserrat", font_body="Arial")
    def fake_extract(path, region="hero", max_colors=8):
        return PixelPalette(colors=[PaletteColor(hex="#1a2540", coverage_pct=70, region="hero")],
                            lightest_idx=0, darkest_idx=0)
    async def fake_vision(**kw):
        return VisionReading(role_refs=VisionRoleRefs(primary=0, accent=0),
                             axes=VisionAxes(headline_type="sans"),
                             confidence={"primary": 0.9, "accent": 0.9})

    async def fake_brief(**kw):
        return _stub_brief()

    monkeypatch.setattr(pl, "capture", fake_capture)
    monkeypatch.setattr(pl.dom_extract, "parse", fake_parse)
    monkeypatch.setattr(pl.pixel_palette, "extract_palette", fake_extract)
    monkeypatch.setattr(pl, "read_vision", fake_vision)
    monkeypatch.setattr(pl, "generate_brand_brief", fake_brief)

    result = await pl.run_onboard_pipeline(
        _req(), output_dir=tmp_path, api_key="k", model="m")
    assert result.brand_profile.brand_primary == "#1a2540"
    assert result.brand_profile.headline_type == "sans"
    assert result.diagnostics.render_mode == "ok"
    assert result.diagnostics.vision_model == "m"
    assert "capture" in result.diagnostics.timings_ms


@pytest.mark.anyio
async def test_pipeline_attaches_design_brief(tmp_path, monkeypatch) -> None:
    async def fake_capture(request, *, output_dir, timeout_ms=30000):
        return CaptureResult(hero_png="h.png", fullpage_png="f.png",
                             raw_dom_eval={}, status="ok")
    def fake_parse(raw):
        return DomSignals(font_head="Inter", font_body="Inter")
    def fake_extract(path, region="hero", max_colors=8):
        return PixelPalette(colors=[PaletteColor(hex="#599ab3", coverage_pct=70, region="hero")],
                            lightest_idx=0, darkest_idx=0)
    async def fake_vision(**kw):
        return VisionReading(role_refs=VisionRoleRefs(primary=0),
                             axes=VisionAxes(headline_type="sans"), confidence={})
    async def fake_brief(**kw):
        return _stub_brief()

    monkeypatch.setattr(pl, "capture", fake_capture)
    monkeypatch.setattr(pl.dom_extract, "parse", fake_parse)
    monkeypatch.setattr(pl.pixel_palette, "extract_palette", fake_extract)
    monkeypatch.setattr(pl, "read_vision", fake_vision)
    monkeypatch.setattr(pl, "generate_brand_brief", fake_brief)

    result = await pl.run_onboard_pipeline(
        _req(), output_dir=tmp_path, api_key="k", model="m")
    assert result.design_brief is not None
    assert result.design_brief.imagery.style == "photographic"
    assert "brand_brief" in result.diagnostics.timings_ms


@pytest.mark.anyio
async def test_pipeline_capture_failure_degrades(tmp_path, monkeypatch) -> None:
    async def fake_capture(request, *, output_dir, timeout_ms=30000):
        return CaptureResult(hero_png=None, fullpage_png=None,
                             raw_dom_eval={}, status="nav_error")
    monkeypatch.setattr(pl, "capture", fake_capture)
    async def boom(**kw): raise AssertionError("vision should be skipped")
    monkeypatch.setattr(pl, "read_vision", boom)

    result = await pl.run_onboard_pipeline(
        _req(), output_dir=tmp_path, api_key="k", model="m")
    assert result.status in ("failed", "partial")
    assert result.needs_review is True


@pytest.mark.anyio
async def test_pipeline_unexpected_exception_is_caught(tmp_path, monkeypatch) -> None:
    async def fake_capture(request, *, output_dir, timeout_ms=30000):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(pl, "capture", fake_capture)
    result = await pl.run_onboard_pipeline(
        _req(), output_dir=tmp_path, api_key="k", model="m")
    assert result.status == "failed"
    assert result.needs_review is True


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
