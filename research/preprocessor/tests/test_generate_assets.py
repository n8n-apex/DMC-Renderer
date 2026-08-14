"""Tests for Stage 5 — generate_assets (AI asset pipeline)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from stages.generate_assets import (
    AssetPlan,
    AssetResult,
    IMAGE_REQUIREMENTS,
    REPORT_LEVEL_GENERATED,
    download_image,
    generate_assets,
    generate_atmospheric_gradient,
    generate_hero_image,
    generate_texture,
    normalise_gdrive_url,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _full_20_page_plan() -> list[dict]:
    """A 20-page sequence covering every ST type that has image rules."""
    return [
        {"slot": 1,  "type": "ST-01", "data": {"title": "Cover"}},
        {"slot": 2,  "type": "ST-02", "data": {}},
        {"slot": 3,  "type": "ST-05", "data": {}},
        {"slot": 4,  "type": "ST-09", "data": {}},
        {"slot": 5,  "type": "ST-09", "data": {}},
        {"slot": 6,  "type": "ST-14", "data": {}},
        {"slot": 7,  "type": "ST-31", "data": {}},
        {"slot": 8,  "type": "ST-06", "data": {}},
        {"slot": 9,  "type": "ST-22", "data": {}},
        {"slot": 10, "type": "ST-07A", "data": {}},
        {"slot": 11, "type": "ST-07B", "data": {}},
        {"slot": 12, "type": "ST-07A", "data": {}},
        {"slot": 13, "type": "ST-07B", "data": {}},
        {"slot": 14, "type": "ST-32", "data": {}},
        {"slot": 15, "type": "ST-07A", "data": {}},
        {"slot": 16, "type": "ST-07B", "data": {}},
        {"slot": 17, "type": "ST-08", "data": {}},
        {"slot": 18, "type": "ST-22", "data": {}},
        {"slot": 19, "type": "ST-FAZIT", "data": {}},
        {"slot": 20, "type": "ST-03", "data": {}},
    ]


def _run(coro):
    """Synchronous wrapper for async tests."""
    return asyncio.run(coro)


# ─────────────────────────────────────────────────────────────────────────────
# The 10 spec test cases
# ─────────────────────────────────────────────────────────────────────────────


def test_1_inventory_counts_required_images_per_ST_type(tmp_path: Path) -> None:
    """A full 20-page report → total_required matches sum of per-ST
    rules plus the 2 report-level generated assets.
    """
    pages = _full_20_page_plan()
    # Phase 4a moved the human/drive photo slots (ST-05 logo, ST-07A
    # portrait) out of IMAGE_REQUIREMENTS into resolve_slots, and G7 removed
    # the ST-FAZIT background (its closing page grounds on panel_texture; the
    # per-page background had no reader). Only the generate-class page slots
    # contribute: ST-01 cover_hero + the ST-09 scene (×2 pages).
    expected_per_page = (
        len(IMAGE_REQUIREMENTS["ST-01"])     # slot 1
        + len(IMAGE_REQUIREMENTS["ST-09"]) * 2  # slots 4, 5
    )
    expected_total = expected_per_page + len(REPORT_LEVEL_GENERATED)

    plan = _run(generate_assets(
        pages=pages,
        image_manifest={"images": []},
        brand_primary="#1A2540", brand_accent="#E97E47",
        output_dir=tmp_path,
    ))
    assert plan.total_required == expected_total


def test_2_manifest_with_cover_hero_marks_as_downloaded(tmp_path: Path) -> None:
    """If manifest already lists a cover_hero with a URL → Stage 5 marks
    it for download, not generation.
    """
    pages = [{"slot": 1, "type": "ST-01", "data": {"title": "Cover"}}]
    manifest = {
        "images": [
            {
                "id": "img_1",
                "page_slot": 1,
                "page_st_type": "ST-01",
                "image_type": "background",
                "url": "https://example.com/cover.png",
                "status": "generated",
            },
        ],
    }
    # Mock the HTTP layer so no real call goes out
    async def fake_get(self, url):
        return httpx.Response(200, content=b"\x89PNG\r\n\x1a\n_FAKE_")
    with patch("httpx.AsyncClient.get", new=fake_get):
        plan = _run(generate_assets(
            pages=pages,
            image_manifest=manifest,
            brand_primary="#1A2540", brand_accent="#E97E47",
            output_dir=tmp_path,
        ))
    cover_hero = next(a for a in plan.assets if a.slot_id == "cover_hero")
    assert cover_hero.status == "downloaded"
    assert cover_hero.path is not None
    assert cover_hero.path.exists()
    assert cover_hero.path.read_bytes().startswith(b"\x89PNG")


def test_3_download_from_direct_url_writes_file(tmp_path: Path) -> None:
    """download_image() with a mocked 200 response saves the bytes to
    target_path.
    """
    target = tmp_path / "out.png"
    fake_bytes = b"\x89PNG\r\n\x1a\nFAKE_DATA"

    async def fake_get(self, url):
        return httpx.Response(200, content=fake_bytes)

    with patch("httpx.AsyncClient.get", new=fake_get):
        ok = _run(download_image(
            "https://example.com/foo.png", target,
        ))
    assert ok is True
    assert target.exists()
    assert target.read_bytes() == fake_bytes


def test_4_gdrive_url_normalisation() -> None:
    """Drive 'view' URL → uc?export=download URL with the same file ID."""
    cases = [
        (
            "https://drive.google.com/file/d/ABC123XYZ_long-file-id/view",
            "https://drive.google.com/uc?export=download&id=ABC123XYZ_long-file-id",
        ),
        (
            "https://drive.google.com/file/d/FILE_ID_42/view?usp=sharing",
            "https://drive.google.com/uc?export=download&id=FILE_ID_42",
        ),
        (
            "https://drive.google.com/open?id=PQRSTUVWXYZ",
            "https://drive.google.com/uc?export=download&id=PQRSTUVWXYZ",
        ),
        (
            "https://example.com/already-direct.png",
            "https://example.com/already-direct.png",
        ),
    ]
    for inp, expected in cases:
        assert normalise_gdrive_url(inp) == expected, f"failed for {inp}"


def test_5_missing_generate_image_returns_stub(tmp_path: Path) -> None:
    """A page that needs a generate-class image with no manifest entry
    → status = stub_not_generated with an informative message.
    """
    pages = [{"slot": 9, "type": "ST-09", "data": {"title": "Status Quo"}}]
    plan = _run(generate_assets(
        pages=pages,
        image_manifest={"images": []},
        brand_primary="#1A2540", brand_accent="#E97E47",
        output_dir=tmp_path,
    ))
    scene = next(a for a in plan.assets if a.slot_id == "status_quo_scene")
    assert scene.status == "stub_not_generated"
    assert scene.path is None
    assert "stubbed" in scene.message.lower()


def test_6_st05_has_no_per_page_generate_assets(tmp_path: Path) -> None:
    """ST-05 (About) no longer carries any IMAGE_REQUIREMENTS entry: its
    human imagery (founder/logo) is drive-sourced via resolve_slots and
    emitted as per-page `slots[]`, not produced by generate_assets. So an
    ST-05 page contributes NO per-page asset here (only the report-level
    texture/gradient remain).
    """
    pages = [{"slot": 5, "type": "ST-05", "data": {}}]
    plan = _run(generate_assets(
        pages=pages,
        image_manifest={"images": []},
        brand_primary="#1A2540", brand_accent="#E97E47",
        output_dir=tmp_path,
    ))
    per_page = [a for a in plan.assets if a.page_slot is not None]
    assert per_page == []
    # No client-upload path is exercised any more (no client-source specs).
    assert plan.total_client_upload_needed == 0
    assert all(a.slot_id != "about_logo" for a in plan.assets)


def test_7_asset_plan_counts_add_up(tmp_path: Path) -> None:
    """total_required == total_downloaded + total_generated + total_stubbed +
    total_client_upload_needed + total_failed.
    """
    pages = _full_20_page_plan()
    plan = _run(generate_assets(
        pages=pages,
        image_manifest={"images": []},
        brand_primary="#1A2540", brand_accent="#E97E47",
        output_dir=tmp_path,
    ))
    total_counted = (
        plan.total_downloaded
        + plan.total_generated
        + plan.total_stubbed
        + plan.total_client_upload_needed
        + plan.total_failed
    )
    assert plan.total_required == total_counted, (
        f"required={plan.total_required} vs sum={total_counted}; "
        f"d={plan.total_downloaded}, g={plan.total_generated}, "
        f"s={plan.total_stubbed}, "
        f"c={plan.total_client_upload_needed}, f={plan.total_failed}"
    )


def test_8_empty_manifest_stubs_and_client_upload(tmp_path: Path) -> None:
    """With an empty manifest, every generate-class asset is stubbed
    and every client-class asset is client_upload_needed.
    """
    pages = _full_20_page_plan()
    plan = _run(generate_assets(
        pages=pages,
        image_manifest={"images": []},
        brand_primary="#1A2540", brand_accent="#E97E47",
        output_dir=tmp_path,
    ))
    # Every asset must be one of stubbed / client_upload_needed (no
    # downloads possible without a manifest)
    statuses = {a.status for a in plan.assets}
    assert statuses.issubset({"stub_not_generated", "client_upload_needed"})
    assert plan.total_downloaded == 0


def test_9_no_image_requirements_for_unrelated_types(tmp_path: Path) -> None:
    """ST-14 / ST-06 / ST-31 etc. have no image requirements → no
    assets generated for those slots.
    """
    pages = [
        {"slot": 6, "type": "ST-14", "data": {}},
        {"slot": 7, "type": "ST-06", "data": {}},
        {"slot": 8, "type": "ST-31", "data": {}},
        {"slot": 9, "type": "ST-32", "data": {}},
    ]
    plan = _run(generate_assets(
        pages=pages,
        image_manifest={"images": []},
        brand_primary="#1A2540", brand_accent="#E97E47",
        output_dir=tmp_path,
    ))
    # No per-page assets; only the 2 report-level ones
    per_page_assets = [a for a in plan.assets if a.page_slot is not None]
    assert per_page_assets == []
    assert plan.total_required == len(REPORT_LEVEL_GENERATED)


def test_10_texture_and_gradient_stubs_carry_brand_colors() -> None:
    """The texture / gradient stubs include the brand colors in their
    `message` so the wiring is verifiable.
    """
    PRIMARY = "#0F172A"
    ACCENT = "#F59E0B"
    tex = _run(generate_texture(
        texture_class="marble",
        primary_hex=PRIMARY, accent_hex=ACCENT,
    ))
    assert tex.slot_id == "background_texture"
    assert tex.status == "stub_not_generated"
    assert PRIMARY in tex.message
    assert ACCENT in tex.message
    assert "marble" in tex.message

    grad = _run(generate_atmospheric_gradient(
        ground_mode="dark", accent_hex=ACCENT,
    ))
    assert grad.slot_id == "atmospheric_gradient"
    assert grad.status == "stub_not_generated"
    assert ACCENT in grad.message
    assert "dark" in grad.message


# ─────────────────────────────────────────────────────────────────────────────
# Additional coverage
# ─────────────────────────────────────────────────────────────────────────────


def test_download_retries_on_500_then_succeeds(tmp_path: Path) -> None:
    """500 on first attempt, 200 on second → True (file written)."""
    target = tmp_path / "retry.png"
    call_count = {"n": 0}

    async def fake_get(self, url):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return httpx.Response(500, content=b"")
        return httpx.Response(200, content=b"OK_BYTES")

    with patch("httpx.AsyncClient.get", new=fake_get):
        ok = _run(download_image(
            "https://example.com/x.png", target, retries=2,
        ))
    assert ok is True
    assert target.read_bytes() == b"OK_BYTES"
    assert call_count["n"] == 2


def test_download_404_no_retry(tmp_path: Path) -> None:
    """404 is non-retriable → False (no file written)."""
    target = tmp_path / "404.png"
    call_count = {"n": 0}

    async def fake_get(self, url):
        call_count["n"] += 1
        return httpx.Response(404, content=b"")

    with patch("httpx.AsyncClient.get", new=fake_get):
        ok = _run(download_image(
            "https://example.com/x.png", target, retries=3,
        ))
    assert ok is False
    assert not target.exists()
    # 4xx is non-retriable so we should NOT have hit retries=3 times
    assert call_count["n"] == 1


def test_download_failure_marked_failed_with_warning(tmp_path: Path) -> None:
    """If manifest has a URL but the download fails, asset is marked
    failed and a warning is added to the plan.
    """
    pages = [{"slot": 1, "type": "ST-01", "data": {}}]
    manifest = {
        "images": [
            {"id": "x", "page_slot": 1, "page_st_type": "ST-01",
             "image_type": "background", "url": "https://example.com/bad.png",
             "status": "generated"},
        ],
    }

    async def fake_get(self, url):
        return httpx.Response(404, content=b"")

    with patch("httpx.AsyncClient.get", new=fake_get):
        plan = _run(generate_assets(
            pages=pages,
            image_manifest=manifest,
            brand_primary="#1A2540", brand_accent="#E97E47",
            output_dir=tmp_path,
        ))
    cover_hero = next(a for a in plan.assets if a.slot_id == "cover_hero")
    assert cover_hero.status == "failed"
    assert plan.total_failed >= 1
    assert any("failed to download" in w for w in plan.warnings)


def test_pydantic_pages_and_manifest_accepted(tmp_path: Path) -> None:
    """generate_assets handles Pydantic ReportPage + ImageManifest models."""
    from models import ImageManifest, ImageManifestItem, ReportPage
    pages = [ReportPage(slot=1, type="ST-01", data={"title": "x"})]
    manifest = ImageManifest(images=[
        ImageManifestItem(
            id="m1", page_slot=1, page_st_type="ST-01",
            image_type="background", url=None, status="pending",
        ),
    ])
    plan = _run(generate_assets(
        pages=pages,
        image_manifest=manifest,
        brand_primary="#1A2540", brand_accent="#E97E47",
        output_dir=tmp_path,
    ))
    # cover_hero has no URL → stub
    cover_hero = next(a for a in plan.assets if a.slot_id == "cover_hero")
    assert cover_hero.status == "stub_not_generated"


# ─────────────────────────────────────────────────────────────────────────────
# Brief-driven prompts (Stage 5 ← BrandDesignBrief)
# ─────────────────────────────────────────────────────────────────────────────


def _design_brief():
    """A minimal-but-valid BrandDesignBrief carrying a recognisable style
    prompt + negative prompt for assertion.
    """
    from models import BrandDesignBrief, ImageryGuidance
    return BrandDesignBrief(
        visual_style_summary="x",
        imagery=ImageryGuidance(style="x", subjects="x", treatment="x",
                                lighting="x"),
        color_usage="x",
        shape_language="x",
        texture_material="x",
        typography_character="x",
        composition="x",
        iconography="x",
        image_style_prompt="STYLE-DNA-XYZ cyan icy frosted glass",
        negative_prompt="warm tones, grunge",
    )


def test_generators_use_brief_style_prompt(tmp_path: Path) -> None:
    """When a design_brief is supplied, stubbed generators compose their
    `prompt` from the brief's image_style_prompt + subject + aspect, and
    carry the brief's negative_prompt.
    """
    pages = [{"slot": 4, "type": "ST-09", "data": {"title": "Status Quo"}}]
    plan = _run(generate_assets(
        pages=pages,
        image_manifest={"images": []},
        brand_primary="#1A2540", brand_accent="#E97E47",
        design_brief=_design_brief(),
        output_dir=tmp_path,
    ))
    branded = [
        a for a in plan.assets
        if a.prompt and "STYLE-DNA-XYZ" in a.prompt
    ]
    assert branded, "no stubbed asset picked up the brief style prompt"
    a = branded[0]
    assert "STYLE-DNA-XYZ" in a.prompt
    assert "Subject:" in a.prompt
    assert a.negative_prompt == "warm tones, grunge"


def test_generators_fallback_without_brief(tmp_path: Path) -> None:
    """With no design_brief, the generator `prompt` falls back to the
    stub message and `negative_prompt` is None.
    """
    pages = [{"slot": 4, "type": "ST-09", "data": {"title": "Status Quo"}}]
    plan = _run(generate_assets(
        pages=pages,
        image_manifest={"images": []},
        brand_primary="#1A2540", brand_accent="#E97E47",
        design_brief=None,
        output_dir=tmp_path,
    ))
    stubbed = [a for a in plan.assets if a.status == "stub_not_generated"]
    assert stubbed
    a = stubbed[0]
    assert a.prompt is not None and "stubbed" in a.prompt.lower()
    assert a.negative_prompt is None


# ─────────────────────────────────────────────────────────────────────────────
# Two-call pipeline — prompt-builder (Sonnet) + real fal (Nano Banana Pro)
# ─────────────────────────────────────────────────────────────────────────────


import json as _json  # noqa: E402

from stages.generate_assets import fal_generate_image  # noqa: E402


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


_FAKE_PNG = b"\x89PNG\r\n\x1a\n_FAL_FAKE_"


def _prompt_builder_payload(slot_ids: list[str]) -> dict:
    """An OpenRouter chat-completion response carrying one prompt per slot."""
    content = {
        "prompts": [
            {"slot_id": sid,
             "prompt": f"PB-PROMPT for {sid}",
             "negative_prompt": f"PB-NEG for {sid}"}
            for sid in slot_ids
        ]
    }
    return {"choices": [{"message": {"content": _json.dumps(content)}}]}


def _routing_transport(*, fal_status: int = 200,
                       prompt_slots: list[str] | None = None) -> httpx.MockTransport:
    """A MockTransport that routes the three call kinds generate_assets makes:
      - POST openrouter.ai            → prompt-builder JSON
      - POST fal.run/…               → fal generation JSON (or error)
      - GET  (the fal image url)      → the fake PNG bytes
    No real network is ever touched.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if request.method == "POST" and "openrouter.ai" in host:
            return httpx.Response(
                200, json=_prompt_builder_payload(prompt_slots or []))
        if request.method == "POST" and host == "fal.run":
            if fal_status != 200:
                return httpx.Response(fal_status, text="fal boom")
            return httpx.Response(
                200, json={"images": [{"url": "https://cdn.fal.ai/out.png"}],
                           "description": "ok"})
        if request.method == "GET":
            return httpx.Response(200, content=_FAKE_PNG)
        return httpx.Response(404, text="unexpected")
    return httpx.MockTransport(handler)


