"""Tests for Stage 5a — build_image_prompts (batched Sonnet prompt-builder)."""

from __future__ import annotations

import json

import httpx
import pytest

from models import BrandDesignBrief, ImageryGuidance
from stages.build_image_prompts import (
    _build_user_prompt,
    _serialize_brief,
    build_image_prompts,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


def _design_brief() -> BrandDesignBrief:
    return BrandDesignBrief(
        visual_style_summary="x",
        mood=["calm", "premium"],
        imagery=ImageryGuidance(
            style="editorial photography",
            subjects="people at work",
            treatment="muted",
            lighting="soft window light",
            avoid=["clip-art", "stock smiles"],
        ),
        color_usage="navy #1A2540 with coral-free accent #E97E47",
        shape_language="rounded",
        texture_material="STYLE-DNA frosted glass",
        typography_character="x",
        composition="generous negative space",
        iconography="x",
        image_style_prompt="STYLE-DNA-XYZ cyan icy frosted glass aesthetic",
        negative_prompt="warm tones, grunge",
    )


def _specs() -> list[dict]:
    return [
        {"slot_id": "cover_hero", "role": "cover-hero background",
         "aspect_ratio": "3:4", "context": "Cover — Your tax burden is too high"},
        {"slot_id": "status_quo_scene", "role": "status-quo scene",
         "aspect_ratio": "16:9", "context": "Status quo of the market"},
    ]


def _ok_response_json() -> dict:
    content = {
        "prompts": [
            {"slot_id": "cover_hero",
             "prompt": "An uncluttered frosted-glass navy backdrop, lots of negative space",
             "negative_prompt": "text, letters, logos, watermark"},
            {"slot_id": "status_quo_scene",
             "prompt": "A muted editorial office scene in soft window light",
             "negative_prompt": "clip-art, stock smiles"},
        ],
    }
    return {"choices": [{"message": {"content": json.dumps(content)}}]}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# ─────────────────────────────────────────────────────────────────────────────
# Prompt assembly
# ─────────────────────────────────────────────────────────────────────────────


def test_serialize_brief_carries_key_fields() -> None:
    text = _serialize_brief(_design_brief())
    assert "STYLE-DNA-XYZ" in text          # image_style_prompt
    assert "calm" in text and "premium" in text  # mood list
    assert "#1A2540" in text                 # color_usage
    assert "frosted glass" in text           # texture_material
    assert "editorial photography" in text   # imagery.style
    assert "negative space" in text          # composition


def test_user_prompt_carries_brief_and_specs() -> None:
    text = _build_user_prompt(_design_brief(), _specs())
    # Brief content present
    assert "STYLE-DNA-XYZ" in text
    # Each spec carried with slot_id, role, aspect ratio, context
    assert "cover_hero" in text and "3:4" in text
    assert "status_quo_scene" in text and "16:9" in text
    assert "Your tax burden is too high" in text


# ─────────────────────────────────────────────────────────────────────────────
# The batched call
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_build_image_prompts_maps_by_slot_id() -> None:
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_ok_response_json())

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        out = await build_image_prompts(
            design_brief=_design_brief(), asset_specs=_specs(),
            api_key="k", model="anthropic/claude-sonnet-4.6",
            http_client=client,
        )
    assert set(out.keys()) == {"cover_hero", "status_quo_scene"}
    assert out["cover_hero"]["prompt"].startswith("An uncluttered frosted-glass")
    assert out["cover_hero"]["negative_prompt"] == "text, letters, logos, watermark"
    # The request actually carried the brief + specs to the model.
    sent = json.dumps(captured["body"])
    assert "STYLE-DNA-XYZ" in sent
    assert "cover_hero" in sent and "status_quo_scene" in sent


@pytest.mark.anyio
async def test_build_image_prompts_tolerates_whitespace_padding() -> None:
    """OpenRouter prepends keep-alive whitespace; resp.json() must still parse."""
    async def handler(request: httpx.Request) -> httpx.Response:
        body = "\n   \n" + json.dumps(_ok_response_json())
        return httpx.Response(200, content=body.encode())

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        out = await build_image_prompts(
            design_brief=_design_brief(), asset_specs=_specs(),
            api_key="k", model="m", http_client=client,
        )
    assert "cover_hero" in out


@pytest.mark.anyio
async def test_build_image_prompts_500_returns_empty() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        out = await build_image_prompts(
            design_brief=_design_brief(), asset_specs=_specs(),
            api_key="k", model="m", http_client=client,
        )
    assert out == {}


@pytest.mark.anyio
async def test_build_image_prompts_no_key_returns_empty() -> None:
    out = await build_image_prompts(
        design_brief=_design_brief(), asset_specs=_specs(),
        api_key=None, model="m",
    )
    assert out == {}


@pytest.mark.anyio
async def test_build_image_prompts_no_brief_returns_empty() -> None:
    out = await build_image_prompts(
        design_brief=None, asset_specs=_specs(),
        api_key="k", model="m",
    )
    assert out == {}


@pytest.mark.anyio
async def test_build_image_prompts_no_specs_returns_empty() -> None:
    out = await build_image_prompts(
        design_brief=_design_brief(), asset_specs=[],
        api_key="k", model="m",
    )
    assert out == {}


@pytest.mark.anyio
async def test_build_image_prompts_parse_error_returns_empty() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "not json {{"}}]}
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        out = await build_image_prompts(
            design_brief=_design_brief(), asset_specs=_specs(),
            api_key="k", model="m", http_client=client,
        )
    assert out == {}
