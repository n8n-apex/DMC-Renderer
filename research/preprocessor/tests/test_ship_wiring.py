"""Phase 4b: the live /render `ship` flag triggers the autonomy spine.

Hermetic (no keys, no network, no real render): a fake RenderRunner stands in for
the subprocess so the wiring is proven end to end -- /render builds the package,
the background task renders+grades+gates via the orchestrator, and the
ship-or-escalate outcome is delivered to the webhook. Without the flag, nothing
changes (non-breaking).
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import main
from orchestrator import RenderResult
from settings import Settings

_SAMPLE = Path(__file__).resolve().parent / "fixtures" / "sample_render_request.json"


class _FakeRunner:
    """Stands in for the subprocess renderer: writes a stub PDF + a cleared report."""

    def run(self, package_dir, out_dir):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "report.pdf").write_bytes(b"%PDF-stub")
        report = {
            "deck_cleared": True, "cleared_count": 20, "total": 20,
            "deck_reward": 1_000_000.0, "pages": [],
            "flags_by_owner": {"renderer": [], "preprocessor": [],
                               "asset_gen": [], "other": []},
        }
        return RenderResult(pdf_path=out_dir / "report.pdf",
                            convergence_report=report)


def _hermetic_settings():
    return Settings(_env_file=None, openrouter_api_key=None, fal_key=None)


def _payload(ship: bool):
    p = json.loads(_SAMPLE.read_text(encoding="utf-8"))
    p.setdefault("image_manifest", {})["images"] = []  # no downloads
    if ship:
        p["ship"] = True
        p["ship_webhook"] = "http://hook.test"
    return p


def test_render_ship_flag_renders_grades_and_delivers(monkeypatch):
    posted: list[tuple] = []
    monkeypatch.setattr(main, "_SHIP_RUNNER", _FakeRunner())
    monkeypatch.setattr(main, "_post_webhook_sync",
                        lambda url, payload: posted.append((url, payload)))
    main.app.dependency_overrides[main.get_settings] = _hermetic_settings
    try:
        with TestClient(main.app) as client:
            resp = client.post("/render", json=_payload(ship=True))
        assert resp.status_code == 200, resp.text
    finally:
        main.app.dependency_overrides.clear()

    # The background ship task ran (TestClient awaits it) and delivered the outcome.
    assert posted, "ship task did not deliver to the webhook"
    url, body = posted[0]
    assert url == "http://hook.test"
    assert body["status"] == "shipped"
    assert body["job_id"]  # the record_id correlates the job


def test_render_without_ship_is_unchanged(monkeypatch):
    posted: list = []
    monkeypatch.setattr(main, "_post_webhook_sync",
                        lambda url, payload: posted.append(1))
    main.app.dependency_overrides[main.get_settings] = _hermetic_settings
    try:
        with TestClient(main.app) as client:
            resp = client.post("/render", json=_payload(ship=False))
        assert resp.status_code == 200, resp.text
    finally:
        main.app.dependency_overrides.clear()
    assert posted == []  # no orchestration without the opt-in flag
