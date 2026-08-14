"""Tests for the shared stamina retry policy."""
from __future__ import annotations

import httpx
import pytest

from resilience import is_retryable_response, retry_http


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_retries_then_succeeds() -> None:
    calls = {"n": 0}

    @retry_http(attempts=3)
    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("boom")
        return "ok"

    assert await flaky() == "ok"
    assert calls["n"] == 3


@pytest.mark.anyio
async def test_gives_up_after_attempts() -> None:
    calls = {"n": 0}

    @retry_http(attempts=2)
    async def always_fail() -> str:
        calls["n"] += 1
        raise httpx.ConnectError("nope")

    with pytest.raises(httpx.ConnectError):
        await always_fail()
    assert calls["n"] == 2


def test_is_retryable_response() -> None:
    assert is_retryable_response(httpx.Response(503))
    assert is_retryable_response(httpx.Response(429))
    assert not is_retryable_response(httpx.Response(200))
    assert not is_retryable_response(httpx.Response(404))