@pytest.mark.anyio
async def test_fal_generate_image_writes_file(tmp_path: Path) -> None:
    """fal_generate_image: 200 + download → status=generated, PNG on disk,
    prompt/negative recorded, negative folded into the sent prompt text.
    """
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            captured["body"] = _json.loads(request.content)
            captured["auth"] = request.headers.get("Authorization")
            return httpx.Response(
                200, json={"images": [{"url": "https://cdn.fal.ai/x.png"}]})
        return httpx.Response(200, content=_FAKE_PNG)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await fal_generate_image(
            prompt="a calm navy backdrop", negative_prompt="text, logos",
            aspect_ratio="3:4", api_key="FALKEY",
            model="fal-ai/nano-banana-pro", resolution="2K",
            output_dir=tmp_path, slot_id="cover_hero", page_slot=1,
            image_type="background", http_client=client,
        )
    assert result.status == "generated"
    assert result.path is not None and result.path.exists()
    assert result.path.read_bytes().startswith(b"\x89PNG")
    assert result.path.name == "1_cover_hero.png"
    assert result.prompt == "a calm navy backdrop"
    assert result.negative_prompt == "text, logos"
    # fal contract: Key auth, no negative_prompt field, negative folded in.
    assert captured["auth"] == "Key FALKEY"
    body = captured["body"]
    assert "negative_prompt" not in body
    assert body["prompt"] == "a calm navy backdrop\n\nAvoid: text, logos"
    assert body["aspect_ratio"] == "3:4"
    assert body["num_images"] == 1
    assert body["resolution"] == "2K"
    assert body["output_format"] == "png"


