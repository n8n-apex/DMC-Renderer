"""The loop must act on what the gates detect, and refuse what it cannot fix."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for extra in (ROOT / "research",):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from composition_registry.registry import load_registry  # noqa: E402
from quality_loop.conductor_v3 import (  # noqa: E402
    CAPABILITY_GAPS,
    ConductorReport,
    apply,
    propose,
)
from stages.plan_compositions_v3 import (  # noqa: E402
    CompositionPlanV3,
    FaceCompositionDecision,
    SelectedComposition,
)

REGISTRY_PATH = ROOT / "research" / "composition_registry" / "families" / "dmc-v1.json"
ATLAS_PATH = ROOT / "research" / "reference-atlas" / "reference-atlas.json"


def registry():
    return load_registry(REGISTRY_PATH, atlas_path=ATLAS_PATH)


class _Failure:
    def __init__(self, code, face_ids, detail="d"):
        self.code = code
        self.face_ids = face_ids
        self.detail = detail


def _plan(family_id: str, variant_id: str, face_id: str = "face.01"):
    reg = registry()
    family = next(f for f in reg.families if f.family_id == family_id)
    return CompositionPlanV3(
        registry_version=reg.version,
        policy_id="dmc-composition-scoring",
        policy_version="1.0.0",
        decisions=(
            FaceCompositionDecision(
                face_id=face_id,
                considered=(),
                selected=SelectedComposition(
                    family_id=family_id,
                    family_version=family.version,
                    variant_id=variant_id,
                    policy_id="dmc-composition-scoring",
                    policy_version="1.0.0",
                ),
            ),
        ),
    )


def _lowest_variant(family_id: str) -> str:
    family = next(f for f in registry().families if f.family_id == family_id)
    return sorted(
        family.variants, key=lambda v: (getattr(v, "envelope_scale", 1.0), v.variant_id)
    )[0].variant_id


def test_dead_space_steps_toward_the_airier_variant() -> None:
    """A sparse face needs a layout BUILT for less content, not more.

    envelope_scale is a word budget, so the low-scale variant is the airy
    one. Stepping the other way is what the first version did, and its
    fixes measured no improvement.
    """
    family_id = "theory_interpretation"
    family = next(f for f in registry().families if f.family_id == family_id)
    ladder = sorted(
        family.variants, key=lambda v: (getattr(v, "envelope_scale", 1.0), v.variant_id)
    )
    plan = _plan(family_id, ladder[-1].variant_id)   # start dense

    report = propose((_Failure("dead_space_region", ("face.01",)),), plan, registry())

    assert len(report.applied) == 1
    assert report.applied[0].to_variant == ladder[-2].variant_id
    assert report.applied[0].knob_class == "renderer"


def test_applying_a_fix_returns_a_copy_and_leaves_the_plan_alone() -> None:
    family_id = "theory_interpretation"
    family = next(f for f in registry().families if f.family_id == family_id)
    start = sorted(
        family.variants, key=lambda v: (getattr(v, "envelope_scale", 1.0), v.variant_id)
    )[-1].variant_id
    plan = _plan(family_id, start)
    report = propose((_Failure("dead_space_region", ("face.01",)),), plan, registry())

    patched = apply(plan, report)

    assert patched is not plan
    assert plan.decisions[0].selected.variant_id == start          # untouched
    assert patched.decisions[0].selected.variant_id != start       # stepped


def test_a_missing_photograph_is_flagged_never_knob_turned() -> None:
    """The anti-faking rule: an asset gap must not move a render axis."""
    plan = _plan("theory_interpretation", _lowest_variant("theory_interpretation"))

    report = propose(
        (
            _Failure("synthetic_placeholder_asset", ("face.01",)),
            _Failure("visual_density_below_reference", ("face.01",)),
        ),
        plan,
        registry(),
    )

    assert not report.applied
    assert len(report.flagged) == 2
    assert all(fix.knob_class == "asset_gen" for fix in report.flagged)


def test_the_end_of_the_variant_ladder_falls_back_to_the_type_knob() -> None:
    """Out of variants is not out of options.

    A designer with the same words and too much room sets them larger. The
    type knob needs no new content, which is exactly why it is worth trying
    before the loop reports a capability gap.
    """
    family_id = "theory_interpretation"
    bottom = _lowest_variant(family_id)
    plan = _plan(family_id, bottom)

    report = propose((_Failure("dead_space_region", ("face.01",)),), plan, registry())

    assert len(report.applied) == 1
    fix = report.applied[0]
    assert fix.type_scale is not None and fix.type_scale > 1.0
    assert fix.to_variant == bottom          # variant unchanged


def test_no_type_headroom_is_reported_as_exhausted_not_forced() -> None:
    """At the registry's own font ceiling the loop stops, it does not push."""

    class _RegionFacts:
        def __init__(self, size): self.font_size_pt = size

    class _Facts:
        language = "de"
        def __init__(self, sizes): self.regions = sizes

    family_id = "theory_interpretation"
    family = next(f for f in registry().families if f.family_id == family_id)
    # Put every region at its declared maximum for German.
    at_max = {
        r.region_id: _RegionFacts(
            next(c.max_font_pt for c in r.capacities if c.language == "de")
        )
        for r in family.regions
    }
    plan = _plan(family_id, _lowest_variant(family_id))

    report = propose(
        (_Failure("dead_space_region", ("face.01",)),),
        plan,
        registry(),
        facts_by_face={"face.01": _Facts(at_max)},
    )

    assert not report.applied
    assert len(report.exhausted) == 1
    assert "no type headroom" in report.exhausted[0].detail


