"""Tests for classifier.py — the VIS asset-understanding layer (Task 2).

One VIS call per asset returns a structured judgement (role + overlaid-text +
0-3 appeal). It mirrors quality_gate.RealVisionGate's pattern (injectable
client, scripted Fake for tests, fail-closed wrapper) so the unit suite never
touches the network. Brand-agnostic prompt: judge depiction + quality only.
"""
from __future__ import annotations

from stages.scrape_founder_assets.classifier import (
    _CLASSIFY_PROMPT,
    AssetClassifierClient,
    FakeAssetClassifier,
    classify_asset,
)


def test_classify_returns_role_and_appeal():
    fake = FakeAssetClassifier(
        {
            "role": "founder_working",
            "has_overlaid_text": False,
            "visual_appeal": 3,
            "notes": "at a laptop",
        }
    )
    j = classify_asset("/x.jpg", fake)
    assert j.role == "founder_working" and j.visual_appeal == 3
    assert fake.calls == ["/x.jpg"]


def test_classify_fails_closed_on_error():
    class Boom:
        def classify(self, p):
            raise RuntimeError("vision down")

    j = classify_asset("/x.jpg", Boom())
    # never raises, never a confident role
    assert j.role == "other" and j.visual_appeal == 0
    assert "error" in j.notes.lower()


def test_prompt_is_brand_agnostic_and_role_aware():
    p = _CLASSIFY_PROMPT.lower()
    assert "role" in p and "overlaid" in p and "ignore brand" in p
    for r in ("founder_working", "founder_speaking", "content_card"):
        assert r in _CLASSIFY_PROMPT


def test_fake_classifier_by_path_and_sequence():
    by_path = FakeAssetClassifier(
        {
            "/a.jpg": {"role": "founder_portrait", "visual_appeal": 3},
            "/b.jpg": {"role": "content_card", "visual_appeal": 1},
        }
    )
    assert classify_asset("/a.jpg", by_path).role == "founder_portrait"
    assert classify_asset("/b.jpg", by_path).role == "content_card"

    seq = FakeAssetClassifier(
        [
            {"role": "logo", "visual_appeal": 0},
            {"role": "lifestyle", "visual_appeal": 2},
        ]
    )
    assert classify_asset("/x.jpg", seq).role == "logo"
    assert classify_asset("/y.jpg", seq).role == "lifestyle"


def test_protocol_is_runtime_checkable():
    assert isinstance(FakeAssetClassifier({"role": "other"}), AssetClassifierClient)
