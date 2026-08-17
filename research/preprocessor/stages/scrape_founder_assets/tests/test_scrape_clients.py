"""Tests for the founder-asset scraper shared contract: dataclasses,
the ChannelClient protocol, and the FakeChannelClient test double.

Pure (no network). Brand-agnostic.
"""
from __future__ import annotations

import pytest

from stages.scrape_founder_assets.clients import ChannelClient, FakeChannelClient
from stages.scrape_founder_assets.models import Candidate, ScrapeResult


def test_fake_returns_scripted_result():
    cands = [
        Candidate(source="youtube", kind="avatar", local_path="/tmp/a.png", width=800, height=800),
        Candidate(source="youtube", kind="banner", local_path="/tmp/b.png", width=2048, height=1152),
    ]
    fake = FakeChannelClient("youtube", candidates=cands, status="ok")

    result = fake.fetch_candidates("https://x", limit=5)

    assert isinstance(result, ScrapeResult)
    assert result.source == "youtube"
    assert result.status == "ok"
    assert result.candidates == cands
    assert len(result.candidates) == 2
    # call recording
    assert fake.calls == [("https://x", 5)]


def test_scrape_result_shapes():
    c = Candidate(source="instagram", kind="post", local_path="/tmp/p.png", width=1080, height=1080)
    # defaults
    assert c.meta == {}

    r = ScrapeResult(source="instagram", status="ok", candidates=[c])
    assert r.reason is None
    assert r.source == "instagram"
    assert r.candidates == [c]

    # status accepts the 4 values
    for status in ("ok", "blocked", "empty", "error"):
        assert ScrapeResult(source="youtube", status=status, candidates=[]).status == status


def test_fake_can_simulate_block_and_error():
    blocked = FakeChannelClient("instagram", status="blocked", reason="login required")
    bres = blocked.fetch_candidates("https://insta")
    assert bres.status == "blocked"
    assert bres.candidates == []
    assert bres.reason == "login required"
    assert blocked.calls == [("https://insta", 12)]  # default limit

    boom = FakeChannelClient("youtube", raises=RuntimeError("network down"))
    with pytest.raises(RuntimeError):
        boom.fetch_candidates("https://yt")
    # call still recorded before raising
    assert boom.calls == [("https://yt", 12)]


def test_fake_accepts_prebuilt_result():
    pre = ScrapeResult(source="youtube", status="ok", candidates=[])
    fake = FakeChannelClient("youtube", pre)
    assert fake.fetch_candidates("https://yt") is pre


def test_fake_is_a_channel_client():
    fake = FakeChannelClient("youtube", candidates=[], status="empty")
    assert isinstance(fake, ChannelClient)
