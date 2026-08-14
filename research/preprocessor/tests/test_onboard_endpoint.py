"""End-to-end test of the /onboard endpoint (pipeline + delivery mocked)."""

from __future__ import annotations

import main
from fastapi.testclient import TestClient
from models import BrandProfile
from models_onboard import OnboardDiagnostics, OnboardResult


def _fake_result(record_id: str) -> OnboardResult:
    return OnboardResult(
        record_id=record_id, job_id="", status="success",
        brand_profile=BrandProfile(brand_primary="#1a2540"),
        diagnostics=OnboardDiagnostics(render_mode="ok", palette_size=4),
    )


def test_onboard_returns_202_with_job_id(monkeypatch) -> None:
    delivered = {}

    async def fake_pipeline(request, **kw):
        return _fake_result(request.record_id)

    async def fake_deliver(result, webhook, output_dir):
        delivered["record_id"] = result.record_id
        delivered["job_id"] = result.job_id
        delivered["webhook"] = webhook

    monkeypatch.setattr(main, "run_onboard_pipeline", fake_pipeline)
    monkeypatch.setattr(main, "_deliver_result", fake_deliver)

    client = TestClient(main.app)
    resp = client.post("/onboard", json={
        "record_id": "recABC", "website_url": "https://x.de",
    })
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["record_id"] == "recABC"
    assert body["job_id"]
    assert delivered["record_id"] == "recABC"
    assert delivered["job_id"] == body["job_id"]


def test_onboard_missing_website_url_returns_422() -> None:
    client = TestClient(main.app)
    resp = client.post("/onboard", json={"record_id": "recABC"})
    assert resp.status_code == 422


def test_deliver_result_posts_then_persists_on_failure(monkeypatch, tmp_path) -> None:
    import asyncio
    import httpx

    calls = {"n": 0}

    async def fake_post(self, url, json=None, **kw):
        calls["n"] += 1
        return httpx.Response(500, text="no")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    result = _fake_result("recX")
    asyncio.run(main._deliver_result(result, "https://hook.test", tmp_path))
    # _WEBHOOK_RETRIES=2 → 1 initial + 2 retries = 3 attempts.
    assert calls["n"] == main._WEBHOOK_RETRIES + 1 == 3
    persisted = tmp_path / "onboard_result.json"
    assert persisted.exists()