@pytest.mark.anyio
async def test_fal_generate_image_non_200_failed(tmp_path: Path) -> None:
    """fal 500 → status=failed, path None, prompt still recorded."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await fal_generate_image(
            prompt="P", negative_prompt="N", aspect_ratio="16:9",
            api_key="K", model="fal-ai/nano-banana-pro", resolution="2K",
            output_dir=tmp_path, slot_id="status_quo_scene", page_slot=4,
            image_type="scene", http_client=client,
        )
    assert result.status == "failed"
    assert result.path is None
    assert result.prompt == "P"
    assert result.negative_prompt == "N"


@pytest.mark.anyio
async def test_fal_report_level_uses_report_prefix(tmp_path: Path) -> None:
    """A report-level asset (page_slot=None) writes report_{slot_id}.png."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(
                200, json={"images": [{"url": "https://cdn.fal.ai/x.png"}]})
        return httpx.Response(200, content=_FAKE_PNG)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await fal_generate_image(
            prompt="P", negative_prompt=None, aspect_ratio="3:4",
            api_key="K", model="fal-ai/nano-banana-pro", resolution="2K",
            output_dir=tmp_path, slot_id="background_texture", page_slot=None,
            image_type="texture", http_client=client,
        )
    assert result.status == "generated"
    assert result.path.name == "report_background_texture.png"


