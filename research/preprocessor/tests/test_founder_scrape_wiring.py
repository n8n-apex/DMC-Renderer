"""Wiring tests for the founder-asset scraper background task on /render.

All NETWORK-FREE. These exercise the `_scrape_founder_and_place` helper
directly (no-op / idempotency / exception-swallowing) and the /render
endpoint scheduling (TestClient + monkeypatched recorder). They do NOT
re-test the scraper itself — the point is the wiring.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import main
from main import _scrape_founder_and_place, app
from settings import Settings


_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "sample_render_request.json"
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def sample_payload() -> dict:
    with _FIXTURE_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _cfg(tmp_path: Path) -> Settings:
    return Settings(client_assets_dir=str(tmp_path / "client_assets"))


# ── _scrape_founder_and_place: no-op when both URLs falsy ────────────────────


@pytest.mark.anyio
async def test_scrape_noop_when_no_founder_urls(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    calls: list = []

    def fake_route(**kwargs):  # pragma: no cover - must never be called
        calls.append(kwargs)
        raise AssertionError("scraper should not run with no founder URLs")

    client_input = SimpleNamespace(
        founder_youtube_url=None, founder_instagram_url=None
    )

    await _scrape_founder_and_place(
        client_input, "acme", cfg, route_fn=fake_route
    )

    assert calls == []
    # Nothing written.
    base = Path(cfg.client_assets_dir)
    assert not base.exists() or not any(base.rglob("*"))


# ── idempotency: existing founder.jpg/team.jpg → skip ────────────────────────


@pytest.mark.anyio
@pytest.mark.parametrize("existing", ["founder.jpg", "team.jpg"])
async def test_scrape_idempotent_skips_when_assets_present(
    tmp_path: Path, existing: str
) -> None:
    cfg = _cfg(tmp_path)
    slug = "acme"
    asset_dir = Path(cfg.client_assets_dir) / slug
    asset_dir.mkdir(parents=True)
    (asset_dir / existing).write_bytes(b"fake")

    calls: list = []

    def fake_route(**kwargs):  # pragma: no cover
        calls.append(kwargs)
        raise AssertionError("scraper should not run when assets already exist")

    client_input = SimpleNamespace(
        founder_youtube_url="https://youtube.com/@x",
        founder_instagram_url=None,
    )

    await _scrape_founder_and_place(
        client_input, slug, cfg, route_fn=fake_route
    )

    assert calls == []
    # Only the pre-existing file remains; nothing new written.
    assert sorted(p.name for p in asset_dir.iterdir()) == [existing]


# ── happy path: scraper is invoked with the expected kwargs ──────────────────


@pytest.mark.anyio
async def test_scrape_invokes_route_fn_with_expected_kwargs(
    tmp_path: Path,
) -> None:
    cfg = _cfg(tmp_path)
    slug = "acme"
    calls: list = []

    async def fake_route(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(flags=["element team: flagged"])

    client_input = SimpleNamespace(
        founder_youtube_url="https://youtube.com/@x",
        founder_instagram_url="https://instagram.com/x",
    )

    await _scrape_founder_and_place(
        client_input, slug, cfg, route_fn=fake_route
    )

    assert len(calls) == 1
    kw = calls[0]
    assert kw["youtube_url"] == "https://youtube.com/@x"
    assert kw["instagram_url"] == "https://instagram.com/x"
    assert kw["founder_id"] == slug
    assert kw["dest_root"] == cfg.client_assets_dir
    assert Path(kw["scratch_dir"]).is_dir()


# ── exception swallowing: a raising scrape must NOT propagate ─────────────────


@pytest.mark.anyio
async def test_scrape_swallows_exceptions(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)

    async def boom(**kwargs):
        raise RuntimeError("network exploded")

    client_input = SimpleNamespace(
        founder_youtube_url="https://youtube.com/@x",
        founder_instagram_url=None,
    )

    # Must not raise.
    await _scrape_founder_and_place(
        client_input, "acme", cfg, route_fn=boom
    )


# ── endpoint wiring: founder URLs present → background task scheduled ─────────


def test_render_schedules_background_task_with_founder_urls(
    client: TestClient, sample_payload: dict, monkeypatch
) -> None:
    recorded: list = []

    async def recorder(client_input, client_slug, cfg, **kwargs):
        recorded.append((client_slug, getattr(client_input, "name", None)))

    monkeypatch.setattr(main, "_scrape_founder_and_place", recorder)

    payload = json.loads(json.dumps(sample_payload))
    payload["client"]["founder_youtube_url"] = "https://youtube.com/@x"

    response = client.post("/render", json=payload)
    assert response.status_code == 200, response.text
    # Response contract unchanged.
    assert response.json()["status"] in ("success", "warn")
    # Background task ran (TestClient executes background tasks synchronously
    # after the response is produced).
    assert len(recorded) == 1
    assert recorded[0][0] == payload["report_json"]["meta"]["client_slug"]


def test_render_no_background_task_without_founder_urls(
    client: TestClient, sample_payload: dict, monkeypatch
) -> None:
    recorded: list = []

    async def recorder(*args, **kwargs):  # pragma: no cover
        recorded.append(args)

    monkeypatch.setattr(main, "_scrape_founder_and_place", recorder)

    payload = json.loads(json.dumps(sample_payload))
    payload["client"].pop("founder_youtube_url", None)
    payload["client"].pop("founder_instagram_url", None)

    response = client.post("/render", json=payload)
    assert response.status_code == 200, response.text
    assert recorded == []
