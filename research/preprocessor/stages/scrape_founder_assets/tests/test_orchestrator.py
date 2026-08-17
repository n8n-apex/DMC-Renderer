"""Tests for orchestrator.py — the full founder-asset pipeline composition.

Everything is faked / local, NO network:

- channels come from ``FakeChannelClient`` returning scripted ``ScrapeResult``s
  whose candidates point at REAL tmp images (sharp noise), so the real
  selector + restorer run on real bytes.
- face geometry is driven by a stub ``face_detector`` returning scripted
  centered, square boxes (frontal + prominent) — injected into the selector.
- the quality gate is a ``FakeVisionGate`` (scripted accept/reject).
- storage is the REAL ``LocalStorage`` writing under a tmp dest_root.

The orchestrator runs the two channels in PARALLEL (asyncio.gather) with a
per-channel try/except so one failing channel never sinks the other, fills
each slot with the FIRST gate-passing candidate (never fabricating), and
ALWAYS wipes the download scratch in a ``finally``.

Async is driven via ``asyncio.run`` (no pytest-asyncio dependency).
"""
from __future__ import annotations

import asyncio
import functools

import numpy as np
from PIL import Image

from stages.scrape_founder_assets.clients import FakeChannelClient
from stages.scrape_founder_assets.models import Candidate
from stages.scrape_founder_assets.quality_gate import FakeVisionGate
from stages.scrape_founder_assets.storage import LocalStorage
from stages.scrape_founder_assets import selector as selector_module
from stages.scrape_founder_assets.classifier import FakeAssetClassifier
from stages.scrape_founder_assets.orchestrator import (
    FounderAssetResult,
    RouteRunResult,
    SlotOutcome,
    maybe_scrape,
    scrape_founder_assets,
    understand_and_route,
)
from stages.generate_assets import AssetResult

SLOTS = ["founder", "about_portrait", "cover_hero"]


# --- helpers ---------------------------------------------------------------

def _write_noise(path, size=(256, 256), seed=0):
    """High-frequency random noise -> high real-cv2 Laplacian variance (sharp)."""
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 256, size=(size[1], size[0], 3), dtype=np.uint8)
    Image.fromarray(arr).save(path)
    return str(path)


def _candidate(path, source, kind="frame", w=256, h=256):
    return Candidate(source=source, kind=kind, local_path=str(path), width=w, height=h)


def _centered_detector(gray):
    """Stub face_detector: a centered, square (frontal + prominent) box."""
    return [(78, 78, 100, 100)]


def _selector_with_stub_detector():
    """A selector facade matching the module funcs but injecting the stub
    face_detector into ``score_candidate`` so tests need no real face photo."""

    class _Sel:
        score_candidate = staticmethod(
            functools.partial(
                selector_module.score_candidate, face_detector=_centered_detector
            )
        )
        select_for_slots = staticmethod(selector_module.select_for_slots)

    return _Sel()


def _run(coro):
    return asyncio.run(coro)


# --- tests -----------------------------------------------------------------

def test_both_channels_fill_slots(tmp_path):
    """YT + IG return good faced+sharp candidates; gate accepts -> all slots
    filled with committed paths."""
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    dest = tmp_path / "dest"

    yt_img = _write_noise(scratch / "yt.png", seed=1)
    ig_img = _write_noise(scratch / "ig.png", seed=2)

    yt = FakeChannelClient("youtube", candidates=[_candidate(yt_img, "youtube")])
    ig = FakeChannelClient("instagram", candidates=[_candidate(ig_img, "instagram")])

    gate = FakeVisionGate({"accept": True, "reason": "real+sharp", "score": 3})

    result = _run(
        scrape_founder_assets(
            youtube_url="https://youtube.com/@f",
            instagram_url="https://instagram.com/f",
            founder_id="acme",
            slots=SLOTS,
            scratch_dir=str(scratch),
            dest_root=str(dest),
            youtube_client=yt,
            instagram_client=ig,
            selector=_selector_with_stub_detector(),
            gate=gate,
            storage=LocalStorage(str(dest)),
        )
    )

    assert isinstance(result, FounderAssetResult)
    assert result.channel_status["youtube"] == "ok"
    assert result.channel_status["instagram"] == "ok"
    for slot in SLOTS:
        outcome = result.slots[slot]
        assert isinstance(outcome, SlotOutcome)
        assert outcome.status == "filled", f"{slot}: {outcome.reason}"
        assert outcome.path is not None
        # committed under the per-founder namespace, file exists on disk
        assert "client-assets" in outcome.path
        assert "acme" in outcome.path
        import os
        assert os.path.exists(outcome.path)