@pytest.mark.anyio
async def test_generate_assets_with_fal_key_generates(tmp_path: Path) -> None:
    """End-to-end (mocked): with openrouter + fal keys, a generate-class
    asset → status=generated, file on disk, the prompt-builder prompt is
    recorded, and total_generated is counted.
    """
    pages = [{"slot": 4, "type": "ST-09", "data": {"title": "Status Quo"}}]
    transport = _routing_transport(
        prompt_slots=["status_quo_scene", "background_texture",
                      "atmospheric_gradient"])
    async with httpx.AsyncClient(transport=transport) as client:
        plan = await generate_assets(
            pages=pages, image_manifest={"images": []},
            brand_primary="#1A2540", brand_accent="#E97E47",
            design_brief=_design_brief(),
            output_dir=tmp_path, http_client=client,
            openrouter_key="ORKEY", fal_key="FALKEY",
        )
    scene = next(a for a in plan.assets if a.slot_id == "status_quo_scene")
    assert scene.status == "generated"
    assert scene.path is not None and scene.path.exists()
    assert scene.path.read_bytes().startswith(b"\x89PNG")
    assert scene.prompt == "PB-PROMPT for status_quo_scene"
    assert scene.negative_prompt == "PB-NEG for status_quo_scene"
    # 1 per-page + 2 report-level generate-class assets all generated.
    assert plan.total_generated == 3
    assert plan.total_stubbed == 0


