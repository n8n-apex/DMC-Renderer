"""Tests for quality_gate.py — the acceptance bar for scraped+restored assets.

A scraped/restored image must pass a VISION quality gate before it can be
accepted into a slot: it has to look like a REAL, SPECIFIC, SHARP photo of
the founder/their business — NOT generic stock, NOT blurry, NOT AI-fake/
"waxy". This mirrors the closed-loop N07 (generic imagery) VIS check.

All tests use a FAKE gate — NO network. The real gate is only exercised for
its construct-without-key / no-network behaviour.
"""
from __future__ import annotations

import pytest

from stages.scrape_founder_assets.quality_gate import (
    _GATE_PROMPT,
    FakeVisionGate,
    RealVisionGate,
    passes_quality,
)


def test_gate_prompt_rejects_overlaid_text_graphics():
    """Guard: the prompt must explicitly reject composited/overlaid text graphics
    (video thumbnails, testimonial cards) while allowing incidental signage.

    This is the load-bearing discrimination verified live; a regression that
    drops it would let sharp title-card thumbnails back into founder slots.
    """
    p = _GATE_PROMPT.lower()
    assert "overlaid" in p
    assert "composited" in p
    assert "thumbnail" in p
    assert "incidental" in p  # real photos with background signage still pass


def test_accepts_passing_image():
    """A specific+sharp+real image is accepted; the call is recorded."""
    gate = FakeVisionGate(
        {"accept": True, "reason": "sharp, specific founder portrait", "score": 3}
    )
    ok, reason = passes_quality("/tmp/founder.jpg", gate)

    assert ok is True
    assert reason == "sharp, specific founder portrait"
    assert gate.calls == ["/tmp/founder.jpg"]


def test_rejects_failing_image():
    """A generic/blurry/fake image is rejected with the gate's reason."""
    gate = FakeVisionGate(
        {"accept": False, "reason": "generic stock photo", "score": 0}
    )
    ok, reason = passes_quality("/tmp/stock.jpg", gate)

    assert ok is False
    assert reason == "generic stock photo"
    assert gate.calls == ["/tmp/stock.jpg"]


def test_fake_gate_sequence_and_by_path():
    """Scripted verdicts can be keyed by path or consumed in sequence."""
    by_path = FakeVisionGate(
        {
            "/a.jpg": {"accept": True, "reason": "real", "score": 3},
            "/b.jpg": {"accept": False, "reason": "waxy", "score": 1},
        }
    )
    assert passes_quality("/a.jpg", by_path) == (True, "real")
    assert passes_quality("/b.jpg", by_path) == (False, "waxy")

    seq = FakeVisionGate(
        [
            {"accept": False, "reason": "blurry", "score": 0},
            {"accept": True, "reason": "sharp", "score": 3},
        ]
    )
    assert passes_quality("/x.jpg", seq) == (False, "blurry")
    assert passes_quality("/y.jpg", seq) == (True, "sharp")


def test_gate_error_fails_closed():
    """If the gate raises, passes_quality fails CLOSED (never accepts, never crashes)."""

    class BoomGate:
        def __init__(self):
            self.calls = []

        def assess(self, image_path):
            self.calls.append(image_path)
            raise RuntimeError("vision backend exploded")

    gate = BoomGate()
    ok, reason = passes_quality("/tmp/x.jpg", gate)

    assert ok is False
    assert "error" in reason.lower()
    assert gate.calls == ["/tmp/x.jpg"]


def test_real_gate_constructs_without_key():
    """RealVisionGate(api_key=None) constructs; assess fails CLOSED w/o key — no network.

    Documented choice: with no API key the real gate does NOT hit the network
    and instead raises a clear RuntimeError naming the missing key. Wrapped by
    passes_quality this becomes a fail-closed (False, "...error...") verdict.
    """
    gate = RealVisionGate(api_key=None)

    with pytest.raises(RuntimeError) as exc:
        gate.assess("/tmp/whatever.jpg")
    assert "key" in str(exc.value).lower()

    # And via passes_quality the same condition fails closed, never raising.
    ok, reason = passes_quality("/tmp/whatever.jpg", gate)
    assert ok is False
    assert "error" in reason.lower()