def test_ig_blocked_still_fills_from_youtube(tmp_path):
    """IG blocked; YT ok -> slots still filled from YT, status reflects blocked,
    a flag notes it, and nothing crashes."""
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    dest = tmp_path / "dest"

    yt_img = _write_noise(scratch / "yt.png", seed=3)
    yt = FakeChannelClient("youtube", candidates=[_candidate(yt_img, "youtube")])
    ig = FakeChannelClient(
        "instagram", candidates=[], status="blocked", reason="login required"
    )

    gate = FakeVisionGate({"accept": True, "reason": "ok", "score": 3})

    result = _run(
        scrape_founder_assets(
            youtube_url="https://youtube.com/@f",
            instagram_url="https://instagram.com/f",
            founder_id="acme",
            slots=SLOTS,
            scratch_dir=str(scratch),
            dest_root=str(dest),
            youtube_client=yt,
            instagram_client=ig,
            selector=_selector_with_stub_detector(),
            gate=gate,
            storage=LocalStorage(str(dest)),
        )
    )

    assert result.channel_status["instagram"] == "blocked"
    assert result.channel_status["youtube"] == "ok"
    for slot in SLOTS:
        assert result.slots[slot].status == "filled"
        assert result.slots[slot].path is not None
    # a human-readable flag mentions the blocked instagram channel
    assert any("instagram" in f.lower() and "blocked" in f.lower() for f in result.flags)


def test_all_fail_gate_flags_never_fabricates(tmp_path):
    """Gate rejects everything -> every slot flagged, path None, reason set;
    no fabricated asset committed."""
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    dest = tmp_path / "dest"

    yt_img = _write_noise(scratch / "yt.png", seed=4)
    ig_img = _write_noise(scratch / "ig.png", seed=5)
    yt = FakeChannelClient("youtube", candidates=[_candidate(yt_img, "youtube")])
    ig = FakeChannelClient("instagram", candidates=[_candidate(ig_img, "instagram")])

    gate = FakeVisionGate({"accept": False, "reason": "looks like stock", "score": 0})

    result = _run(
        scrape_founder_assets(
            youtube_url="https://youtube.com/@f",
            instagram_url="https://instagram.com/f",
            founder_id="acme",
            slots=SLOTS,
            scratch_dir=str(scratch),
            dest_root=str(dest),
            youtube_client=yt,
            instagram_client=ig,
            selector=_selector_with_stub_detector(),
            gate=gate,
            storage=LocalStorage(str(dest)),
        )
    )

    for slot in SLOTS:
        outcome = result.slots[slot]
        assert outcome.status == "flagged"
        assert outcome.path is None
        assert outcome.reason
    # every flagged slot surfaces a flag
    assert all(any(slot in f for f in result.flags) for slot in SLOTS)
    # NEVER fabricated: nothing was committed under the founder namespace
    founder_dir = dest / "client-assets" / "acme"
    assert not founder_dir.exists() or not any(founder_dir.iterdir())


def test_scratch_cleaned_up_always(tmp_path):
    """cleanup_scratch runs (scratch dir gone) on BOTH a success run AND a run
    where a client raised."""
    # 1) success run
    scratch_ok = tmp_path / "scratch_ok"
    scratch_ok.mkdir()
    dest = tmp_path / "dest"
    yt_img = _write_noise(scratch_ok / "yt.png", seed=6)
    yt = FakeChannelClient("youtube", candidates=[_candidate(yt_img, "youtube")])
    gate = FakeVisionGate({"accept": True, "reason": "ok", "score": 3})

    _run(
        scrape_founder_assets(
            youtube_url="https://youtube.com/@f",
            instagram_url=None,
            founder_id="acme",
            slots=SLOTS,
            scratch_dir=str(scratch_ok),
            dest_root=str(dest),
            youtube_client=yt,
            instagram_client=None,
            selector=_selector_with_stub_detector(),
            gate=gate,
            storage=LocalStorage(str(dest)),
        )
    )
    assert not scratch_ok.exists(), "scratch must be wiped after a success run"

    # 2) a client raises -> still wiped
    scratch_err = tmp_path / "scratch_err"
    scratch_err.mkdir()
    raising = FakeChannelClient("youtube", raises=RuntimeError("yt boom"))
    ig_img = _write_noise(scratch_err / "ig.png", seed=7)
    ig = FakeChannelClient("instagram", candidates=[_candidate(ig_img, "instagram")])

    result = _run(
        scrape_founder_assets(
            youtube_url="https://youtube.com/@f",
            instagram_url="https://instagram.com/f",
            founder_id="acme",
            slots=SLOTS,
            scratch_dir=str(scratch_err),
            dest_root=str(dest),
            youtube_client=raising,
            instagram_client=ig,
            selector=_selector_with_stub_detector(),
            gate=gate,
            storage=LocalStorage(str(dest)),
        )
    )
    assert not scratch_err.exists(), "scratch must be wiped even when a client raised"
    # the raising channel is recorded as error; the other still ran
    assert result.channel_status["youtube"] == "error"
    assert result.channel_status["instagram"] == "ok"
    for slot in SLOTS:
        assert result.slots[slot].status == "filled"