@pytest.mark.anyio
async def test_generate_assets_fal_500_marks_failed(tmp_path: Path) -> None:
    """fal 500 during a /render-style run → asset failed + warning; the
    other assets are not aborted.
    """
    pages = [{"slot": 4, "type": "ST-09", "data": {"title": "Status Quo"}}]
    transport = _routing_transport(
        fal_status=500,
        prompt_slots=["status_quo_scene", "background_texture",
                      "atmospheric_gradient"])
    async with httpx.AsyncClient(transport=transport) as client:
        plan = await generate_assets(
            pages=pages, image_manifest={"images": []},
            brand_primary="#1A2540", brand_accent="#E97E47",
            design_brief=_design_brief(),
            output_dir=tmp_path, http_client=client,
            openrouter_key="ORKEY", fal_key="FALKEY",
        )
    scene = next(a for a in plan.assets if a.slot_id == "status_quo_scene")
    assert scene.status == "failed"
    # All three generate-class assets failed; none crashed the run.
    assert plan.total_failed == 3
    assert plan.total_generated == 0
    assert any("fal generation failed" in w for w in plan.warnings)
    # The failed asset still carries its built prompt for replay.
    assert scene.prompt == "PB-PROMPT for status_quo_scene"


@pytest.mark.anyio
async def test_generate_assets_no_fal_key_stubs_with_prompt(tmp_path: Path) -> None:
    """With an openrouter key but NO fal key, the built prompt is recorded
    on a stub_not_generated asset — no crash, no generation.
    """
    pages = [{"slot": 4, "type": "ST-09", "data": {"title": "Status Quo"}}]
    transport = _routing_transport(
        prompt_slots=["status_quo_scene", "background_texture",
                      "atmospheric_gradient"])
    async with httpx.AsyncClient(transport=transport) as client:
        plan = await generate_assets(
            pages=pages, image_manifest={"images": []},
            brand_primary="#1A2540", brand_accent="#E97E47",
            design_brief=_design_brief(),
            output_dir=tmp_path, http_client=client,
            openrouter_key="ORKEY", fal_key=None,
        )
    scene = next(a for a in plan.assets if a.slot_id == "status_quo_scene")
    assert scene.status == "stub_not_generated"
    assert scene.path is None
    assert scene.prompt == "PB-PROMPT for status_quo_scene"
    assert scene.negative_prompt == "PB-NEG for status_quo_scene"
    assert plan.total_generated == 0
    assert plan.total_stubbed == 3


