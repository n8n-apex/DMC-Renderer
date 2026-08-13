"""VisualReviewLoopV3: build -> review -> repair -> re-review, fail-closed.

The v3 pipeline used to ship a deck even when the visual reviewer could not
run (an OpenRouter failure became an "other" flag and the PDF was still
returned). This orchestrator makes that impossible: a page is reviewed, a
transient reviewer failure is retried with backoff, a rejected page is
repaired by the conductor and rebuilt, and a deck that still cannot pass
after the whole retry ladder returns REVIEW_REQUIRED with no delivery PDF.

Components reused, not rebuilt: the v3 builder, the conductor's propose/apply
(renderer-fixable knobs), the vision client, and the artifact store. The loop
only decides the visual half of the release state; deterministic hard
failures still keep REJECTED, and ship_ready still requires calibrated human
threshold evidence owned by the existing gate.
"""
from __future__ import annotations

import time
from typing import Any, Callable

TRANSIENT_EXC = (RuntimeError, TimeoutError, ConnectionError)


def retry_transient(
    fn: Callable[..., Any],
    *,
    attempts: int,
    base_delay_s: float = 1.0,
    exc_types: tuple[type, ...] = TRANSIENT_EXC,
) -> Any | None:
    """Call fn up to `attempts` times; exponential backoff between attempts.

    Returns the first successful result, or None after the last failure.
    Non-transient exceptions propagate (a design defect is not retryable).
    """
    for attempt in range(attempts):
        try:
            return fn()
        except exc_types:
            if attempt == attempts - 1:
                return None
            time.sleep(base_delay_s * (2**attempt))
    return None