def test_distinct_candidates_fill_distinct_slots(tmp_path):
    """With enough distinct passing candidates, de-dup gives each slot a
    DIFFERENT source image (no team+scene-style duplicate)."""
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    dest = tmp_path / "dest"

    imgs = [_write_noise(scratch / f"c{i}.png", seed=10 + i) for i in range(3)]
    yt = FakeChannelClient(
        "youtube", candidates=[_candidate(p, "youtube") for p in imgs]
    )
    gate = FakeVisionGate({"accept": True, "reason": "ok", "score": 3})

    result = _run(
        scrape_founder_assets(
            youtube_url="https://youtube.com/@f",
            instagram_url=None,
            founder_id="acme",
            slots=SLOTS,
            scratch_dir=str(scratch),
            dest_root=str(dest),
            youtube_client=yt,
            instagram_client=None,
            selector=_selector_with_stub_detector(),
            gate=gate,
            storage=LocalStorage(str(dest)),
        )
    )

    paths = [result.slots[s].path for s in SLOTS]
    assert all(p is not None for p in paths)
    # three distinct committed files for three slots
    assert len(set(paths)) == 3, f"expected distinct images per slot, got {paths}"


def test_no_urls_is_noop(tmp_path):
    """maybe_scrape with no founder urls -> empty no-op result, no crash."""

    class _Input:
        founder_youtube_url = None
        founder_instagram_url = None

    result = _run(
        maybe_scrape(
            _Input(),
            founder_id="acme",
            slots=SLOTS,
            scratch_dir=str(tmp_path / "scratch"),
            dest_root=str(tmp_path / "dest"),
        )
    )

    assert isinstance(result, FounderAssetResult)
    assert result.slots == {}
    assert result.flags == []
    assert result.channel_status["youtube"] == "skipped"
    assert result.channel_status["instagram"] == "skipped"


# --- understand_and_route: scrape -> perceive -> classify -> route -> place --

def _big_centered_detector(gray):
    """Stub face_detector: a centered, square (frontal) box for a 1200px image."""
    return [(450, 450, 300, 300)]


def _selector_with_big_detector():
    """Selector facade injecting a stub detector sized for a ~1200px image so the
    real CandidateScore reports a frontal, prominent face."""
    import functools

    class _Sel:
        score_candidate = staticmethod(
            functools.partial(
                selector_module.score_candidate, face_detector=_big_centered_detector
            )
        )
        select_for_slots = staticmethod(selector_module.select_for_slots)

    return _Sel()


def test_understand_and_route_commits_portrait_as_founder(tmp_path):
    """A clean, print-capable, frontal-face image classified founder_portrait ->
    routed to cover_hero -> committed as founder.jpg."""
    scratch = tmp_path / "scratch"; scratch.mkdir()
    dest = tmp_path / "dest"

    # print-capable (long edge >= 1000) sharp noise so the portrait DET passes.
    img = _write_noise(scratch / "p.png", size=(1200, 1200), seed=1)
    yt = FakeChannelClient(
        "youtube", candidates=[_candidate(img, "youtube", w=1200, h=1200)]
    )
    classifier = FakeAssetClassifier(
        {"role": "founder_portrait", "has_overlaid_text": False,
         "visual_appeal": 3, "notes": "clean portrait"}
    )

    result = _run(
        understand_and_route(
            youtube_url="https://youtube.com/@f",
            instagram_url=None,
            founder_id="acme",
            scratch_dir=str(scratch),
            dest_root=str(dest),
            youtube_client=yt,
            instagram_client=None,
            classifier=classifier,
            selector=_selector_with_big_detector(),
            storage=LocalStorage(str(dest)),
        )
    )

    assert isinstance(result, RouteRunResult)
    by_el = {r.element: r for r in result.routed}
    assert by_el["cover_hero"].status == "filled"
    assert by_el["cover_hero"].role == "founder_portrait"

    # founder.jpg landed in the per-founder client_assets dir the resolver reads
    founder_dir = dest / "acme"
    names = sorted(p.name for p in founder_dir.iterdir())
    assert "founder.png" in names or "founder.jpg" in names
    assert "cover_hero" in result.placed


