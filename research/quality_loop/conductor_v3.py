"""Conductor v3 -- the detect->direct->execute bridge for the v3 pipeline.

The v3 gates are read-only. They name a defect and stop, which means every
repair has been done by a human reading a failure list. The v2 conductor
already implements the loop that should close this, but it speaks the old
world's language (`st_type`, `pkg["pages"][i]["layout_variant"]`), and
translating that onto composition families would create an impedance
mismatch worse than the gap. So this is the same discipline expressed in
v3's own terms.

Three rules carried over from the v2 conductor, because they are what make
the loop trustworthy rather than a way to make gates go quiet:

  1. This is the ONLY component permitted to mutate a plan.
  2. It patches a COPY. The frozen plan is never edited in place.
  3. It never fakes. A defect the renderer cannot fix (a missing photograph,
     a placeholder, too few pictures) is FLAGGED as a capability gap, not
     papered over by turning a knob until the metric moves.

The knob is the variant's `envelope_scale`, which the registry already
declares per variant: the share of a region's WORD BUDGET the variant expects
to use. A low-scale variant is therefore the one designed for sparse content,
and its geometry spreads that content across the sheet. A face with dead
space steps toward the LOW end; a face whose content is clipped steps toward
the high end, which accepts more. The ladder is read from the registry rather
than hardcoded, so adding a variant extends the conductor without touching it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal


# Which gate codes the renderer can actually act on, and in which direction.
# A code absent from here is not renderer-fixable and is flagged instead.
# `envelope_scale` is the share of a region's word budget a variant expects
# to use, so a LOW-scale variant is one designed for sparse content and its
# geometry spreads that content across the sheet. The direction therefore
# reads backwards at first glance and the first version of this file had it
# inverted: it stepped a dead-space face from the airy 0.62 variant to the
# dense 1.00 one, which is why its four fixes measured no improvement.
_AIRIER = "airier"      # toward a LOWER scale: less content, spread wider
_DENSER = "denser"      # toward a HIGHER scale: accepts more content

RENDERER_FIXABLE: dict[str, str] = {
    # Too little content for the area -> a layout built for less content.
    "dead_space_region": _AIRIER,
    # Too much content for the area -> a layout that accepts more.
    "element_clipped": _DENSER,
    "element_overflow": _DENSER,
    "height_line_budget_exceeded": _DENSER,
}

# One step of the type knob. 8% is small enough that a pass cannot leap past
# the right size and large enough to move the measured fill.
TYPE_STEP = 1.08

# Defects that are real but out of the renderer's reach. Naming them here is
# what stops the loop from spinning on something it can never fix.
CAPABILITY_GAPS: frozenset[str] = frozenset(
    {
        "visual_density_below_reference",
        "synthetic_placeholder_asset",
        "asset_reused_across_faces",
        "missing_required_asset",
        "asset_rights_not_cleared",
        "ungrounded_claim",
        "ungrounded_numeric_candidate",
    }
)


@dataclass(frozen=True)
class FixV3:
    """One proposed repair, or one honest refusal to repair."""

    face_id: str
    defect_code: str
    knob_class: Literal["renderer", "asset_gen", "content", "unknown"]
    from_variant: str | None
    to_variant: str | None
    detail: str
    exhausted: bool = False
    # The second knob: type size per region. `None` means this fix does not
    # touch it. A step is a ratio, applied within the registry's declared
    # min/max, so the capacity model still bounds it.
    type_scale: float | None = None


@dataclass(frozen=True)
class ConductorReport:
    """What the conductor decided, and what it refused to touch."""

    applied: tuple[FixV3, ...] = ()
    flagged: tuple[FixV3, ...] = ()
    exhausted: tuple[FixV3, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.applied)

    def summary(self) -> str:
        return (
            f"{len(self.applied)} applied, {len(self.flagged)} flagged as "
            f"capability gaps, {len(self.exhausted)} exhausted"
        )


def _variant_ladder(family) -> list[tuple[str, float]]:
    """This family's variants ordered by how much content they expect.

    `envelope_scale` is the share of its region a variant plans to fill, so
    ordering by it gives a real ladder: step up to fill more of the sheet,
    step down to relieve content that is being clipped.
    """
    return sorted(
        (
            (variant.variant_id, float(getattr(variant, "envelope_scale", 1.0)))
            for variant in family.variants
        ),
        key=lambda item: (item[1], item[0]),
    )


def _step(ladder: list[tuple[str, float]], current: str, direction: str) -> str | None:
    """The next variant at a STRICTLY different scale, or None at the end.

    Stepping by index alone lets the loop move between two variants that
    share an envelope_scale, which changes the layout name and nothing the
    capacity model can see. closing_cta has three variants at 1.00, so an
    index step there was a guaranteed no-op.
    """
    ids = [variant_id for variant_id, _ in ladder]
    if current not in ids:
        return None
    current_scale = dict(ladder)[current]
    if direction == _AIRIER:
        candidates = [(v, s) for v, s in ladder if s < current_scale]
    else:
        candidates = [(v, s) for v, s in ladder if s > current_scale]
    if not candidates:
        return None
    # The NEAREST different scale, so the loop moves one real rung at a time.
    return (
        max(candidates, key=lambda item: item[1])[0]
        if direction == _AIRIER
        else min(candidates, key=lambda item: item[1])[0]
    )


def _type_headroom(family, facts_by_face, face_id: str, scale: float) -> bool:
    """True when every region on this face can take the type step.

    The registry declares min_font_pt / max_font_pt per region per language.
    Proposing a step past them would only be rejected downstream, so the
    conductor checks first and reports exhaustion honestly instead.
    """
    facts = (facts_by_face or {}).get(face_id)
    if facts is None:
        return True   # no facts supplied: let the capacity gate arbitrate
    for region in family.regions:
        region_facts = getattr(facts, "regions", {}).get(region.region_id)
        if region_facts is None:
            continue
        current = float(getattr(region_facts, "font_size_pt", 0) or 0)
        if not current:
            continue
        capacity = next(
            (c for c in region.capacities if c.language == getattr(facts, "language", "de")),
            None,
        )
        if capacity is None:
            continue
        stepped = current * scale
        if stepped > capacity.max_font_pt or stepped < capacity.min_font_pt:
            return False
    return True


def propose(
    failures: tuple[Any, ...],
    composition_plan: Any,
    registry: Any,
    facts_by_face: dict[str, Any] | None = None,
) -> ConductorReport:
    """Decide what to do about each gate failure. Mutates nothing.

    One fix per face per pass: a face with three defects is stepped once and
    re-measured, because stepping three times on one reading is how a loop
    overshoots and oscillates.
    """
    families = {
        (family.family_id, family.version): family for family in registry.families
    }
    decision_by_face = {
        decision.face_id: decision for decision in composition_plan.decisions
    }

    applied: list[FixV3] = []
    flagged: list[FixV3] = []
    exhausted: list[FixV3] = []
    handled: set[str] = set()

    for failure in failures:
        code = getattr(failure, "code", None) or failure.get("code", "")
        face_ids = getattr(failure, "face_ids", None) or failure.get("face_ids", ())
        detail = getattr(failure, "detail", None) or failure.get("detail", "")
        face_id = face_ids[0] if face_ids else ""

        if code in CAPABILITY_GAPS:
            flagged.append(
                FixV3(
                    face_id=face_id,
                    defect_code=code,
                    knob_class="asset_gen" if "asset" in code or "density" in code
                    else "content",
                    from_variant=None,
                    to_variant=None,
                    detail=detail,
                )
            )
            continue

        direction = RENDERER_FIXABLE.get(code)
        if direction is None or not face_id or face_id in handled:
            if direction is None and code not in CAPABILITY_GAPS:
                flagged.append(
                    FixV3(
                        face_id=face_id,
                        defect_code=code,
                        knob_class="unknown",
                        from_variant=None,
                        to_variant=None,
                        detail=f"no knob addresses {code}; {detail}",
                    )
                )
            continue

        decision = decision_by_face.get(face_id)
        if decision is None:
            continue
        selected = decision.selected
        family = families.get((selected.family_id, selected.family_version))
        if family is None:
            continue

        ladder = _variant_ladder(family)
        target = _step(ladder, selected.variant_id, direction)
        if target is not None:
            applied.append(
                FixV3(
                    face_id=face_id,
                    defect_code=code,
                    knob_class="renderer",
                    from_variant=selected.variant_id,
                    to_variant=target,
                    detail=f"{code} on {face_id}: step {direction} to {target}",
                )
            )
            handled.add(face_id)
            continue

        # No rung left. A designer with the same words and too much room sets
        # them LARGER, so type size is the second knob. It needs no new
        # content, which is exactly why it is worth trying before giving up.
        scale = TYPE_STEP if direction == _AIRIER else 1.0 / TYPE_STEP
        if _type_headroom(family, facts_by_face, face_id, scale):
            applied.append(
                FixV3(
                    face_id=face_id,
                    defect_code=code,
                    knob_class="renderer",
                    from_variant=selected.variant_id,
                    to_variant=selected.variant_id,
                    detail=(
                        f"{code} on {face_id}: variant ladder exhausted, "
                        f"stepping type size by {scale:.2f}"
                    ),
                    type_scale=scale,
                )
            )
        else:
            exhausted.append(
                FixV3(
                    face_id=face_id,
                    defect_code=code,
                    knob_class="renderer",
                    from_variant=selected.variant_id,
                    to_variant=None,
                    detail=(
                        f"{selected.family_id}: no variant and no type headroom "
                        f"left in the {direction} direction"
                    ),
                    exhausted=True,
                )
            )
        handled.add(face_id)

    return ConductorReport(
        applied=tuple(applied), flagged=tuple(flagged), exhausted=tuple(exhausted)
    )


def apply_type(facts_by_face: dict[str, Any], report: ConductorReport) -> dict[str, Any]:
    """A COPY of the facts with each type step applied to every region.

    Same discipline as `apply`: the caller's facts are never edited, and a
    caller that drops the return value gets no change.
    """
    steps = {
        fix.face_id: fix.type_scale
        for fix in report.applied
        if fix.type_scale is not None
    }
    if not steps:
        return facts_by_face
    patched: dict[str, Any] = {}
    for face_id, facts in facts_by_face.items():
        scale = steps.get(face_id)
        if scale is None:
            patched[face_id] = facts
            continue
        regions = {
            region_id: region.model_copy(
                update={"font_size_pt": round(region.font_size_pt * scale, 2)}
            )
            for region_id, region in facts.regions.items()
        }
        patched[face_id] = facts.model_copy(update={"regions": regions})
    return patched


def apply(composition_plan: Any, report: ConductorReport) -> Any:
    """A COPY of the plan with each applied fix's variant swapped in.

    The frozen plan is never edited. A caller that ignores the return value
    gets no change, which is the intended shape: mutation is explicit.
    """
    if not report.applied:
        return composition_plan
    target_by_face = {fix.face_id: fix.to_variant for fix in report.applied}
    decisions = []
    for decision in composition_plan.decisions:
        target = target_by_face.get(decision.face_id)
        if target is None:
            decisions.append(decision)
            continue
        decisions.append(
            decision.model_copy(
                update={"selected": decision.selected.model_copy(
                    update={"variant_id": target}
                )}
            )
        )
    return composition_plan.model_copy(update={"decisions": tuple(decisions)})
