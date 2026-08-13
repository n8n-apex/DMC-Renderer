"""Tests: the per-report generation budget caps real fal POSTs (over-budget
specs degrade to stub_not_generated, preserving the counting invariant)."""
from __future__ import annotations

import httpx
import pytest

from stages.generate_assets import generate_assets

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _transport(counter: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "fal.run" in url:
            counter["fal"] += 1
            return httpx.Response(200, json={"images": [{"url": "https://cdn.test/i.png"}]})
        if "cdn.test" in url:
            return httpx.Response(200, content=_PNG)
        return httpx.Response(404)
    return httpx.MockTransport(handler)


_PAGES = [
    {"slot": 1, "type": "ST-01", "data": {"title": "t"}},
    {"slot": 9, "type": "ST-09", "data": {"title": "t"}},
    {"slot": 20, "type": "ST-FAZIT", "data": {"title": "t"}},
]


def _invariant(plan) -> bool:
    return plan.total_required == (
        plan.total_downloaded + plan.total_generated + plan.total_stubbed
        + plan.total_client_upload_needed + plan.total_failed
    )


@pytest.mark.anyio
async def test_budget_caps_real_generations(tmp_path) -> None:
    counter = {"fal": 0}
    client = httpx.AsyncClient(transport=_transport(counter), follow_redirects=True)
    plan = await generate_assets(
        pages=_PAGES, image_manifest={"images": []},
        brand_primary="#111111", brand_accent="#00aaff",
        output_dir=tmp_path, http_client=client,
        fal_key="FALKEY", max_generations_per_report=2,
    )
    await client.aclose()
    assert counter["fal"] == 2
    assert plan.total_generated == 2
    assert plan.total_stubbed >= 2
    assert _invariant(plan)


@pytest.mark.anyio
async def test_no_budget_generates_all(tmp_path) -> None:
    counter = {"fal": 0}
    client = httpx.AsyncClient(transport=_transport(counter), follow_redirects=True)
    plan = await generate_assets(
        pages=_PAGES, image_manifest={"images": []},
        brand_primary="#111111", brand_accent="#00aaff",
        output_dir=tmp_path, http_client=client, fal_key="FALKEY",
    )
    await client.aclose()
    # G7: the ST-FAZIT background slot is removed (its closing page grounds on
    # panel_texture), so the generate set is cover_hero + status_quo_scene +
    # 2 report-level assets = 4, not 5.
    assert counter["fal"] == 4
    assert plan.total_generated == 4
    assert _invariant(plan)


@pytest.mark.anyio
async def test_cache_hit_served_despite_exhausted_budget(tmp_path) -> None:
    """A content-addressed cache hit costs $0, so it must be SERVED even when
    the budget is exhausted — and counted as generated-from-cache, never
    stubbed (PRD §9.3: never re-pay, bounded cost)."""
    cache = tmp_path / "cache"

    # Run 1: no budget, populate the cache. Record the POST count.
    counter = {"fal": 0}
    client = httpx.AsyncClient(transport=_transport(counter), follow_redirects=True)
    plan1 = await generate_assets(
        pages=_PAGES, image_manifest={"images": []},
        brand_primary="#111111", brand_accent="#00aaff",
        output_dir=tmp_path / "run1", http_client=client,
        fal_key="FALKEY", cache_dir=cache,
    )
    await client.aclose()
    full_spec_count = plan1.total_generated
    posts_after_run1 = counter["fal"]
    assert full_spec_count >= 1
    assert posts_after_run1 == full_spec_count  # all real POSTs on the cold run

    # Run 2: SAME cache, budget exhausted (0). Cache hits must still be served.
    client2 = httpx.AsyncClient(transport=_transport(counter), follow_redirects=True)
    plan2 = await generate_assets(
        pages=_PAGES, image_manifest={"images": []},
        brand_primary="#111111", brand_accent="#00aaff",
        output_dir=tmp_path / "run2", http_client=client2,
        fal_key="FALKEY", cache_dir=cache, max_generations_per_report=0,
    )
    await client2.aclose()

    # No NEW fal POSTs on the 2nd run (everything served from cache).
    assert counter["fal"] == posts_after_run1
    # All specs served from cache count as generated, NOT stubbed.
    assert plan2.total_generated == full_spec_count
    assert plan2.total_stubbed == 0
    assert _invariant(plan2)
