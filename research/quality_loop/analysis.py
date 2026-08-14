"""Analysis scorer -- the "judgment" of the self-correcting quality loop.

``score(facts, matched_refs, rubric) -> PageScore`` adjudicates each rubric row
against the deterministic ``PageFacts`` and produces a normalized reward, a
latching hard-fail verdict, per-row results, and ranked, knob-routed defects.

Two invariants are deliberately conservative / load-bearing:

  1. HARD-FAIL DOMINANCE -- any fired hard-fail row latches the page below ship
     no matter how high the reward. This is the anti-reward-hacking rule:
     ``cleared`` ANDs ``not hard_fail`` into the verdict so reward can never buy
     past a structural defect (a missing photo, a font fallback, a placeholder
     leak).

  2. NO VIS OVER-CREDIT -- any row whose detect needs a vision model (VIS or
     DET∧VIS) is reported "skipped:needs_vision" and contributes 0. We do NOT
     award a DET∧VIS positive on its DET half alone, to avoid over-crediting
     before reference-grounded visual comparison is wired. Likewise pure-DET
     rows with no computed fact are "skipped:needs_fact". Skipped rows are
     ALWAYS reported, never silently passed.

The rubric (the criteria) is data in ``rubric.py``; this module is the logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rubric import (
    RubricRow,
    N05_CONTRAST_MIN,
    N08_EMPTY_GAP_THRESHOLD,
    positive_max,
)


# --------------------------------------------------------------------------- #
# Result records
# --------------------------------------------------------------------------- #
@dataclass
class RowResult:
    """The adjudication outcome of one rubric row.

    status ∈ {"earned", "not_earned", "fired", "clear",
              "skipped:needs_vision", "skipped:needs_fact"}.
    """

    id: str
    status: str
    points: int
    detail: str


@dataclass
class Defect:
    """A localized, repair-routed defect (a fired negative row).

    ``severity`` is "hard_fail" for latching rows, else "weighted".
    ``target`` is the fact_key / page locus the repair should aim at.
    """

    id: str
    severity: str
    knob_class: str
    target: str
    detail: str


@dataclass
class PageScore:
    """The full judgment of a single page."""

    reward: float
    raw_points: int
    hard_fail: bool
    hard_fail_ids: list[str]
    row_results: list[RowResult]
    defects: list[Defect]
    skipped_vis: list[str]
    skipped_fact: list[str]
    matched_ref_count: int = 0


# --------------------------------------------------------------------------- #
# Per-row evaluators (pure DET rows with a computed fact)
# --------------------------------------------------------------------------- #
def _eval_positive(row: RubricRow, facts) -> RowResult:
    """A pure-DET positive earns its weight when its fact is satisfied."""
    value = getattr(facts, row.fact_key)
    earned = bool(value)
    if earned:
        return RowResult(row.id, "earned", row.weight,
                         f"{row.fact_key}={value!r} -> earned +{row.weight}")
    return RowResult(row.id, "not_earned", 0,
                     f"{row.fact_key}={value!r} -> not earned")


def _negative_fires(row: RubricRow, facts) -> bool:
    """Whether a pure-DET negative row's defect condition holds.

    Each branch cites the spec §6.2 row it adjudicates.
    """
    value = getattr(facts, row.fact_key)
    if row.id == "N01":  # empty required photo box
        return bool(value)  # required_slots_missing non-empty
    if row.id == "N03":  # font fallback / wrong family
        return value is False  # display_font_embedded False
    if row.id == "N04":  # overflow / clipping (text drawn beyond the page bounds)
        return value is True  # content_overflow
    if row.id == "N05":  # low text contrast (hard-fail < 4.5)
        return value < N05_CONTRAST_MIN
    if row.id == "N06":  # oversized QR / qr_enabled false
        return value is True  # qr_gating_violation
    if row.id == "N08":  # dead/hollow space (unified empty_gap: white gaps OR
        # content-less solid panels). Fires above the unified emptiness cut.
        return value > N08_EMPTY_GAP_THRESHOLD
    if row.id == "N09":  # missing header furniture
        return value is False  # header_furniture_present False
    if row.id == "N14":  # placeholder / lorem leakage
        return value is True  # placeholder_text_present
    if row.id == "N15":  # stat callout is prose, not a numeral
        return bool(value)  # non_numeral_stat_values non-empty
    # Defensive: an unmapped fact-bearing negative -- treat truthiness as firing.
    return bool(value)


def _eval_negative(row: RubricRow, facts) -> RowResult:
    """A pure-DET negative fires (applies its penalty / hard-fail) or clears."""
    fires = _negative_fires(row, facts)
    if not fires:
        return RowResult(row.id, "clear", 0,
                         f"{row.fact_key} did not trip {row.id}")
    points = 0 if row.hard_fail else row.weight  # hard-fails carry no numeric weight
    tag = "HARD-FAIL" if row.hard_fail else f"{row.weight}"
    detail = f"{row.fact_key} tripped {row.id} ({tag})"
    if row.id == "N08":  # hollow/empty region -> renderer fills it.
        gap = getattr(facts, row.fact_key)
        detail = (
            f"{row.fact_key}={gap:.3f} tripped {row.id} ({tag}): hollow/empty "
            f"region (white gap OR content-less solid panel) -- route to renderer"
        )
    if row.id == "N15":  # name the offending prose values + route to content.
        prose = getattr(facts, row.fact_key) or []
        detail = (
            f"{row.fact_key} tripped {row.id} ({tag}): prose-as-a-stat "
            f"values {list(prose)!r} -- route to content/preprocessor"
        )
    return RowResult(row.id, "fired", points, detail)


# --------------------------------------------------------------------------- #
# VIS adjudication thresholds + DET-gates-VIS (spec §6.3)
# --------------------------------------------------------------------------- #
# On the 0..3 reference-grounded scale, a POSITIVE VIS row is EARNED only at or
# above this bar (a clear visual match, not a faint resemblance).
VIS_EARN_THRESHOLD = 2
# A NEGATIVE VIS row FIRES at or above this bar (higher score = worse, per the
# prompt: more generic / more dead-space / more untreated bleed).
VIS_FIRE_THRESHOLD = 2

# Anti-reward-hacking caps (spec §6.3): a VIS-adjudicated positive contributes
# AT MOST its own row weight (no stacking across detectors), the summed earned
# positive is clamped to ``positive_max``, and any hard-fail still DOMINATES the
# clear verdict regardless of how much VIS reward accrued.

# DET-gates-VIS routing: for each DET∧VIS positive, the DET half must be PROVEN
# before the VIS reward is granted. ``_det_gate`` returns
# (gate_passed, gate_proven):
#   * P05 named-client photo  -> LIVE gate: passes iff no required portrait slot
#     is missing (``required_slots_missing == []``).
#   * all other DET∧VIS positives (P01, P07, P10, P11, P13, P14, P16) have NO
#     computed DET fact yet -> gate UNPROVEN -> conservatively NOT awarded.
def _det_gate(row_id: str, facts) -> tuple[bool, bool]:
    """Return ``(passed, proven)`` for a DET∧VIS positive's DET half.

    ``proven`` is False when no DET fact exists for the row -- we never award a
    DET∧VIS positive on an unproven gate (conservative).
    """
    if row_id == "P05":  # named client photo / case study (LIVE gate)
        passed = len(getattr(facts, "required_slots_missing", []) or []) == 0
        return (passed, True)
    # P01, P07, P10, P11, P13, P14, P16: no DET fact computed yet -> unproven.
    return (False, False)


def _earnable_positive_max(facts, vis_results, rubric, st_type: str = "all") -> int:
    """Sum of positive weights ACTUALLY earnable for this page (the
    capability-clamped denominator, parent design §5.5). A positive counts iff:
      * it applies to this st_type (applies_to == 'all' or includes st_type), AND
      * pure-DET row: it has a computed fact (fact_key is not None); OR
      * VIS / DET∧VIS row: a vision verdict exists for it AND (for DET∧VIS) its
        DET gate is PROVABLE (_det_gate proven) -- an unprovable gate can never
        be earned, so it is backlog, not part of the denominator.
    Rows the system cannot currently score are excluded (surfaced as skipped), so
    reward is measured against the achievable bar, not the theoretical 92.
    """
    vis_results = vis_results or {}
    total = 0
    for row in rubric:
        if row.polarity != "positive":
            continue
        if row.applies_to != "all" and st_type not in row.applies_to:
            continue
        if "VIS" in row.detect:
            if row.id not in vis_results:
                continue
            if row.detect == "DET∧VIS":
                _, gate_proven = _det_gate(row.id, facts)
                if not gate_proven:
                    continue
            total += row.weight
        else:  # pure DET positive
            if row.fact_key is None:
                continue
            total += row.weight
    return total


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def score(
    facts,
    matched_refs: list[dict],
    rubric: list[RubricRow],
    vis_results: dict | None = None,
) -> PageScore:
    """Adjudicate every rubric row against ``facts`` and produce a PageScore.

    ``matched_refs`` is accepted and recorded (matched_ref_count) for grounding
    / traceability.

    ``vis_results`` (shape ``{row_id: {"score": int 0..3, "rationale": str}}``)
    is the reference-grounded vision adjudication. When ``None`` the behavior is
    EXACTLY as before: every VIS / DET∧VIS row that lacks a computed DET fact is
    reported "skipped:needs_vision". When provided, rows WITH a vis_result are
    adjudicated (earned / not_earned / fired) and leave the skipped set; VIS rows
    with NO vis_result entry stay "skipped:needs_vision". DET-gates-VIS and the
    anti-reward-hacking caps (spec §6.3) apply.
    """
    vis_results = vis_results or {}
    row_results: list[RowResult] = []
    skipped_vis: list[str] = []
    skipped_fact: list[str] = []
    hard_fail_ids: list[str] = []
    defects: list[Defect] = []

    earned_positive = 0
    fired_penalty = 0

    for row in rubric:
        # 1. A negative row with a computed DET fact is adjudicated
        #    DETERMINISTICALLY even when its detect names VIS. Firing a penalty
        #    / hard-fail on detected DET evidence (a missing slot, dead space)
        #    is conservative -- it can only penalize, never over-credit -- so
        #    the no-VIS-over-credit rule does NOT apply here. (The rule guards
        #    POSITIVE awards: we never hand out a DET∧VIS reward on the DET half
        #    alone; see branch 2.)
        det_fact_negative = (
            row.polarity == "negative" and row.fact_key is not None
        )

        # 2. A row needing vision and lacking a DET fact: adjudicate it from
        #    ``vis_results`` if present, else skip as before.
        if "VIS" in row.detect and not det_fact_negative:
            vr = vis_results.get(row.id)
            if vr is None:
                # No vision verdict -> unchanged behavior: skipped:needs_vision.
                row_results.append(RowResult(
                    row.id, "skipped:needs_vision", 0,
                    f"{row.detect} requires vision model (not wired)"))
                skipped_vis.append(row.id)
                continue

            vis_score = int(vr.get("score", 0))
            rationale = str(vr.get("rationale", ""))

            if row.polarity == "positive":
                gate_passed, gate_proven = (True, True)
                # DET∧VIS rows are DET-gated (spec §6.3). A "VIS"/"VIS+DET" row
                # (e.g. P12 magazine density) is pure-VIS with no DET gate.
                if row.detect == "DET∧VIS":
                    gate_passed, gate_proven = _det_gate(row.id, facts)
                if vis_score >= VIS_EARN_THRESHOLD and gate_passed:
                    rr = RowResult(
                        row.id, "earned", row.weight,
                        f"VIS {vis_score}>={VIS_EARN_THRESHOLD} & DET gate ok "
                        f"-> earned +{row.weight}: {rationale}")
                    earned_positive += rr.points
                elif vis_score >= VIS_EARN_THRESHOLD and not gate_proven:
                    rr = RowResult(
                        row.id, "not_earned", 0,
                        f"VIS high but DET gate unproven -> not awarded: {rationale}")
                elif vis_score >= VIS_EARN_THRESHOLD and not gate_passed:
                    rr = RowResult(
                        row.id, "not_earned", 0,
                        f"VIS high but DET gate failed -> not awarded: {rationale}")
                else:
                    rr = RowResult(
                        row.id, "not_earned", 0,
                        f"VIS {vis_score}<{VIS_EARN_THRESHOLD} -> not earned: {rationale}")
                row_results.append(rr)
            else:  # negative VIS row (e.g. N07, N10)
                if vis_score >= VIS_FIRE_THRESHOLD:
                    points = 0 if row.hard_fail else row.weight
                    rr = RowResult(
                        row.id, "fired", points,
                        f"VIS {vis_score}>={VIS_FIRE_THRESHOLD} tripped {row.id}: "
                        f"{rationale}")
                    row_results.append(rr)
                    if row.hard_fail:
                        hard_fail_ids.append(row.id)
                        severity = "hard_fail"
                    else:
                        fired_penalty += -rr.points  # rr.points is negative
                        severity = "weighted"
                    defects.append(Defect(
                        id=row.id, severity=severity, knob_class=row.knob_class,
                        target=row.fact_key or row.id, detail=rr.detail))
                else:
                    row_results.append(RowResult(
                        row.id, "clear", 0,
                        f"VIS {vis_score}<{VIS_FIRE_THRESHOLD} did not trip {row.id}"))
            continue

        # 3. Pure-DET row with no computed fact -> needs_fact. ----------------
        if row.fact_key is None:
            row_results.append(RowResult(
                row.id, "skipped:needs_fact", 0,
                f"DET row {row.id} has no computed fact yet"))
            skipped_fact.append(row.id)
            continue

        # 4. Row WITH a fact -> evaluate. ------------------------------------
        if row.polarity == "positive":
            rr = _eval_positive(row, facts)
            row_results.append(rr)
            if rr.status == "earned":
                earned_positive += rr.points
        else:  # negative
            rr = _eval_negative(row, facts)
            row_results.append(rr)
            if rr.status == "fired":
                if row.hard_fail:
                    hard_fail_ids.append(row.id)
                    severity = "hard_fail"
                    target = row.fact_key
                else:
                    fired_penalty += -rr.points  # rr.points is negative
                    severity = "weighted"
                    target = row.fact_key
                defects.append(Defect(
                    id=row.id,
                    severity=severity,
                    knob_class=row.knob_class,
                    target=target,
                    detail=rr.detail,
                ))

    # Raw points: earned positives minus fired penalties (hard-fails carry 0). #
    raw_points = earned_positive - fired_penalty

    # Normalize to the author's scale against the EARNABLE positive max (the
    # capability-clamped denominator, §5.5), so the gate is reachable + honest.
    pmax = _earnable_positive_max(
        facts, vis_results, rubric, getattr(facts, "st_type", "all")
    )
    clamped = max(0, min(raw_points, pmax))
    raw_pct = clamped / pmax if pmax else 0.0
    reward = 1_000_000 * raw_pct

    # Rank defects: hard-fails first, then larger penalties first. ------------
    def _rank(d: Defect):
        is_hard = 0 if d.severity == "hard_fail" else 1
        # weighted defects: bigger penalty (more negative weight) ranks higher.
        penalty_magnitude = 0
        for row in rubric:
            if row.id == d.id and not row.hard_fail:
                penalty_magnitude = -row.weight
                break
        return (is_hard, -penalty_magnitude, d.id)

    defects.sort(key=_rank)

    return PageScore(
        reward=reward,
        raw_points=raw_points,
        hard_fail=bool(hard_fail_ids),
        hard_fail_ids=hard_fail_ids,
        row_results=row_results,
        defects=defects,
        skipped_vis=skipped_vis,
        skipped_fact=skipped_fact,
        matched_ref_count=len(matched_refs or []),
    )


def cleared(score: PageScore, threshold: int = 950_000) -> bool:
    """Ship verdict: clears iff reward meets the bar AND no hard-fail latched.

    The ``and not score.hard_fail`` clause is the hard-fail DOMINANCE rule: a
    structural defect (missing photo, font fallback, placeholder leak) makes the
    page un-shippable regardless of how high its reward climbed.
    """
    return (score.reward >= threshold) and (not score.hard_fail)
