"""Router — place each understood asset into the report element it best serves.

Pure (no I/O, no network): given ``(Candidate, det_score, AssetJudgement)``
triples, it maps each asset's VIS ``role`` to candidate report elements (design
§4.3), then fills each element best-appeal-first with DET cross-checks and
source de-dup. An element with no role-appropriate, DET-passing, appealing
asset is FLAGGED — never fabricated.

DET robustness: ``det_score`` is a stand-in object in tests (``.frontal`` /
``.print_capable`` / ``.faces``) and the real ``selector.CandidateScore`` in
production (``.frontal`` / ``.has_face`` / ``.face_area_frac`` / ``.width`` /
``.height`` — but NO ``.print_capable`` or ``.faces``). Everything is read via
getattr with both shapes supported:
  * print-capable = a ``.print_capable`` attr if present, else long edge >= 1000;
  * face count = ``.faces`` if present, else ``1 if .has_face else 0``.

Brand-agnostic: no client literals; routing keys off depiction + DET only.
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from .models import AssetJudgement, Candidate, RoutedElement

# A routed item: the scraped candidate, its DET score, its VIS judgement.
RoutedItem = Tuple[Candidate, object, AssetJudgement]

# Long edge (px) at/above which a source is "print-capable" — mirrors
# selector.MIN_PRINT_LONG_EDGE so face elements demand enough pixels.
_PRINT_LONG_EDGE = 1000

# An asset must be at least this appealing to be placed (low-confidence ->
# flag, not place; design §6 "role mis-classification" mitigation).
APPEAL_MIN = 2

# role -> candidate report element(s), in preference order (design §4.3).
ROLE_TO_ELEMENTS: dict[str, list[str]] = {
    "founder_portrait": ["cover_hero", "team"],
    "founder_working": ["device_mockup"],
    "founder_speaking": ["scene"],
    "group_team": ["team"],
    "lifestyle": ["scene"],
    "content_card": ["proof"],
    "logo": ["logo"],
}

# Fill order across elements (best assets claimed first by higher-priority els).
ELEMENT_PRIORITY: list[str] = [
    "cover_hero",
    "team",
    "device_mockup",
    "scene",
    "proof",
    "logo",
]

# Elements that demand a real frontal, print-capable face.
_FACE_ELEMENTS = {"cover_hero"}


def _is_print_capable(det: object) -> bool:
    """True if the source has enough pixels for print.

    Supports both shapes: an explicit ``.print_capable`` attr (test stand-in)
    or a long edge >= 1000 (real ``selector.CandidateScore``).
    """
    pc = getattr(det, "print_capable", None)
    if pc is not None:
        return bool(pc)
    long_edge = max(getattr(det, "width", 0), getattr(det, "height", 0))
    return long_edge >= _PRINT_LONG_EDGE


def _face_count(det: object) -> int:
    """Number of faces. ``.faces`` if present, else 1/0 from ``.has_face``."""
    faces = getattr(det, "faces", None)
    if faces is not None:
        return int(faces)
    return 1 if getattr(det, "has_face", False) else 0


def _resolution(item: RoutedItem) -> int:
    """Longest edge of the source (px). Uses the Candidate dims (always present)
    and falls back to the DET score if needed."""
    cand, det, _judge = item
    return max(
        getattr(cand, "width", 0) or 0,
        getattr(cand, "height", 0) or 0,
        getattr(det, "width", 0) or 0,
        getattr(det, "height", 0) or 0,
    )


def _passes_element_det(element: str, det: object) -> bool:
    """DET constraint for an element.

    - face elements (cover_hero): require a frontal FACE.
      Print-capability is NOT a hard gate — it is a strong RANKING preference
      (see ``_rank_key``). A slightly-sub-print but frontal portrait (e.g. a
      990px studio headshot) is the best real hero available for many founders;
      the restorer upscales it. Hard-excluding it would flag the hero empty,
      which is worse than a crisp upscale (proven in the Phase-1 founder slot).
    - others: no face requirement.
    (team's face PREFERENCE is applied in ranking, not as a hard gate, so a
    sparse feed with only solo shots can still fill the team element.)
    """
    if element in _FACE_ELEMENTS:
        return bool(getattr(det, "frontal", False))
    return True


def _rank_key(element: str, item: RoutedItem) -> tuple:
    """Best-first sort key for an element's eligible candidates.

    Primary: visual appeal. Then a team element prefers >=2 faces. Then
    print-capable sources, then raw resolution (a 990px portrait beats a 320px
    one for the hero). The candidate path is appended so the sort is
    deterministic for equal scores.
    """
    cand, det, judge = item
    team_pref = 1 if (element == "team" and _face_count(det) >= 2) else 0
    return (
        judge.visual_appeal,
        team_pref,
        1 if _is_print_capable(det) else 0,
        _resolution(item),
        # deterministic tie-break (stable, brand-agnostic): newest-by-path last
        cand.local_path,
    )


def route_assets(items: Sequence[RoutedItem]) -> List[RoutedElement]:
    """Route ``(Candidate, det, AssetJudgement)`` triples to report elements.

    For each element in ``ELEMENT_PRIORITY``: gather candidates whose role maps
    to it AND pass the element's DET constraint AND ``appeal >= APPEAL_MIN`` AND
    whose source is not already used; pick the best by ``_rank_key``; mark its
    source used. If none qualifies, FLAG the element (never fabricate).

    Returns exactly one ``RoutedElement`` per element in ``ELEMENT_PRIORITY``.
    """
    used_paths: set[str] = set()
    out: List[RoutedElement] = []

    for element in ELEMENT_PRIORITY:
        eligible = [
            item
            for item in items
            if element in ROLE_TO_ELEMENTS.get(item[2].role, [])
            and item[2].visual_appeal >= APPEAL_MIN
            and _passes_element_det(element, item[1])
            and item[0].local_path not in used_paths
        ]
        if eligible:
            cand, _det, judge = max(eligible, key=lambda it: _rank_key(element, it))
            used_paths.add(cand.local_path)
            out.append(
                RoutedElement(
                    element=element,
                    status="filled",
                    path=cand.local_path,
                    role=judge.role,
                    appeal=judge.visual_appeal,
                )
            )
        else:
            out.append(
                RoutedElement(
                    element=element,
                    status="flagged",
                    reason=_flag_reason(element, items),
                )
            )

    return out


def _flag_reason(element: str, items: Sequence[RoutedItem]) -> str:
    """A short, brand-agnostic reason for why an element could not be filled."""
    roles_for_el = [
        role for role, els in ROLE_TO_ELEMENTS.items() if element in els
    ]
    any_role_match = any(it[2].role in roles_for_el for it in items)
    if not any_role_match:
        return f"no asset with a role suited to {element}"
    if element in _FACE_ELEMENTS:
        return f"no frontal print-capable face for {element}"
    return f"no suitable asset for {element}"
