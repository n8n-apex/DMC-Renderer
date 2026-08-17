"""Deterministic scoring + per-slot selection of founder-imagery candidates.

Each downloaded `Candidate` image is scored on a few cheap, deterministic
signals, then ranked into the founder slots:

- ``cover_hero`` / ``founder`` / ``about_portrait`` — want a sharp, frontal,
  prominent face.
- ``team`` — a wider / multi-person shot (multiple faces, or just a large
  image); ranked by sharpness.
- ``scene`` — atmosphere / b-roll; no face required, just sharp enough.

Design notes
------------
- **Sharpness** is the variance of the Laplacian (``cv2.Laplacian(...).var()``)
  on the grayscale image. This is fully deterministic and works on any image,
  so it is computed with REAL cv2 in tests too.
- **Face detection is injectable.** ``score_candidate`` takes a
  ``face_detector(image_gray) -> list[(x, y, w, h)]`` callable, defaulting to
  the OpenCV Haar frontal-face cascade. Tests inject a stub returning scripted
  boxes so they do not depend on a real face photo.

Pure + brand-agnostic: no network, no client literals.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Optional, Sequence

import cv2
import numpy as np

from .models import Candidate

# A face_detector takes a grayscale image and returns face boxes (x, y, w, h).
FaceDetector = Callable[[np.ndarray], list[tuple[int, int, int, int]]]
Box = tuple[int, int, int, int]

# --- tunables (documented) --------------------------------------------------

# Minimum acceptable variance-of-Laplacian. Below this the image reads as
# blurry / out of focus and is rejected from every slot. Empirically a heavy
# Gaussian blur drops a noisy/edge-rich photo well under ~100 while genuinely
# sharp imagery sits in the hundreds-to-thousands, so 100 cleanly separates
# the two without being so high that ordinary in-focus photos get dropped.
SHARPNESS_MIN: float = 60.0  # loose garbage pre-filter; the VIS gate is the
# real acceptance bar. A real curated founder avatar measured ~93, so the prior
# 100 wrongly rejected it; let borderline-but-real images reach the VIS gate.

# A face must occupy at least this fraction of the image area to count as a
# usable portrait subject (rejects tiny background faces from face slots).
MIN_FACE_AREA_FRAC: float = 0.02

# A source whose long edge is at least this many pixels is "print-capable": it
# can be face-cropped + modestly upscaled to the ~2500px print target while
# staying crisp. Ranking buckets print-capable sources ABOVE sub-print ones so a
# crisp high-res environmental portrait beats a tiny low-res thumbnail whose
# face merely fills the frame (the latter upscales to a soft, capped result).
MIN_PRINT_LONG_EDGE: int = 1000


def _print_capable(score: "CandidateScore") -> bool:
    return max(score.width, score.height) >= MIN_PRINT_LONG_EDGE


def _face_rank_key(score: "CandidateScore") -> tuple:
    """Sort key (higher = better) for ranking a face into a portrait slot.

    Two tiers, fully separated by the leading flag:
      * print-capable sources first — among them prefer the most PROMINENT face
        (then sharpness); they all have enough pixels, so framing wins.
      * sub-print sources next — among them prefer the LARGEST source (more
        pixels to upscale from → crisper print), then prominence. This is the
        fix for a hero slot picking a tiny 320px avatar over a 990px one just
        because the small one's face filled marginally more of the frame.
    """
    if _print_capable(score):
        return (1, score.face_area_frac, score.sharpness)
    return (0, max(score.width, score.height), score.face_area_frac)

# "frontal" heuristic thresholds (see _is_frontal).
_FRONTAL_ASPECT_MIN = 0.7   # box width/height: a frontal face box is ~square
_FRONTAL_ASPECT_MAX = 1.4
_FRONTAL_CENTER_MAX = 0.30  # box center may sit at most this far (as a frac of
                            # image dim) from the image center on each axis


@dataclass
class CandidateScore:
    """Deterministic per-image signals used to rank candidates into slots."""

    has_face: bool
    frontal: bool
    face_area_frac: float
    sharpness: float
    width: int
    height: int
    # The largest detected face box (x, y, w, h), or None when no face — exposed
    # so a portrait slot can be face-cropped (head + shoulders) downstream.
    box: Optional[Box] = None


@lru_cache(maxsize=1)
def _default_face_detector() -> FaceDetector:
    """Build the default OpenCV Haar frontal-face detector (cached)."""
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(cascade_path)

    def detect(gray: np.ndarray) -> list[Box]:
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        return [tuple(int(v) for v in box) for box in faces]

    return detect


def _is_frontal(box: Box, img_w: int, img_h: int) -> bool:
    """Heuristic: a frontal face box is roughly square and reasonably centered.

    - aspect ratio ``w / h`` within [0.7, 1.4] (frontal faces are near-square;
      strongly non-square boxes tend to be profiles or false positives), and
    - the box center lies within 30% of an image dimension from the image
      center on both axes (centered subjects read as posed portraits).
    """
    x, y, w, h = box
    if w <= 0 or h <= 0 or img_w <= 0 or img_h <= 0:
        return False

    aspect = w / h
    if not (_FRONTAL_ASPECT_MIN <= aspect <= _FRONTAL_ASPECT_MAX):
        return False

    cx, cy = x + w / 2.0, y + h / 2.0
    off_x = abs(cx - img_w / 2.0) / img_w
    off_y = abs(cy - img_h / 2.0) / img_h
    return off_x <= _FRONTAL_CENTER_MAX and off_y <= _FRONTAL_CENTER_MAX


def score_candidate(
    path: str,
    *,
    face_detector: FaceDetector | None = None,
) -> CandidateScore:
    """Score one candidate image into a `CandidateScore`.

    ``sharpness`` uses the REAL cv2 Laplacian variance. Face presence/geometry
    comes from ``face_detector`` (default = OpenCV Haar cascade); tests inject
    a stub so they need no real face photo.
    """
    detector = face_detector or _default_face_detector()

    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"could not read image: {path}")

    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    img_h, img_w = gray.shape[:2]

    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    boxes = list(detector(gray))
    has_face = len(boxes) > 0

    face_area_frac = 0.0
    frontal = False
    largest: Optional[Box] = None
    if has_face:
        img_area = float(img_w * img_h) or 1.0
        largest = max(boxes, key=lambda b: b[2] * b[3])
        face_area_frac = (largest[2] * largest[3]) / img_area
        frontal = _is_frontal(largest, img_w, img_h)

    return CandidateScore(
        has_face=has_face,
        frontal=frontal,
        face_area_frac=face_area_frac,
        sharpness=sharpness,
        width=img_w,
        height=img_h,
        box=largest,
    )


# Slots that demand a sharp, frontal, prominent face.
_FACE_SLOTS = ("cover_hero", "founder", "about_portrait")


def _select_face_slot(
    scored: Sequence[tuple[Candidate, CandidateScore]],
) -> list[Candidate]:
    """Candidates with a sharp, frontal, sufficiently-large face.

    Ranked best-first by prominence (``face_area_frac``) then ``sharpness``.
    """
    eligible = [
        (cand, sc)
        for cand, sc in scored
        if sc.has_face
        and sc.frontal
        and sc.sharpness >= SHARPNESS_MIN
        and sc.face_area_frac >= MIN_FACE_AREA_FRAC
    ]
    # Print-capable sources first (so a crisp high-res portrait beats a tiny
    # thumbnail whose face fills the frame); within the sub-print tier prefer the
    # largest source so the hero never lands on a tiny avatar by accident.
    eligible.sort(key=lambda cs: _face_rank_key(cs[1]), reverse=True)
    return [cand for cand, _ in eligible]


def _select_team_slot(
    scored: Sequence[tuple[Candidate, CandidateScore]],
) -> list[Candidate]:
    """Wider / multi-person shots: must be sharp enough; ranked by sharpness.

    A candidate qualifies if it is sharp and either has more than one detected
    face (a group) or is simply a large image (a wide establishing shot).
    """
    eligible = [
        (cand, sc)
        for cand, sc in scored
        if sc.sharpness >= SHARPNESS_MIN
    ]
    # Print-capable first, then sharpness (a soft-but-large group shot beats a
    # razor-sharp tiny thumbnail for a printed page).
    eligible.sort(
        key=lambda cs: (_print_capable(cs[1]), cs[1].sharpness), reverse=True
    )
    return [cand for cand, _ in eligible]


def _select_scene_slot(
    scored: Sequence[tuple[Candidate, CandidateScore]],
) -> list[Candidate]:
    """Any sufficiently-sharp image; no face required. Print-capable first,
    then sharpness."""
    eligible = [(cand, sc) for cand, sc in scored if sc.sharpness >= SHARPNESS_MIN]
    eligible.sort(
        key=lambda cs: (_print_capable(cs[1]), cs[1].sharpness), reverse=True
    )
    return [cand for cand, _ in eligible]


# Face-crop padding (fractions of the face box). Deliberately GENEROUS so a
# portrait reads as an environmental head-and-shoulders shot — like the
# reference decks — NOT a tight mugshot: wide on the sides, a little headroom,
# and a lot below for shoulders/torso.
_CROP_SIDE_PAD = 0.9
_CROP_TOP_PAD = 0.7
_CROP_BOTTOM_PAD = 2.0


def crop_to_face(
    image_path: str,
    box: Box,
    dest_path: str,
    *,
    side_pad: float = _CROP_SIDE_PAD,
    top_pad: float = _CROP_TOP_PAD,
    bottom_pad: float = _CROP_BOTTOM_PAD,
) -> str:
    """Crop ``image_path`` to a GENEROUS region around the face ``box`` and save.

    The face box is expanded by the padding fractions (head + shoulders + some
    torso), clamped to the image bounds, and written to ``dest_path``. Returns
    ``dest_path``. Deterministic; no inpainting. A box that is already near an
    edge simply clamps (never goes negative / out of bounds).
    """
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"could not read image: {image_path}")
    img_h, img_w = image.shape[:2]

    x, y, w, h = box
    x0 = int(round(x - side_pad * w))
    x1 = int(round(x + w + side_pad * w))
    y0 = int(round(y - top_pad * h))
    y1 = int(round(y + h + bottom_pad * h))

    x0 = max(0, min(x0, img_w - 1))
    y0 = max(0, min(y0, img_h - 1))
    x1 = max(x0 + 1, min(x1, img_w))
    y1 = max(y0 + 1, min(y1, img_h))

    crop = image[y0:y1, x0:x1]
    cv2.imwrite(str(dest_path), crop)
    return str(dest_path)


def select_for_slots(
    candidates_with_scores: Sequence[tuple[Candidate, CandidateScore]],
    slots: Sequence[str],
) -> dict[str, list[Candidate]]:
    """Rank scored candidates into each requested slot (best-first).

    A blurry or no-face candidate is simply not ranked into a face slot (it is
    excluded rather than appended low). ``scene`` allows no-face images.
    """
    out: dict[str, list[Candidate]] = {}
    for slot in slots:
        if slot in _FACE_SLOTS:
            out[slot] = _select_face_slot(candidates_with_scores)
        elif slot == "team":
            out[slot] = _select_team_slot(candidates_with_scores)
        elif slot == "scene":
            out[slot] = _select_scene_slot(candidates_with_scores)
        else:
            out[slot] = []
    return out
