"""Tests for lifespan-pooled httpx client + Settings/job-id wiring."""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

import main
from settings import Settings


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_lifespan_opens_and_exposes_pooled_client() -> None:
    with TestClient(main.app):
        assert isinstance(main.app.state.http_client, httpx.AsyncClient)


def test_get_settings_returns_settings() -> None:
    assert isinstance(main.get_settings(), Settings)


@pytest.mark.anyio
async def test_get_http_client_reads_app_state() -> None:
    sentinel = object()
    fake_request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(http_client=sentinel))
    )
    assert await main.get_http_client(fake_request) is sentinel
