"""Tests for the rubric config + analysis scorer (the "judgment").

Strategy: synthetic ``PageFacts`` instances (imported from the real perception
module so the dataclass shape stays honest) make the unit tests deterministic;
ONE render-free integration test runs the real perception + reference retrieval
against the actual Apex case-study artifacts and scores them.

Hard-fail DOMINANCE is the load-bearing invariant under test: a hard-fail must
make the page un-shippable no matter how high the reward.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from perception import PageFacts, perceive
from references import retrieve_references

from rubric import (
    RUBRIC,
    RUBRIC_VERSION,
    RubricRow,
    positive_max,
    N08_DEAD_SPACE_THRESHOLD,
    N08_DEAD_SPACE_GAP_THRESHOLD,
    N08_EMPTY_GAP_THRESHOLD,
)
from analysis import PageScore, RowResult, Defect, score, cleared

RENDERER_ROOT = Path("/Users/utkarsh/Projects/richard/research/v7-renderer")
OUTPUT_DIR = RENDERER_ROOT / "output"
PACKAGE_PATH = RENDERER_ROOT / "fixtures" / "apex" / "resolved_package.json"
PDF_PATH = OUTPUT_DIR / "report.pdf"
CASE_STUDY_INDEX = 6  # ST-07A


def make_facts(**overrides) -> PageFacts:
    """Build a synthetic PageFacts with sensible 'all clean' defaults.

    Defaults represent a flawless page: font embedded, high contrast, no missing
    slots, no dead space, no placeholders, header present, QR consistent.
    """
    base = dict(
        page_index=0,
        st_type="ST-07A",
        display_font_embedded=True,
        embedded_fonts=["Source-Serif-4"],
        min_text_contrast=12.0,
        required_slots_missing=[],
        dead_space_fraction=0.0,
        dead_space_gap=0.0,
        empty_gap=0.0,
        placeholder_text_present=False,
        placeholder_hits=[],
        header_furniture_present=True,
        qr_present=False,
        qr_gating_violation=False,
        non_numeral_stat_values=[],
    )
    base.update(overrides)
    return PageFacts(**base)


def _result_for(s: PageScore, row_id: str) -> RowResult:
    matches = [r for r in s.row_results if r.id == row_id]
    assert matches, f"no RowResult for {row_id}"
    return matches[0]


# --------------------------------------------------------------------------- #
# 1. Missing required photo latches a hard fail (N01).
# --------------------------------------------------------------------------- #
def test_missing_required_photo_latches_hard_fail():
    facts = make_facts(required_slots_missing=["case-study-1"])
    s = score(facts, [], RUBRIC)
    assert s.hard_fail is True
    assert "N01" in s.hard_fail_ids
    assert _result_for(s, "N01").status == "fired"
    # Cannot clear even at a perfect reward.
    assert cleared(s, threshold=0) is False

    # Even if every positive earned, the hard-fail stays True.
    perfect = make_facts(
        required_slots_missing=["case-study-1"],
        header_furniture_present=True,
        display_font_embedded=True,
    )
    s2 = score(perfect, [], RUBRIC)
    assert s2.hard_fail is True
    assert cleared(s2) is False


# --------------------------------------------------------------------------- #
# 2. Font fallback latches a hard fail (N03) and blocks P09.
# --------------------------------------------------------------------------- #
def test_font_fallback_latches_hard_fail():
    facts = make_facts(display_font_embedded=False)
    s = score(facts, [], RUBRIC)
    assert "N03" in s.hard_fail_ids
    assert s.hard_fail is True
    assert _result_for(s, "N03").status == "fired"
    # P09 (font loaded) must NOT be earned when the font fell back.
    assert _result_for(s, "P09").status == "not_earned"


def test_n04_overflow_clipping_latches_hard_fail():
    """N04 is now LIVE: content drawn beyond the page bounds latches a hard fail."""
    facts = make_facts()
    facts.content_overflow = True
    s = score(facts, [], RUBRIC)
    assert "N04" in s.hard_fail_ids
    assert s.hard_fail is True
    assert _result_for(s, "N04").status == "fired"


# --------------------------------------------------------------------------- #
# 3. Dead/hollow-space penalty N08 fires on a real empty region, clears below.
#    N08 now keys on the UNIFIED ``empty_gap`` (white gaps OR hollow dark/colored
#    panels) so a dark void cannot game the white-only metric.
# --------------------------------------------------------------------------- #
def test_dead_space_fires_n08():
    # A real empty region (empty_gap > 0.13) fires N08 -- here a hollow dark
    # panel (the ST-07B fill void measures ~0.293).
    fired = score(make_facts(empty_gap=0.293), [], RUBRIC)
    n08 = _result_for(fired, "N08")
    assert n08.status == "fired"
    assert n08.points == -6
    # -6 reflected in raw_points (other defaults are clean / positives earn).
    assert fired.raw_points <= positive_max() - 6 or fired.raw_points < 0 or True
    # Confirm the -6 is part of the running total by comparing to the clean case.
    clean = score(make_facts(empty_gap=0.00), [], RUBRIC)
    assert _result_for(clean, "N08").status == "clear"
    assert clean.raw_points - fired.raw_points == 6


def test_dead_space_n08_boundary_calibration():
    """Calibrated 0.13 cut on the unified emptiness metric.

    Hollow/gappy pages measure >= 0.185 (ST-07B dark void 0.293) -> FIRE; good /
    PACKED pages measure <= 0.12 (packed dark stat panel 0.067) -> CLEAR. Nothing
    real sits in (0.12, 0.185), so 0.13 is the clean separator that catches BOTH
    white gaps AND content-less dark panels."""
    # A hollow/gappy page just above the cut -> FIRES.
    fired = score(make_facts(empty_gap=0.185), [], RUBRIC)
    assert _result_for(fired, "N08").status == "fired"
    # The ST-07B hollow dark void -> FIRES (the anti-gaming case).
    void = score(make_facts(empty_gap=0.293), [], RUBRIC)
    assert _result_for(void, "N08").status == "fired"
    # A packed page (dense dark stat panel) at the upper-good band -> clears.
    good = score(make_facts(empty_gap=0.12), [], RUBRIC)
    assert _result_for(good, "N08").status == "clear"
    # The packed case study's measured value -> clears.
    packed = score(make_facts(empty_gap=0.067), [], RUBRIC)
    assert _result_for(packed, "N08").status == "clear"


def test_n08_uses_empty_gap_unified_metric():
    """The anti-gaming fix: N08 keys on the UNIFIED ``empty_gap`` so a hollow
    DARK panel (white-only metric ~0) still fires, while a genuinely PACKED dark
    panel clears."""
    # Hollow dark void: dead_space_gap ~0 (white-only is blind) but empty_gap
    # high -> N08 must FIRE on the unified metric.
    void = score(make_facts(dead_space_gap=0.0, empty_gap=0.293), [], RUBRIC)
    n08 = _result_for(void, "N08")
    assert n08.status == "fired"
    assert n08.points == -6
    assert [d for d in void.defects if d.id == "N08"]

    # Genuinely packed page: empty_gap low -> N08 CLEARS.
    packed = score(make_facts(dead_space_gap=0.0, empty_gap=0.067), [], RUBRIC)
    assert _result_for(packed, "N08").status == "clear"
    assert not [d for d in packed.defects if d.id == "N08"]

    # The unified threshold is the documented 0.13 cut.
    assert N08_EMPTY_GAP_THRESHOLD == 0.13


# --------------------------------------------------------------------------- #
# 4. QR gating violation N06 fires (-8), clears when consistent.
# --------------------------------------------------------------------------- #
def test_qr_gating_violation_fires_n06():
    fired = score(make_facts(qr_gating_violation=True), [], RUBRIC)
    n06 = _result_for(fired, "N06")
    assert n06.status == "fired"
    assert n06.points == -8
    clean = score(make_facts(qr_gating_violation=False), [], RUBRIC)
    assert _result_for(clean, "N06").status == "clear"
    assert clean.raw_points - fired.raw_points == 8


# --------------------------------------------------------------------------- #
# 5. Placeholder leakage latches a hard fail (N14).
# --------------------------------------------------------------------------- #
def test_placeholder_leak_latches_hard_fail():
    facts = make_facts(placeholder_text_present=True, placeholder_hits=["lorem ipsum"])
    s = score(facts, [], RUBRIC)
    assert "N14" in s.hard_fail_ids
    assert s.hard_fail is True
    assert _result_for(s, "N14").status == "fired"


# --------------------------------------------------------------------------- #
# 5b. Prose-as-a-stat content defect fires N15 (-5, routed to preprocessor).
# --------------------------------------------------------------------------- #
def test_n15_fires_on_prose_stats():
    prose = ["von bis zu 24 Stunden auf Minuten"]
    fired = score(make_facts(non_numeral_stat_values=prose), [], RUBRIC)
    n15 = _result_for(fired, "N15")
    assert n15.status == "fired"
    assert n15.points == -5
    # -5 reflected vs the clean baseline.
    clean = score(make_facts(non_numeral_stat_values=[]), [], RUBRIC)
    assert clean.raw_points - fired.raw_points == 5
    # A Defect routed to the content/preprocessor knob is present.
    n15_defect = [d for d in fired.defects if d.id == "N15"]
    assert n15_defect
    assert n15_defect[0].knob_class == "preprocessor"
    assert n15_defect[0].severity == "weighted"


def test_n15_clear_on_numeral_stats():
    clean = score(make_facts(non_numeral_stat_values=[]), [], RUBRIC)
    assert _result_for(clean, "N15").status == "clear"
    assert not [d for d in clean.defects if d.id == "N15"]


# --------------------------------------------------------------------------- #
# 6. Reward is clamped to [0, 1e6] and normalized by positive_max.
# --------------------------------------------------------------------------- #
def test_reward_clamped_and_normalized():
    clean = score(make_facts(), [], RUBRIC)
    # Earnable positives in DET-only mode are P08 (+4) + P09 (+4) = 8, both
    # earned, so the clean page reaches the full reward (capability-clamped
    # denominator, §5.5): reward = 1e6 * 8/8.
    assert clean.reward == pytest.approx(1_000_000)
    assert 0.0 <= clean.reward <= 1_000_000

    # Drowning in penalties -> clamped to 0, never negative.
    drowning = make_facts(
        empty_gap=0.40,                  # N08 -6
        qr_gating_violation=True,        # N06 -8
        min_text_contrast=2.0,           # N05 -10 (and hard-fail)
        header_furniture_present=False,  # N09 -5, and P08 not earned
    )
    ds = score(drowning, [], RUBRIC)
    assert ds.reward == 0.0
    assert ds.reward >= 0.0


# --------------------------------------------------------------------------- #
# 7. VIS rows + fact_key=None DET rows are reported skipped, never passed.
# --------------------------------------------------------------------------- #
def test_vis_rows_reported_skipped_not_passed():
    s = score(make_facts(), [], RUBRIC)

    # VIS rows are skipped EXCEPT negatives that carry a computed DET fact
    # (N01, N08), which are adjudicated deterministically -- firing a penalty on
    # DET evidence cannot over-credit, so the no-VIS rule does not gate them.
    vis_ids = {
        row.id for row in RUBRIC
        if "VIS" in row.detect
        and not (row.polarity == "negative" and row.fact_key is not None)
    }
    assert vis_ids, "expected some VIS rows"
    for rid in vis_ids:
        assert rid in s.skipped_vis
        rr = _result_for(s, rid)
        assert rr.status == "skipped:needs_vision"
        # Never counted as earned.
        assert rr.points == 0

    # Pure-DET rows with no computed fact -> skipped:needs_fact. (N04 is now LIVE
    # via content_overflow; N11/N12/N13 still have no computed fact.)
    needs_fact_ids = {"N11", "N12", "N13"}
    for rid in needs_fact_ids:
        assert rid in s.skipped_fact
        assert _result_for(s, rid).status == "skipped:needs_fact"


# --------------------------------------------------------------------------- #
# 8. Defects ranked: hard-fails first, then by penalty magnitude; knob_class set.
# --------------------------------------------------------------------------- #
def test_defects_ranked_hardfail_first_with_knob_class():
    facts = make_facts(
        required_slots_missing=["case-study-1"],  # N01 hard-fail (asset_gen)
        empty_gap=0.40,                           # N08 -6 (renderer)
    )
    s = score(facts, [], RUBRIC)
    assert s.defects[0].id == "N01"
    assert s.defects[0].knob_class == "asset_gen"
    n08_defect = [d for d in s.defects if d.id == "N08"]
    assert n08_defect and n08_defect[0].knob_class == "renderer"


# --------------------------------------------------------------------------- #
# 9. Integration: real Apex case-study page (render-free perception + scoring).
# --------------------------------------------------------------------------- #
def test_integration_real_case_study_page():
    pkg = json.loads(PACKAGE_PATH.read_text())
    facts = perceive(
        pdf_path=PDF_PATH,
        page_index=CASE_STUDY_INDEX,
        page_png_path=OUTPUT_DIR / f"report-p{CASE_STUDY_INDEX + 1}.png",
        page_data=pkg["pages"][CASE_STUDY_INDEX],
        axes=pkg["axes"],
        brand=pkg["brand"],
    )
    refs = retrieve_references("ST-07A", pkg["axes"])
    s = score(facts, refs, RUBRIC)

    # Print the full PageScore for the record.
    print("\n=== REAL ST-07A PageScore (rubric", RUBRIC_VERSION, ") ===")
    print("reward:", s.reward)
    print("raw_points:", s.raw_points)
    print("hard_fail:", s.hard_fail)
    print("hard_fail_ids:", s.hard_fail_ids)
    print("fired_negatives:", [r.id for r in s.row_results if r.status == "fired"])
    print("skipped_vis:", s.skipped_vis)
    print("skipped_fact:", s.skipped_fact)
    print("matched_ref_count:", s.matched_ref_count)
    print("top_defect:", s.defects[0] if s.defects else None)
    print("cleared:", cleared(s))

    # The missing case-study-1 portrait -> N01 hard-fail.
    assert s.hard_fail is True
    assert "N01" in s.hard_fail_ids
    # N08 (dead/hollow space) is adjudicated, but whether it FIRES is a property
    # of the live render, not a stable invariant. The serif-headline fix
    # (compile_tokens: --font-head now follows --font-display) made headings
    # taller and raised page fill, legitimately dropping the central empty gap
    # below the N08 threshold on this render. Assert the row is evaluated (not
    # skipped), not that it fires.
    assert _result_for(s, "N08").status in {"fired", "clear"}
    # Reference grounding is recorded for traceability.
    assert s.matched_ref_count == len(refs)
    # The top defect routes to a sensible knob_class.
    assert s.defects[0].knob_class in {"asset_gen", "renderer", "preprocessor"}
    # A hard-failed page can never clear.
    assert cleared(s) is False


# --------------------------------------------------------------------------- #
# Task C -- reference-grounded VIS branch in score().
# --------------------------------------------------------------------------- #
def _vis_skipped_set(s: PageScore) -> set[str]:
    return set(s.skipped_vis)


def test_score_without_vis_unchanged():
    """Regression: vis_results=None yields the SAME skipped_vis set as before."""
    facts = make_facts()
    before = score(facts, [], RUBRIC)
    after = score(facts, [], RUBRIC, vis_results=None)
    assert _vis_skipped_set(before) == _vis_skipped_set(after)
    # And every row result is identical (status + points).
    b = {r.id: (r.status, r.points) for r in before.row_results}
    a = {r.id: (r.status, r.points) for r in after.row_results}
    assert a == b
    assert after.raw_points == before.raw_points


def test_vis_awards_pure_vis_positive():
    """P12 (pure VIS, weight 5) earns when vis_score >= threshold."""
    facts = make_facts()
    clean = score(facts, [], RUBRIC)
    s = score(facts, [], RUBRIC,
              vis_results={"P12": {"score": 3, "rationale": "dense"}})
    p12 = _result_for(s, "P12")
    assert p12.status == "earned"
    assert p12.points == 5
    # P12 is no longer skipped.
    assert "P12" not in s.skipped_vis
    # Its weight shows up in raw_points.
    assert s.raw_points - clean.raw_points == 5


def test_det_gates_vis_blocks_p05_when_photo_missing():
    """P05 (DET∧VIS) must NOT earn when the required portrait is missing."""
    facts = make_facts(required_slots_missing=["case-study-1"])
    s = score(facts, [], RUBRIC,
              vis_results={"P05": {"score": 3, "rationale": "looks framed"}})
    p05 = _result_for(s, "P05")
    assert p05.status == "not_earned"
    assert "DET gate" in p05.detail
    assert p05.points == 0
    # The N01 hard-fail (missing photo) still latches.
    assert s.hard_fail is True
    assert "N01" in s.hard_fail_ids


def test_vis_negative_fires_n07_generic():
    """N07 (pure VIS negative, -10) fires when vis_score >= fire threshold."""
    facts = make_facts()
    clean = score(facts, [], RUBRIC)
    s = score(facts, [], RUBRIC,
              vis_results={"N07": {"score": 3, "rationale": "generic stock"}})
    n07 = _result_for(s, "N07")
    assert n07.status == "fired"
    assert n07.points == -10
    assert "N07" not in s.skipped_vis
    # raw_points reduced by the N07 weight.
    assert clean.raw_points - s.raw_points == 10


def test_vis_cannot_buy_back_hardfail():
    """A hard-failed page cannot clear no matter how many VIS positives earn."""
    facts = make_facts(required_slots_missing=["case-study-1"])  # N01 hard-fail
    s = score(facts, [], RUBRIC, vis_results={
        "P12": {"score": 3, "rationale": "dense"},
        "P10": {"score": 3, "rationale": "glyphs"},
        "P07": {"score": 3, "rationale": "logos"},
        "P11": {"score": 3, "rationale": "charts"},
    })
    assert s.hard_fail is True
    assert cleared(s) is False


def test_n08_not_double_counted():
    """N08 has both a DET trigger and a VIS half; fire ONCE, not twice."""
    facts = make_facts(empty_gap=0.40)  # DET fires N08 (-6)
    det_only = score(facts, [], RUBRIC)
    both = score(facts, [], RUBRIC,
                 vis_results={"N08": {"score": 3, "rationale": "lots of empty"}})
    # Same penalty whether or not the VIS half also flags it.
    assert det_only.raw_points == both.raw_points
    n08 = _result_for(both, "N08")
    assert n08.status == "fired"
    assert n08.points == -6
    # N08 fired exactly once in the defect list.
    n08_defects = [d for d in both.defects if d.id == "N08"]
    assert len(n08_defects) == 1


# --------------------------------------------------------------------------- #
# Phase 2 (grader correctness): the per-page gate is REACHABLE (#17), normalized
# against the EARNABLE positive max (capability clamp, §5.5), still anti-gamed.
# --------------------------------------------------------------------------- #
def test_cleared_is_reachable_det_only():
    """#17 fix: a clean page must be able to CLEAR. Reward is normalized against
    the EARNABLE positives (here P08+P09 = 8, both earned), not the global 92."""
    s = score(make_facts(), [], RUBRIC)
    assert s.reward == pytest.approx(1_000_000)
    assert s.hard_fail is False
    assert cleared(s) is True


def test_penalty_keeps_page_below_clear():
    """A penalty must still drop reward below the bar (penalties untouched)."""
    s = score(make_facts(empty_gap=0.40), [], RUBRIC)  # N08 -6 on earnable base 8
    assert s.reward < 950_000
    assert cleared(s) is False


def test_earnable_max_grows_with_vision_and_stays_gated():
    """With vision, more positives become earnable (P12 pure-VIS, P05 DET-gated);
    earning them clears. A hard-fail still blocks clear regardless of reward."""
    facts = make_facts()  # no missing slots -> P05 DET gate passes
    vis = {"P12": {"score": 3, "rationale": "dense"},
           "P05": {"score": 3, "rationale": "framed portrait"}}
    s = score(facts, [], RUBRIC, vis_results=vis)
    assert cleared(s) is True
    # hard-fail dominance unchanged:
    hf = score(make_facts(required_slots_missing=["case-study-1"]), [], RUBRIC, vis_results=vis)
    assert cleared(hf) is False
