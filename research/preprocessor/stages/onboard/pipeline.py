"""Onboard orchestrator — runs the 5-layer chain and assembles OnboardResult.

Each layer consumes only the previous layer's typed output. Wrapped so any
unexpected error degrades to a failed-but-valid result (webhook still fires).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import httpx

from models_onboard import OnboardRequest, OnboardResult, PixelPalette
from stages.onboard import dom_extract, pixel_palette
from stages.onboard.brand_brief import generate_brand_brief
from stages.onboard.capture import capture
from stages.onboard.reconcile import reconcile
from stages.onboard.vision_reading import read_vision


async def run_onboard_pipeline(
    request: OnboardRequest,
    *,
    output_dir: Path,
    api_key: Optional[str],
    model: str,
    brief_model: str = "anthropic/claude-opus-4.6",
    http_client: Optional[httpx.AsyncClient] = None,
) -> OnboardResult:
    timings: dict[str, int] = {}

    def _mark(name: str, start: float) -> None:
        timings[name] = int((time.perf_counter() - start) * 1000)

    try:
        t = time.perf_counter()
        cap = await capture(request, output_dir=Path(output_dir))
        _mark("capture", t)

        t = time.perf_counter()
        dom = dom_extract.parse(cap.raw_dom_eval)
        _mark("dom_extract", t)

        t = time.perf_counter()
        palette = (pixel_palette.extract_palette(cap.hero_png, region="hero")
                   if cap.hero_png else PixelPalette())
        _mark("pixel_palette", t)

        t = time.perf_counter()
        vision = None
        if cap.hero_png and api_key:
            vision = await read_vision(
                hero_png=cap.hero_png, fullpage_png=cap.fullpage_png,
                palette=palette, dom=dom, api_key=api_key, model=model,
                http_client=http_client,
            )
        _mark("vision", t)

        result = reconcile(
            dom=dom, palette=palette, vision=vision,
            request=request, capture_status=cap.status,
        )
        # Store screenshot basenames (relative), not absolute server
        # paths — the diagnostics ride in the webhook payload.
        result.diagnostics.screenshots = [
            Path(p).name for p in (cap.hero_png, cap.fullpage_png) if p
        ]
        t = time.perf_counter()
        brief = None
        if cap.hero_png and api_key:
            brief = await generate_brand_brief(
                hero_png=cap.hero_png, fullpage_png=cap.fullpage_png,
                palette=palette, dom=dom, vision=vision,
                api_key=api_key, model=brief_model, http_client=http_client,
            )
        _mark("brand_brief", t)
        result.design_brief = brief
        if brief is None:
            result.needs_review = True
            result.review_reasons.append("design brief unavailable")

        result.diagnostics.timings_ms = timings
        result.diagnostics.vision_model = model if vision is not None else None
        return result

    except Exception as exc:  # last-resort guard — never crash the request
        result = reconcile(
            dom=dom_extract.parse({}), palette=PixelPalette(), vision=None,
            request=request, capture_status="nav_error",
        )
        result.status = "failed"
        result.needs_review = True
        result.review_reasons.append(f"pipeline exception: {exc!s}")
        result.diagnostics.timings_ms = timings
        return result
