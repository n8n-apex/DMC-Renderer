"""Transient reviewer failures retry with backoff; exhaustion is honest."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from visual_review_loop_v3 import retry_transient  # noqa: E402


def test_retries_transient_failures_with_backoff() -> None:
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient 503")
        return "ok"

    result = retry_transient(flaky, attempts=3, base_delay_s=0.0)
    assert result == "ok"
    assert calls["n"] == 3


def test_exhausted_returns_none_not_raise() -> None:
    def always_fails(*args, **kwargs):
        raise RuntimeError("still down")

    assert retry_transient(always_fails, attempts=3, base_delay_s=0.0) is None


def test_non_transient_exception_propagates() -> None:
    class DesignDefect(ValueError):
        pass

    def bad(*args, **kwargs):
        raise DesignDefect("not a transient failure")

    try:
        retry_transient(bad, attempts=3, base_delay_s=0.0)
    except DesignDefect:
        return
    raise AssertionError("a non-transient exception must propagate, not retry")
