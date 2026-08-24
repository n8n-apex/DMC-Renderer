"""Supabase weekly-sync engine — deterministic core tests (no network).

Covers the parts that MUST be provable without touching Supabase: the due
logic, the DSN-absent loud failure mode, the paused/unreachable loud failure
mode, and the manual route wiring (live app, no real DSN expected).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from stages.supabase_sync import (
    SYNC_INTERVAL_SECONDS,
    is_due,
    run_catalog_sync,
    pdf_text_provider,
)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# 1. due logic
# --------------------------------------------------------------------------- #
def test_is_due_when_never_synced():
    assert is_due(None, now=NOW) is True


def test_is_due_false_within_interval():
    fresh = NOW - timedelta(seconds=3600)
    assert is_due(fresh, now=NOW) is False


def test_is_due_true_past_interval():
    old = NOW - timedelta(seconds=SYNC_INTERVAL_SECONDS + 60)
    assert is_due(old, now=NOW) is True


def test_is_due_exactly_interval():
    old = NOW - timedelta(seconds=SYNC_INTERVAL_SECONDS)
    assert is_due(old, now=NOW) is True


# --------------------------------------------------------------------------- #
# 2. loud failure modes (never raise, never fabricate)
# --------------------------------------------------------------------------- #

def test_run_catalog_sync_no_dsn_warns_loudly(caplog):
    res = asyncio.run(run_catalog_sync(None, text_provider=pdf_text_provider, verbose=True))
    assert res["state"] == "no_dsn"
    assert "LEGACY 84-page index" in caplog.text


def test_run_catalog_sync_unreachable_warns_loudly(monkeypatch, caplog):
    async def boom(*args, **kwargs):
        raise ConnectionError("project paused")

    import stages.supabase_sync as ss

    monkeypatch.setattr(ss._catalog, "upsert_catalog", boom)
    res = asyncio.run(run_catalog_sync("postgres://unreachable", verbose=True))
    assert res["state"] == "unavailable"
    assert "error" in res
    assert "paused" in caplog.text or "FAILED" in caplog.text


def test_run_catalog_sync_success_stamps_last_run(monkeypatch, tmp_path):
    import stages.supabase_sync as ss

    calls = {"upsert": 0, "verify": 0}

    async def fake_upsert(dsn, verbose=False):
        calls["upsert"] += 1
        return {"reports": 6, "faces": 200}

    async def fake_verify(dsn, text_provider=None, verbose=False):
        calls["verify"] += 1
        return {"verified": 180}

    monkeypatch.setattr(ss, "_LAST_RUN_FILE", tmp_path / "last.json")
    monkeypatch.setattr(ss._catalog, "upsert_catalog", fake_upsert)
    monkeypatch.setattr(ss._catalog, "verify_and_persist_anatomy", fake_verify)
    res = asyncio.run(run_catalog_sync("postgres://ok", text_provider=lambda d, p: "x"))
    assert res["state"] == "ok"
    assert res["faces"] == 200 and res["verified"] == 180
    assert (tmp_path / "last.json").exists()


# --------------------------------------------------------------------------- #
# 3. text provider honesty — missing deck/file -> "", never crashes
# --------------------------------------------------------------------------- #

def test_pdf_text_provider_unknown_deck():
    assert pdf_text_provider("not-a-deck", 1) == ""


# --------------------------------------------------------------------------- #
# 4. the app route: wired, and safe without a real Supabase
# --------------------------------------------------------------------------- #

def test_sync_catalog_route_registered():
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app) as client:
        r = client.post("/sync-catalog")
        assert r.status_code == 200
        body = r.json()
        # no DSN in the test env -> the honest "no_dsn" state, never an error
        assert body["state"] in ("no_dsn", "unavailable", "ok", "not_due")


def test_health_route_green():
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app) as client:
        assert client.get("/health").json()["status"] == "ok"