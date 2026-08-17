"""Tests for selector.py — deterministic scoring + per-slot ranking of
founder-imagery candidates.

Strategy:
- sharpness uses REAL cv2 Laplacian (deterministic on any image), so we
  build a sharp vs blurred image with PIL/numpy and assert ordering.
- face presence/geometry is driven through an INJECTED stub detector that
  returns scripted boxes, so the tests never need a real face photo.

Pure (no network). Brand-agnostic.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

from stages.scrape_founder_assets.models import Candidate
from stages.scrape_founder_assets.selector import (
    SHARPNESS_MIN,
    CandidateScore,
    crop_to_face,
    score_candidate,
    select_for_slots,
)


# --- image fixtures ---------------------------------------------------------

def _write_noise(path, size=(256, 256), seed=0):
    """High-frequency random noise -> high Laplacian variance (sharp)."""
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 256, size=(size[1], size[0], 3), dtype=np.uint8)
    Image.fromarray(arr).save(path)
    return path


def _write_blurred(path, size=(256, 256), seed=0, radius=8):
    """Same noise heavily Gaussian-blurred -> low Laplacian variance."""
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 256, size=(size[1], size[0], 3), dtype=np.uint8)
    img = Image.fromarray(arr).filter(ImageFilter.GaussianBlur(radius=radius))
    img.save(path)
    return path


def _stub(boxes):
    """A face_detector stub: ignores the image, returns scripted boxes."""
    return lambda gray: list(boxes)


def _cand(path, w=256, h=256):
    return Candidate(source="youtube", kind="frame", local_path=str(path),
                     width=w, height=h)


# --- tests ------------------------------------------------------------------

def test_sharpness_discriminates(tmp_path):
    sharp = _write_noise(tmp_path / "sharp.png", seed=1)
    blurry = _write_blurred(tmp_path / "blurry.png", seed=1, radius=8)

    s_sharp = score_candidate(sharp)
    s_blurry = score_candidate(blurry)

    assert isinstance(s_sharp, CandidateScore)
    # Real cv2 Laplacian: noise is far sharper than a blurred copy.
    assert s_sharp.sharpness > s_blurry.sharpness
    assert s_sharp.sharpness > s_blurry.sharpness * 5


def test_face_slots_require_frontal_sharp_face(tmp_path):
    sharp = _write_noise(tmp_path / "sharp.png", seed=2)
    blurry = _write_blurred(tmp_path / "blurry.png", seed=2, radius=10)
    noface = _write_noise(tmp_path / "noface.png", seed=3)

    # centered, square box ~ frontal & prominent (image is 256x256)
    centered = [(78, 78, 100, 100)]

    good = score_candidate(sharp, face_detector=_stub(centered))
    blur_faced = score_candidate(blurry, face_detector=_stub(centered))
    none = score_candidate(noface, face_detector=_stub([]))

    assert good.has_face and good.frontal
    assert none.has_face is False
    assert blur_faced.sharpness < SHARPNESS_MIN

    pairs = [
        (_cand(sharp), good),
        (_cand(blurry), blur_faced),
        (_cand(noface), none),
    ]
    out = select_for_slots(pairs, ["founder"])
    founder = out["founder"]

    # the sharp, frontal-faced candidate is present and ranked first
    assert founder, "expected at least one founder candidate"
    assert founder[0].local_path == str(sharp)
    # no-face candidate excluded from a face slot
    assert str(noface) not in [c.local_path for c in founder]
    # blurry-faced candidate rejected by SHARPNESS_MIN
    assert str(blurry) not in [c.local_path for c in founder]


def test_face_area_frac_prefers_prominent(tmp_path):
    big = _write_noise(tmp_path / "big.png", seed=4)
    small = _write_noise(tmp_path / "small.png", seed=5)

    big_box = [(48, 48, 160, 160)]   # large centered face
    small_box = [(108, 108, 60, 60)]  # small centered face

    s_big = score_candidate(big, face_detector=_stub(big_box))
    s_small = score_candidate(small, face_detector=_stub(small_box))

    assert s_big.face_area_frac > s_small.face_area_frac

    pairs = [(_cand(small), s_small), (_cand(big), s_big)]
    out = select_for_slots(pairs, ["about_portrait"])
    portraits = out["about_portrait"]

    assert [c.local_path for c in portraits][0] == str(big)
    assert {c.local_path for c in portraits} == {str(big), str(small)}


def test_score_exposes_face_box(tmp_path):
    """The largest detected face box is exposed for downstream face-cropping."""
    sharp = _write_noise(tmp_path / "boxed.png", seed=7)
    box = (78, 78, 100, 100)
    s = score_candidate(sharp, face_detector=_stub([box]))
    assert s.box == box
    none = score_candidate(sharp, face_detector=_stub([]))
    assert none.box is None


def test_crop_to_face_generous_headshoulders(tmp_path):
    """crop_to_face expands the face box generously (head + shoulders + torso),
    clamped to image bounds, and writes a real cropped file."""
    src = _write_noise(tmp_path / "portrait.png", size=(400, 600), seed=8)
    dest = tmp_path / "cropped.png"
    # a face box near the top-center, as in a real portrait
    box = (160, 120, 80, 80)  # x, y, w, h
    out = crop_to_face(str(src), box, str(dest))
    assert out == str(dest)

    cropped = Image.open(dest)
    cw, ch = cropped.size
    # generous: the crop must be substantially WIDER and TALLER than the bare
    # face box (head + shoulders), not a tight mugshot
    assert cw > 80 * 2, f"crop width {cw} not generous vs face 80"
    assert ch > 80 * 2, f"crop height {ch} not generous vs face 80"
    # and clamped to the source bounds
    assert cw <= 400 and ch <= 600


def test_crop_to_face_clamps_at_edges(tmp_path):
    """A face box hard against the top-left clamps without going negative."""
    src = _write_noise(tmp_path / "edge.png", size=(300, 300), seed=9)
    dest = tmp_path / "edge_crop.png"
    box = (0, 0, 60, 60)
    crop_to_face(str(src), box, str(dest))
    cropped = Image.open(dest)
    cw, ch = cropped.size
    assert cw > 0 and ch > 0
    assert cw <= 300 and ch <= 300


def test_face_slot_prefers_high_res_over_prominence(tmp_path):
    """A high-res portrait with a SMALLER (environmental) face must outrank a
    tiny low-res thumbnail whose face fills the frame — otherwise face slots
    fill with soft, upscale-capped thumbnails instead of crisp real photos."""
    big = _write_noise(tmp_path / "hi.png", size=(1080, 1350), seed=20)   # print-capable
    thumb = _write_noise(tmp_path / "lo.png", size=(480, 360), seed=21)   # sub-print

    # the thumbnail's face fills most of the small frame (high face_area_frac);
    # the high-res portrait has a smaller, environmental face.
    big_score = score_candidate(big, face_detector=_stub([(440, 400, 200, 200)]))
    thumb_score = score_candidate(thumb, face_detector=_stub([(140, 60, 220, 220)]))
    assert thumb_score.face_area_frac > big_score.face_area_frac  # thumb is "more prominent"

    pairs = [
        (_cand(thumb, 480, 360), thumb_score),
        (_cand(big, 1080, 1350), big_score),
    ]
    out = select_for_slots(pairs, ["founder"])["founder"]
    assert out, "expected eligible founder candidates"
    # despite lower prominence, the high-res source ranks FIRST
    assert out[0].local_path == str(big), [c.local_path for c in out]


def test_face_slot_subprint_prefers_larger_source(tmp_path):
    """Among sub-print face candidates (both < 1000px), the LARGER source ranks
    first — a 990px avatar beats a 320px one even if the small one's face is
    marginally more prominent (the hero-slot soft-avatar bug)."""
    big = _write_noise(tmp_path / "a990.png", size=(990, 990), seed=30)
    small = _write_noise(tmp_path / "a320.png", size=(320, 320), seed=31)

    # small avatar's face is marginally MORE prominent (would win on face_area)
    big_score = score_candidate(big, face_detector=_stub([(345, 345, 300, 300)]))
    small_score = score_candidate(small, face_detector=_stub([(105, 105, 110, 110)]))
    assert small_score.face_area_frac >= big_score.face_area_frac

    pairs = [(_cand(small, 320, 320), small_score), (_cand(big, 990, 990), big_score)]
    out = select_for_slots(pairs, ["founder"])["founder"]
    assert out and out[0].local_path == str(big), [c.local_path for c in out]


def test_scene_slot_allows_no_face(tmp_path):
    sharp = _write_noise(tmp_path / "scene.png", seed=6)
    s = score_candidate(sharp, face_detector=_stub([]))

    assert s.has_face is False

    pairs = [(_cand(sharp), s)]
    out = select_for_slots(pairs, ["scene", "founder"])

    # eligible for scene (no face required), excluded from founder
    assert [c.local_path for c in out["scene"]] == [str(sharp)]
    assert out["founder"] == []
