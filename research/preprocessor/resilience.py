"""Shared retry policy for flaky external HTTP calls (stamina).

One definition of what is retryable (transport failures + timeouts) and
the backoff (exponential + jitter), so every outbound call in the pipeline
behaves consistently. Applied at each new external call site as it is
built. Pure infrastructure — no client literal.
"""
from __future__ import annotations

import httpx
import stamina

# Transport-level failures + timeouts are always retryable.
RETRYABLE_EXC = (httpx.TransportError, httpx.TimeoutException)


def is_retryable_response(resp: httpx.Response) -> bool:
    """A 5xx / 429 / 408 status is worth retrying; everything else is not."""
    return resp.status_code in (408, 429, 500, 502, 503, 504)


def retry_http(attempts: int = 3, timeout: float = 60.0):
    """Decorator: retry an async coroutine on transport errors / timeouts
    with exponential backoff + jitter.
    """
    return stamina.retry(
        on=RETRYABLE_EXC,
        attempts=attempts,
        timeout=timeout,
        wait_initial=0.5,
        wait_max=8.0,
        wait_jitter=1.0,
    )
