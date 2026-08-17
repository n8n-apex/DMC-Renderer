"""Channel-client contract + a network-free fake.

`ChannelClient` is the protocol every real source adapter (YouTube,
Instagram, ...) implements. `FakeChannelClient` is the test double that
returns a scripted `ScrapeResult` (or raises a scripted exception), so
later selection/gating/orchestrator code is built + tested without
network.

Brand-agnostic: shapes + behaviour only, no client value.
"""
from __future__ import annotations

from typing import List, Optional, Protocol, Tuple, runtime_checkable

from .models import Candidate, ChannelStatus, ScrapeResult


@runtime_checkable
class ChannelClient(Protocol):
    """Fetches candidate images for a single channel URL."""

    def fetch_candidates(self, url: str, *, limit: int = 12) -> ScrapeResult:
        ...


class FakeChannelClient:
    """Scripted, network-free ChannelClient for tests.

    Construct either with a prebuilt result::

        FakeChannelClient("youtube", some_scrape_result)

    or with the parts::

        FakeChannelClient("youtube", candidates=[...], status="ok",
                          reason=None, raises=None)

    If ``raises`` is set, ``fetch_candidates`` records the call then raises
    it (to exercise downstream graceful-handling). Otherwise it returns the
    scripted ScrapeResult. Every call's ``(url, limit)`` is appended to
    ``self.calls``.
    """

    def __init__(
        self,
        source: str,
        result: Optional[ScrapeResult] = None,
        *,
        candidates: Optional[List[Candidate]] = None,
        status: ChannelStatus = "ok",
        reason: Optional[str] = None,
        raises: Optional[BaseException] = None,
    ) -> None:
        self.source = source
        self.raises = raises
        self.calls: List[Tuple[str, int]] = []

        if result is not None:
            self.result: ScrapeResult = result
        else:
            self.result = ScrapeResult(
                source=source,
                status=status,
                candidates=list(candidates or []),
                reason=reason,
            )

    def fetch_candidates(self, url: str, *, limit: int = 12) -> ScrapeResult:
        self.calls.append((url, limit))
        if self.raises is not None:
            raise self.raises
        return self.result
