"""Tests: the fal cache makes an identical second generation free."""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from stages.generate_assets import fal_generate_image

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _transport(counter: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "fal.run" in url:
            counter["posts"] += 1
            return httpx.Response(200, json={"images": [{"url": "https://cdn.test/img.png"}]})
        if "cdn.test" in url:
            return httpx.Response(200, content=_PNG)
        return httpx.Response(404)
    return httpx.MockTransport(handler)


async def _gen(client, out_dir, cache_dir):
    return await fal_generate_image(
        prompt="p", negative_prompt="n", aspect_ratio="1:1", api_key="K", model="m",
        resolution="2K", output_dir=out_dir, slot_id="s", page_slot=1,
        http_client=client, cache_dir=cache_dir,
    )


@pytest.mark.anyio
async def test_second_identical_generation_hits_cache(tmp_path) -> None:
    counter = {"posts": 0}
    client = httpx.AsyncClient(transport=_transport(counter), follow_redirects=True)
    cache = tmp_path / "cache"
    r1 = await _gen(client, tmp_path / "o1", cache)
    r2 = await _gen(client, tmp_path / "o2", cache)
    await client.aclose()
    assert r1.status == "generated" and r2.status == "generated"
    assert counter["posts"] == 1
    assert Path(r2.path).exists()


@pytest.mark.anyio
async def test_no_cache_dir_always_posts(tmp_path) -> None:
    counter = {"posts": 0}
    client = httpx.AsyncClient(transport=_transport(counter), follow_redirects=True)
    await _gen(client, tmp_path / "o1", None)
    await _gen(client, tmp_path / "o2", None)
    await client.aclose()
    assert counter["posts"] == 2
