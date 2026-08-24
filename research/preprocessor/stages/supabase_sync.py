"""Weekly Supabase catalog sync — the internally-triggered maintenance job.

The reference catalog (ref_reports / ref_faces) is the AUTHORITATIVE corpus the
Director + QA read from (84 legacy pages + 120 atlas faces joined). It is not
optional decoration: reference selection, format/density weighting, and the
each-client-deck-excluded rule all query these tables. This module makes the
sync happen WITHOUT a human: a background loop inside the app checks the last
successful sync; when >= SYNC_INTERVAL_SECONDS have passed it RE-RUNS the
ingestion + deterministic anatomy re-verification + a storage-object record,
then stamps the last-run time.

Failure discipline: a paused/unreachable Supabase (or a missing DSN) does NOT
fail the render — it WARNS LOUDLY and schedules the next try. No fabrication:
anatomy is derived from each face's ACTUAL PDF page text (deterministic keyword
hints), never invented.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Awaitable, Callable, Optional

import supabase.catalog as _catalog  # module-qualified so tests can patch it

logger = logging.getLogger(__name__)

# Default sync cadence: weekly. Overridable via env (seconds).
SYNC_INTERVAL_SECONDS = int(os.environ.get("SUPABASE_SYNC_INTERVAL_SECONDS", str(7 * 24 * 3600)))
# Health-check cadence: how often the loop re-examines whether the sync is due.
CHECK_INTERVAL_SECONDS = int(os.environ.get("SUPABASE_SYNC_CHECK_SECONDS", str(6 * 3600)))

_LAST_RUN_FILE = Path(__file__).resolve().parent.parent / "var" / "catalog_sync_last.json"

# The repository root (where the six reference source PDFs live).
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

_REF_PDFS: dict[str, str] = {
    "apex": "APEX - KI DMC Report v1 (1).pdf",
    "niklas": "Niklas Niemeyer DMC-Report Druckfertig (1).pdf",
    "buchagentur": "Buchagentur DMC-Report (1).pdf",
    "boss": "DMC-Report Alexander Boss doppelt (1).pdf",
    "werkzeugkoffer": "DMC-Report Mein_Werkzeugkoffer.pdf",
    "aerztepartner": "aerztepartner_v0.2 (1).pdf",
}


def _read_last_run() -> Optional[datetime]:
    try:
        raw = _LAST_RUN_FILE.read_text(encoding="utf-8").strip()
        return datetime.fromisoformat(raw)
    except (OSError, ValueError):
        return None


def _write_last_run(when: datetime) -> None:
    try:
        _LAST_RUN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LAST_RUN_FILE.write_text(when.isoformat(), encoding="utf-8")
    except OSError:
        pass


def pdf_text_provider(deck: str, page_no: int) -> str:
    """Deterministic page-text extractor for the six source decks.

    Reads the deck's source PDF from the repo root; returns the page's text
    (the anatomy hints live here) or "" when the file/page is unavailable —
    the anatomy then keeps its current values (nothing fabricated).
    """
    fname = _REF_PDFS.get(deck)
    if not fname:
        return ""
    path = _REPO_ROOT / fname
    if not path.exists():
        return ""
    try:
        import fitz  # PyMuPDF

        with fitz.open(path) as doc:
            if page_no < 1 or page_no > len(doc):
                return ""
            return doc[page_no - 1].get_text() or ""
    except Exception:
        return ""


def is_due(last: Optional[datetime], now: Optional[datetime] = None) -> bool:
    """True when no successful sync yet, or the last is older than the cadence.
    Deterministic (no clock surprises in tests)."""
    now = now or datetime.now(timezone.utc)
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return now - last >= timedelta(seconds=SYNC_INTERVAL_SECONDS)


async def run_catalog_sync(
    dsn: Optional[str],
    *,
    text_provider: Callable[[str, int], str] = pdf_text_provider,
    project_url: str = "",
    storage_key: str = "",
    verbose: bool = True,
) -> dict:
    """Run the full weekly sync (upsert + anatomy verify + storage record).

    Returns a result dict with a `state` field:
      "ok"            — everything ran and stamped
      "no_dsn"        — no Supabase DSN (LOUD warning; nothing to do)
      "unavailable"   — Supabase unreachable/paused (LOUD warning; retry later)
    Idempotent; never raises.
    """
    if not dsn:
        logger.warning(
            "supabase-sync: SUPABASE_POOLER_URL absent - the reference catalog "
            "stays on the LEGACY 84-page index; selection/QA are degraded until "
            "Supabase is configured."
        )
        return {"state": "no_dsn"}

    try:
        upserted = await _catalog.upsert_catalog(dsn, verbose=verbose)
        verified = await _catalog.verify_and_persist_anatomy(
            dsn, text_provider=text_provider, verbose=verbose,
        )
        storage = {}
        if project_url and storage_key:
            try:
                storage = await _catalog.record_storage_objects(
                    dsn, project_url, storage_key, bucket="references")
            except Exception as _st_exc:  # noqa: BLE001 -- storage is best-effort
                storage = {"error": str(_st_exc)}
        _write_last_run(datetime.now(timezone.utc))
        return {"state": "ok", **upserted, **verified, "storage": storage}
    except Exception as exc:  # noqa: BLE001 -- must be loud, never fatal
        logger.warning(
            "supabase-sync: catalog sync FAILED (project paused or unreachable?) "
            "-> %s. The render continues on the legacy index; next attempt at "
            "the next check interval.", exc,
        )
        return {"state": "unavailable", "error": str(exc)}


async def maybe_sync_catalog(
    dsn: Optional[str],
    *,
    now: Optional[datetime] = None,
    text_provider: Callable[[str, int], str] = pdf_text_provider,
    project_url: str = "",
    storage_key: str = "",
) -> dict:
    """The weekly-trigger decision: run the sync only when due.

    Returns the sync result when it ran; otherwise {"state": "not_due"}.
    """
    last = _read_last_run()
    if not is_due(last, now=now):
        return {"state": "not_due", "last_run": last.isoformat() if last else None}
    return await run_catalog_sync(
        dsn, text_provider=text_provider,
        project_url=project_url, storage_key=storage_key,
    )


async def run_sync_loop(
    dsn_provider: Callable[[], Optional[str]],
    *,
    interval: int = CHECK_INTERVAL_SECONDS,
    text_provider: Callable[[str, int], str] = pdf_text_provider,
    project_url: str = "",
    storage_key: str = "",
) -> None:
    """The background loop: wakes every `interval` seconds and syncs when due.

    Runs forever (the app owns the task); the FIRST wake does a due check so a
    boot catches up after downtime.
    """
    while True:
        try:
            await maybe_sync_catalog(
                dsn_provider(),
                text_provider=text_provider,
                project_url=project_url, storage_key=storage_key,
            )
        except Exception as exc:  # noqa: BLE001 -- the loop must never die
            logger.warning("supabase-sync loop error: %s", exc)
        await asyncio.sleep(interval)


def dsn_from_env() -> Optional[str]:
    return os.environ.get("SUPABASE_POOLER_URL") or None


__all__ = [
    "SYNC_INTERVAL_SECONDS", "CHECK_INTERVAL_SECONDS",
    "is_due", "run_catalog_sync", "maybe_sync_catalog",
    "run_sync_loop", "pdf_text_provider", "dsn_from_env",
]