"""Tests for Stage Onboard-3 — vision_reading (OpenRouter call)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from PIL import Image

from models_onboard import DomSignals, PaletteColor, PixelPalette
from stages.onboard.vision_reading import (
    read_vision,
    _build_palette_prompt,
    _validate_indices,
)
from models_onboard import VisionReading, VisionRoleRefs, VisionAxes


def _png(tmp_path: Path) -> str:
    p = tmp_path / "hero.png"
    Image.new("RGB", (10, 10), (26, 37, 64)).save(p)
    return str(p)


def _palette() -> PixelPalette:
    return PixelPalette(colors=[
        PaletteColor(hex="#1a2540", coverage_pct=60, region="hero"),
        PaletteColor(hex="#e97e47", coverage_pct=20, region="hero"),
    ], lightest_idx=1, darkest_idx=0)


def _ok_response_json() -> dict:
    content = {
        "role_refs": {"primary": 0, "accent": 1, "neutral_dark": 0,
                      "neutral_mid": None, "neutral_light": 1},
        "axes": {"accent_mechanic": "contrasting_hue", "ground_mode": "cool_light",
                 "texture": "smooth", "headline_type": "sans"},
        "confidence": {"primary": 0.95, "accent": 0.9},
        "notes": "navy primary, coral accent",
    }
    return {"choices": [{"message": {"content": json.dumps(content)}}]}


def test_build_palette_prompt_lists_indices() -> None:
    text = _build_palette_prompt(_palette(), DomSignals(font_head="Montserrat"))
    assert "[0]" in text and "#1a2540" in text
    assert "[1]" in text and "#e97e47" in text
    assert "Montserrat" in text


def test_validate_indices_drops_out_of_range() -> None:
    vr = VisionReading(
        role_refs=VisionRoleRefs(primary=0, accent=99),
        axes=VisionAxes(), confidence={},
    )
    cleaned = _validate_indices(vr, palette_len=2)
    assert cleaned.role_refs.primary == 0
    assert cleaned.role_refs.accent is None


@pytest.mark.anyio
async def test_read_vision_parses_ok(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ok_response_json())
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        vr = await read_vision(
            hero_png=_png(tmp_path), fullpage_png=None,
            palette=_palette(), dom=DomSignals(),
            api_key="k", model="anthropic/claude-sonnet-4.6", http_client=client,
        )
    assert vr is not None
    assert vr.role_refs.primary == 0
    assert vr.axes.headline_type == "sans"


@pytest.mark.anyio
async def test_read_vision_api_error_returns_none(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        vr = await read_vision(
            hero_png=_png(tmp_path), fullpage_png=None,
            palette=_palette(), dom=DomSignals(),
            api_key="k", model="m", http_client=client,
        )
    assert vr is None


@pytest.mark.anyio
async def test_read_vision_no_api_key_returns_none(tmp_path: Path) -> None:
    vr = await read_vision(
        hero_png=_png(tmp_path), fullpage_png=None,
        palette=_palette(), dom=DomSignals(), api_key=None, model="m",
    )
    assert vr is None


@pytest.mark.anyio
async def test_read_vision_tolerates_null_confidence(tmp_path: Path) -> None:
    """The model returns null confidence for roles it's unsure about. That
    must NOT sink the whole reading (regression: a null in dict[str, float]
    raised ValidationError → read_vision returned None on real responses).
    """
    content = {
        "role_refs": {"primary": 0, "accent": 1, "neutral_dark": None,
                      "neutral_mid": None, "neutral_light": None},
        "axes": {"accent_mechanic": "tonal_same_hue", "ground_mode": "cool_light",
                 "texture": "smooth", "headline_type": "serif"},
        "confidence": {"primary": 0.7, "accent": 0.6, "neutral_dark": None,
                       "neutral_mid": None, "neutral_light": None},
        "notes": None,
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        # Include OpenRouter's leading keep-alive whitespace padding too.
        body = "\n   \n" + json.dumps(
            {"choices": [{"message": {"content": json.dumps(content)}}]}
        )
        return httpx.Response(200, content=body.encode())
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        vr = await read_vision(
            hero_png=_png(tmp_path), fullpage_png=None,
            palette=_palette(), dom=DomSignals(),
            api_key="k", model="m", http_client=client,
        )
    assert vr is not None
    assert vr.role_refs.primary == 0
    assert vr.confidence["primary"] == 0.7
    assert "neutral_dark" not in vr.confidence  # null dropped, reading kept


@pytest.mark.anyio
async def test_invalid_axis_value_nulled(tmp_path: Path) -> None:
    """An off-vocabulary axis value from the model is nulled, not stored
    verbatim into the profile."""
    content = {
        "role_refs": {"primary": 0, "accent": 1, "neutral_dark": None,
                      "neutral_mid": None, "neutral_light": None},
        "axes": {"accent_mechanic": "contrasting_hue", "ground_mode": None,
                 "texture": "NOT_A_REAL_TEXTURE", "headline_type": "sans"},
        "confidence": {"primary": 0.9},
        "notes": None,
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(content)}}]}
        )
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        vr = await read_vision(
            hero_png=_png(tmp_path), fullpage_png=None,
            palette=_palette(), dom=DomSignals(),
            api_key="k", model="m", http_client=client,
        )
    assert vr is not None
    assert vr.axes.texture is None                        # invalid → nulled
    assert vr.axes.accent_mechanic == "contrasting_hue"   # valid → kept
    assert vr.axes.headline_type == "sans"                # valid → kept


def test_encode_image_downscales_large(tmp_path: Path) -> None:
    """A large full-page screenshot is downscaled + JPEG-recompressed so
    the payload stays under the provider's ~5MB image limit. Regression
    for the live-found bug where a 6.9MB fullpage made Anthropic 400.
    """
    import base64

    from stages.onboard.vision_reading import _encode_image

    big = tmp_path / "fullpage.png"
    Image.new("RGB", (1440, 9000), (90, 154, 179)).save(big)  # tall landing page
    data_url = _encode_image(str(big))
    assert data_url is not None
    assert data_url.startswith("data:image/jpeg;base64,")
    raw = base64.b64decode(data_url.split(",", 1)[1])
    assert len(raw) < 5 * 1024 * 1024          # under Anthropic's ~5MB limit
    assert len(raw) < big.stat().st_size       # smaller than the source PNG


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