def test_clipping_steps_the_other_way() -> None:
    """Too much content needs a layout that accepts more, i.e. denser."""
    family_id = "theory_interpretation"
    family = next(f for f in registry().families if f.family_id == family_id)
    ladder = sorted(
        family.variants, key=lambda v: (getattr(v, "envelope_scale", 1.0), v.variant_id)
    )
    plan = _plan(family_id, ladder[0].variant_id)

    report = propose((_Failure("element_clipped", ("face.01",)),), plan, registry())

    assert len(report.applied) == 1
    assert report.applied[0].to_variant == ladder[1].variant_id


def test_one_step_per_face_per_pass() -> None:
    """Three defects on one face must not step it three times and oscillate."""
    family = next(f for f in registry().families if f.family_id == "theory_interpretation")
    top = sorted(
        family.variants, key=lambda v: (getattr(v, "envelope_scale", 1.0), v.variant_id)
    )[-1].variant_id
    plan = _plan("theory_interpretation", top)

    report = propose(
        (
            _Failure("dead_space_region", ("face.01",)),
            _Failure("dead_space_region", ("face.01",)),
            _Failure("dead_space_region", ("face.01",)),
        ),
        plan,
        registry(),
    )

    assert len(report.applied) == 1


def test_every_capability_gap_code_is_a_real_gate_code() -> None:
    """A flagged code nobody emits is a rule that never fires."""
    from quality_loop.ship_gate_v3 import KNOWN_FAILURE_CODES

    assert CAPABILITY_GAPS <= KNOWN_FAILURE_CODES


def test_stepping_requires_a_strictly_different_scale() -> None:
    """Two variants at the same scale are the same rung.

    closing_cta ships three variants at envelope_scale 1.00. An index-based
    step moved between them and changed nothing the capacity model can see,
    so the loop burned a whole pass on a no-op.
    """
    family = next(f for f in registry().families if f.family_id == "closing_cta")
    scales = sorted({getattr(v, "envelope_scale", 1.0) for v in family.variants})
    assert len(scales) >= 2, "closing_cta needs a real ladder for this to mean anything"

    at_top = [
        v.variant_id
        for v in family.variants
        if getattr(v, "envelope_scale", 1.0) == scales[-1]
    ]
    plan = _plan("closing_cta", at_top[0])

    report = propose((_Failure("dead_space_region", ("face.01",)),), plan, registry())

    assert len(report.applied) == 1
    target = report.applied[0].to_variant
    target_scale = next(
        getattr(v, "envelope_scale", 1.0)
        for v in family.variants
        if v.variant_id == target
    )
    assert target_scale < scales[-1]
