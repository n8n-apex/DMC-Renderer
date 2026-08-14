"""Tests for Stage Onboard-6 — brand_brief (OpenRouter Opus call) and the
shared image encoder it shares with vision_reading.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx
import pytest
from PIL import Image

from models_onboard import (
    BrandDesignBrief,
    DomSignals,
    PaletteColor,
    PixelPalette,
    VisionAxes,
    VisionReading,
    VisionRoleRefs,
)
from stages.onboard._imaging import encode_image_data_url
from stages.onboard.brand_brief import (
    _build_user_prompt,
    generate_brand_brief,
)


def _png(tmp_path: Path) -> str:
    p = tmp_path / "hero.png"
    Image.new("RGB", (10, 10), (90, 154, 179)).save(p)
    return str(p)


def _palette() -> PixelPalette:
    return PixelPalette(colors=[
        PaletteColor(hex="#599ab3", coverage_pct=38, region="hero"),
        PaletteColor(hex="#1a2540", coverage_pct=22, region="hero"),
    ], lightest_idx=0, darkest_idx=1)


def _vision() -> VisionReading:
    return VisionReading(
        role_refs=VisionRoleRefs(primary=1, accent=0),
        axes=VisionAxes(accent_mechanic="contrasting_hue", ground_mode="cool_light",
                        texture="smooth", headline_type="sans"),
        confidence={"primary": 0.9},
    )


def _brief_payload() -> dict:
    content = {
        "visual_style_summary": "Calm clinical-tech, lots of whitespace.",
        "mood": ["trustworthy", "calm", "precise"],
        "imagery": {
            "style": "photographic",
            "subjects": "people in soft-lit offices",
            "treatment": "full_bleed",
            "lighting": "soft",
            "avoid": ["harsh shadows", "neon"],
        },
        "color_usage": "Teal #599ab3 as primary fields, navy #1a2540 for type.",
        "shape_language": "Rounded 12px corners, generous gutters.",
        "texture_material": "Matte, faint paper grain.",
        "typography_character": "Humanist sans, medium weight headings.",
        "composition": "Asymmetric grid, left-aligned hero copy.",
        "iconography": "Thin-line 1.5px icons, rounded caps.",
        "image_style_prompt": (
            "Soft-lit photographic style, teal #599ab3 and navy #1a2540 palette, "
            "calm trustworthy mood, matte paper grain, shallow depth of field."
        ),
        "negative_prompt": "neon, harsh shadows, clip-art, lens flare",
        "confidence": 0.82,
    }
    return {"choices": [{"message": {"content": json.dumps(content)}}]}


def test_imaging_encode_downscales_large(tmp_path: Path) -> None:
    """A 1440x9000 PNG is downscaled + JPEG-recompressed under the ~5MB
    provider limit (and smaller than the source)."""
    big = tmp_path / "fullpage.png"
    Image.new("RGB", (1440, 9000), (90, 154, 179)).save(big)
    data_url = encode_image_data_url(str(big))
    assert data_url is not None
    assert data_url.startswith("data:image/jpeg;base64,")
    raw = base64.b64decode(data_url.split(",", 1)[1])
    assert len(raw) < 5 * 1024 * 1024
    assert len(raw) < big.stat().st_size


def test_brand_brief_prompt_carries_palette_fonts_axes() -> None:
    text = _build_user_prompt(
        _palette(), DomSignals(font_head="Inter", font_body="Inter"), _vision()
    )
    assert "#599ab3" in text            # a measured palette hex
    assert "Inter" in text              # resolved heading font
    assert "accent_mechanic=" in text   # designer axes line (vision given)


def test_brand_brief_prompt_omits_axes_without_vision() -> None:
    text = _build_user_prompt(
        _palette(), DomSignals(font_head="Inter"), None
    )
    assert "accent_mechanic=" not in text
    assert "#599ab3" in text


@pytest.mark.anyio
async def test_brand_brief_parses_ok(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_brief_payload())
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        brief = await generate_brand_brief(
            hero_png=_png(tmp_path), fullpage_png=None,
            palette=_palette(), dom=DomSignals(font_head="Inter"),
            vision=_vision(), api_key="k",
            model="anthropic/claude-opus-4.6", http_client=client,
        )
    assert isinstance(brief, BrandDesignBrief)
    assert brief.imagery.style == "photographic"
    assert brief.imagery.treatment == "full_bleed"
    assert "#599ab3" in brief.image_style_prompt
    assert "neon" in brief.negative_prompt
    assert brief.confidence == 0.82


@pytest.mark.anyio
async def test_brand_brief_tolerates_whitespace_padding(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = "\n   \n" + json.dumps(_brief_payload())
        return httpx.Response(200, content=body.encode())
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        brief = await generate_brand_brief(
            hero_png=_png(tmp_path), fullpage_png=None,
            palette=_palette(), dom=DomSignals(), vision=None,
            api_key="k", model="m", http_client=client,
        )
    assert isinstance(brief, BrandDesignBrief)
    assert brief.imagery.lighting == "soft"


@pytest.mark.anyio
async def test_brand_brief_api_error_returns_none(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        brief = await generate_brand_brief(
            hero_png=_png(tmp_path), fullpage_png=None,
            palette=_palette(), dom=DomSignals(), vision=None,
            api_key="k", model="m", http_client=client,
        )
    assert brief is None


@pytest.mark.anyio
async def test_brand_brief_no_key_returns_none(tmp_path: Path) -> None:
    """No api_key → returns None without any HTTP call (a transport that
    fails the test if hit proves no request is made)."""
    async def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no HTTP call should be made without a key")
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        brief = await generate_brand_brief(
            hero_png=_png(tmp_path), fullpage_png=None,
            palette=_palette(), dom=DomSignals(), vision=None,
            api_key=None, model="m", http_client=client,
        )
    assert brief is None


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
