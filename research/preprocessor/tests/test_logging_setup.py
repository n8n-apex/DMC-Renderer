"""Tests for structlog setup + the job-id contextvar."""
from __future__ import annotations

import logging_setup as ls


def setup_function() -> None:
    ls.clear_job_id()


def test_add_job_id_injects_when_bound() -> None:
    ls.bind_job_id("abc123")
    event = ls._add_job_id(None, "info", {"event": "x"})
    assert event["job_id"] == "abc123"


def test_add_job_id_absent_when_unbound() -> None:
    ls.clear_job_id()
    event = ls._add_job_id(None, "info", {"event": "x"})
    assert "job_id" not in event


def test_configure_is_idempotent() -> None:
    ls.configure_logging()
    ls.configure_logging()  # second call must not raise
    log = ls.get_logger("test")
    assert log is not None


def test_clear_resets_binding() -> None:
    ls.bind_job_id("xyz")
    ls.clear_job_id()
    event = ls._add_job_id(None, "info", {"event": "y"})
    assert "job_id" not in event