@pytest.mark.anyio
async def test_generate_assets_fal_without_promptbuilder_uses_fallback(
    tmp_path: Path,
) -> None:
    """fal key but NO openrouter key → no prompt-builder call; the prompt
    falls back to the brief concatenation and fal still generates.
    """
    pages = [{"slot": 4, "type": "ST-09", "data": {"title": "Status Quo"}}]

    def handler(request: httpx.Request) -> httpx.Response:
        # An openrouter call here would be a bug — fail loudly if attempted.
        assert "openrouter.ai" not in request.url.host, "must not call prompt-builder"
        if request.method == "POST":
            return httpx.Response(
                200, json={"images": [{"url": "https://cdn.fal.ai/x.png"}]})
        return httpx.Response(200, content=_FAKE_PNG)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        plan = await generate_assets(
            pages=pages, image_manifest={"images": []},
            brand_primary="#1A2540", brand_accent="#E97E47",
            design_brief=_design_brief(),
            output_dir=tmp_path, http_client=client,
            openrouter_key=None, fal_key="FALKEY",
        )
    scene = next(a for a in plan.assets if a.slot_id == "status_quo_scene")
    assert scene.status == "generated"
    # Fallback prompt = brief style prompt + subject + aspect.
    assert "STYLE-DNA-XYZ" in scene.prompt
    assert "Subject:" in scene.prompt
    assert scene.negative_prompt == "warm tones, grunge"
    assert plan.total_generated == 3


def test_fallback_prompt_carries_brand_tone() -> None:
    """G19 closure: without a design_brief, the fal fallback prompt still
    names the brand palette (primary + accent hex) so generated imagery is
    brand-tinted, never generic. Deterministic, no fabrication."""
    from stages.generate_assets import _compose_prompt

    out = _compose_prompt(
        None,
        "a seamless abstract surface",
        "A4 portrait",
        fallback="a seamless abstract surface in the brand palette "
                 "primary=#1A2540, accent=#E97E47",
    )
    assert "primary=#1A2540" in out and "accent=#E97E47" in out
    assert "A4 portrait" in out


def test_brief_prompt_wins_over_fallback() -> None:
    """A real style prompt (from an onboarded brief) beats the fallback and
    is composed with subject + aspect."""
    from stages.generate_assets import _compose_prompt

    out = _compose_prompt(
        "Premium glass aesthetic, soft studio light",
        "a seamless abstract surface",
        "A4 portrait",
        fallback="fallback text",
    )
    assert "Premium glass aesthetic" in out
    assert "fallback text" not in out
    assert "Aspect ratio A4 portrait" in out