def test_understand_and_route_working_photo_becomes_device_asset(tmp_path):
    """A founder_working photo -> device_mockup element -> emitted as an
    AssetResult with image_type 'device' (NOT a drive file)."""
    scratch = tmp_path / "scratch"; scratch.mkdir()
    dest = tmp_path / "dest"

    img = _write_noise(scratch / "w.png", size=(1200, 800), seed=2)
    yt = FakeChannelClient(
        "youtube", candidates=[_candidate(img, "youtube", w=1200, h=800)]
    )
    classifier = FakeAssetClassifier(
        {"role": "founder_working", "has_overlaid_text": False,
         "visual_appeal": 3, "notes": "at a laptop"}
    )

    result = _run(
        understand_and_route(
            youtube_url="https://youtube.com/@f",
            instagram_url=None,
            founder_id="acme",
            scratch_dir=str(scratch),
            dest_root=str(dest),
            youtube_client=yt,
            instagram_client=None,
            classifier=classifier,
            selector=_selector_with_big_detector(),
            storage=LocalStorage(str(dest)),
        )
    )

    by_el = {r.element: r for r in result.routed}
    assert by_el["device_mockup"].status == "filled"

    assert len(result.device_assets) == 1
    dev = result.device_assets[0]
    assert isinstance(dev, AssetResult)
    assert dev.slot_id == "device_mockup"
    assert dev.image_type == "device"
    assert dev.status in ("resolved", "generated")
    assert str(dev.path) == str(by_el["device_mockup"].path)
    # device_mockup is NOT a drive file -> not in placed
    assert "device_mockup" not in result.placed


def test_understand_and_route_all_cards_flags_never_fabricates(tmp_path):
    """A pool of only content_card assets: portrait/team/device flagged (never
    fabricated); proof is filled from the cards."""
    scratch = tmp_path / "scratch"; scratch.mkdir()
    dest = tmp_path / "dest"

    imgs = [_write_noise(scratch / f"c{i}.png", size=(1200, 1200), seed=20 + i)
            for i in range(3)]
    yt = FakeChannelClient(
        "youtube",
        candidates=[_candidate(p, "youtube", w=1200, h=1200) for p in imgs],
    )
    classifier = FakeAssetClassifier(
        {"role": "content_card", "has_overlaid_text": True,
         "visual_appeal": 2, "notes": "designed card"}
    )

    result = _run(
        understand_and_route(
            youtube_url="https://youtube.com/@f",
            instagram_url=None,
            founder_id="acme",
            scratch_dir=str(scratch),
            dest_root=str(dest),
            youtube_client=yt,
            instagram_client=None,
            classifier=classifier,
            selector=_selector_with_big_detector(),
            storage=LocalStorage(str(dest)),
        )
    )

    by_el = {r.element: r for r in result.routed}
    # face/working elements with no suitable asset are FLAGGED, never faked
    assert by_el["cover_hero"].status == "flagged"
    assert by_el["team"].status == "flagged"
    assert by_el["device_mockup"].status == "flagged"
    # proof IS filled from the content cards
    assert by_el["proof"].status == "filled"
    # no founder/team drive file fabricated
    founder_dir = dest / "acme"
    names = sorted(p.name for p in founder_dir.iterdir()) if founder_dir.exists() else []
    assert "founder.png" not in names and "founder.jpg" not in names
    assert "team.png" not in names and "team.jpg" not in names
    # no fabricated device asset
    assert result.device_assets == []


def test_understand_and_route_cleans_scratch_always(tmp_path):
    """Scratch dir is wiped in finally on a normal run."""
    scratch = tmp_path / "scratch"; scratch.mkdir()
    dest = tmp_path / "dest"

    img = _write_noise(scratch / "p.png", size=(1200, 1200), seed=5)
    yt = FakeChannelClient(
        "youtube", candidates=[_candidate(img, "youtube", w=1200, h=1200)]
    )
    classifier = FakeAssetClassifier(
        {"role": "founder_portrait", "visual_appeal": 3}
    )

    _run(
        understand_and_route(
            youtube_url="https://youtube.com/@f",
            instagram_url=None,
            founder_id="acme",
            scratch_dir=str(scratch),
            dest_root=str(dest),
            youtube_client=yt,
            instagram_client=None,
            classifier=classifier,
            selector=_selector_with_big_detector(),
            storage=LocalStorage(str(dest)),
        )
    )
    assert not scratch.exists(), "scratch must be wiped after the run"
