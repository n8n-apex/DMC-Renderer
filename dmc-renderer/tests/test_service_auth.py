"""G8: every render route requires a shared-secret bearer token."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dmc-renderer"))
sys.path.insert(0, str(ROOT / "dmc-renderer" / "tests"))

from fastapi.testclient import TestClient  # noqa: E402

import service  # noqa: E402


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RENDERER_SHARED_SECRET", "test-secret-value")
    return TestClient(service.app)


def test_health_is_exempt_from_auth(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_render_v3_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/render-v3",
        json={"payload": {}, "images": {}, "brand_tokens": {}},
    )
    assert response.status_code == 401


def test_render_v3_rejects_wrong_token(client: TestClient) -> None:
    response = client.post(
        "/render-v3",
        headers={"Authorization": "Bearer wrong-secret"},
        json={"payload": {}, "images": {}, "brand_tokens": {}},
    )
    assert response.status_code == 401


def test_render_v3_with_valid_token_passes_auth(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Stub the build so the request reaches the handler; the auth gate is what
    # is under test, not the render itself.
    monkeypatch.setattr(service, "build_and_render_v3", lambda body, **_kwargs: {
        "release_state": "rejected",
        "failures": [],
        "hashes": {},
        "face_count": 0,
    })
    response = client.post(
        "/render-v3",
        headers={"Authorization": "Bearer test-secret-value"},
        json={"payload": {"meta": {"report_id": "auth-test", "client_slug": "x", "page_count_target": 20}}, "images": {}, "brand_tokens": {}},
    )
    # 401 would mean auth failed; anything else means the gate let it through
    # (the stubbed handler then produced its own status).
    assert response.status_code != 401


def test_missing_secret_fails_closed(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDERER_SHARED_SECRET", raising=False)
    response = client.post(
        "/render-v3",
        json={"payload": {}, "images": {}, "brand_tokens": {}},
    )
    assert response.status_code == 500
    assert "RENDERER_SHARED_SECRET" in response.text


def test_render_v3_enforces_end_to_end_timeout(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G9: a build that exceeds the cap returns 504, not a hung request."""
    import time

    from test_service_v3 import envelope

    def slow_build(body, **_kwargs):
        time.sleep(5)
        return {"release_state": "rejected", "failures": []}

    monkeypatch.setattr(service, "build_and_render_v3", slow_build)
    monkeypatch.setenv("DMC_RENDER_TIMEOUT_S", "0.05")

    response = client.post(
        "/render-v3",
        headers={"Authorization": "Bearer test-secret-value"},
        json=envelope(),
    )
    assert response.status_code == 504
