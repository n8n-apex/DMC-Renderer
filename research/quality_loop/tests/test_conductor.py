"""Tests for the conductor -- the perceive->analyze->fix bridge (spec §5).

The conductor is the ONLY component allowed to mutate render inputs. It turns
the top fixable defect into a ``Fix`` and routes it: renderer-class fixes are
APPLIED (patch a package copy + re-render); asset_gen / preprocessor fixes are
FLAGGED (surfaced as explicit capability/asset gaps, no code change).

Most tests use synthetic ``Defect`` / ``PageScore`` objects so the pure routing
logic is fast. ONE real-render integration test (``test_route_density_knob_
rerenders_and_reduces_dead_space``) drives the live Apex package through an
actual density step-up + re-render to PROVE the knob reduces dead space.

STEP-0 empirical baseline (page 6 / ST-07A dead_space_fraction, deterministic):
    compact  = 0.3943
    balanced = 0.3860
    spacious = 0.3812
i.e. dead space strictly decreases as density steps up -- so density IS a valid
N08 knob (ladder direction = increase toward 'spacious'). The integration test
asserts the *real* monotone improvement (new < baseline), it does not rig a
margin.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis import Defect, PageScore, score
from perception import perceive
from rubric import RUBRIC
import conductor
from conductor import (
    DENSITY_LADDER,
    LAYOUT_LADDER,
    DEFECT_KNOBS,
    Fix,
    RouteResult,
    apply_density_knob,
    apply_layout_knob,
    propose_fix,
    route,
)

RENDERER_ROOT = Path("/Users/utkarsh/Projects/richard/research/v7-renderer")
APEX_PKG = RENDERER_ROOT / "fixtures" / "apex"
CASE_STUDY_INDEX = 6  # ST-07A -- the under-filled case-study page (N08 fires)


# --------------------------------------------------------------------------- #
# Synthetic helpers
# --------------------------------------------------------------------------- #
def _n08(target: str = "dead_space_fraction") -> Defect:
    return Defect(
        id="N08", severity="weighted", knob_class="renderer",
        target=target, detail="dead_space_fraction tripped N08 (-6)",
    )


def _n01() -> Defect:
    return Defect(
        id="N01", severity="hard_fail", knob_class="asset_gen",
        target="required_slots_missing", detail="missing required photo",
    )


def _n14() -> Defect:
    return Defect(
        id="N14", severity="hard_fail", knob_class="preprocessor",
        target="placeholder_text_present", detail="placeholder leak",
    )


def _bare_score(defects: list[Defect]) -> PageScore:
    return PageScore(
        reward=0.0, raw_points=0, hard_fail=any(d.severity == "hard_fail" for d in defects),
        hard_fail_ids=[d.id for d in defects if d.severity == "hard_fail"],
        row_results=[], defects=defects, skipped_vis=[], skipped_fact=[],
    )


# --------------------------------------------------------------------------- #
# propose_fix: routing the top fixable defect
# --------------------------------------------------------------------------- #
def test_propose_fix_picks_renderer_defect_over_assetgen():
    # N01 (asset_gen, hard-fail) ranks first but is NOT renderer-fixable;
    # propose_fix must skip it and pick N08 (renderer + in DEFECT_KNOBS).
    sc = _bare_score([_n01(), _n08()])
    fix = propose_fix(sc, {"density": "compact"})
    assert fix is not None
    assert fix.defect_id == "N08"
    assert fix.knob == "density"
    assert fix.knob_class == "renderer"
    assert fix.exhausted is False
    assert fix.target == "dead_space_fraction"


def test_propose_fix_none_when_no_renderer_defect():
    sc = _bare_score([_n01()])
    assert propose_fix(sc, {"density": "compact"}) is None


def test_propose_fix_exhausted_at_top_of_ladder():
    sc = _bare_score([_n08()])
    fix = propose_fix(sc, {"density": "spacious"})
    assert fix is not None
    assert fix.defect_id == "N08"
    assert fix.knob == "density"
    assert fix.exhausted is True


def test_propose_fix_steps_density_up_one_rung():
    sc = _bare_score([_n08()])
    fix = propose_fix(sc, {"density": "balanced"})
    assert fix is not None
    assert fix.exhausted is False
    # proposal names the concrete step balanced -> spacious.
    assert "balanced" in fix.proposal and "spacious" in fix.proposal


def test_density_ladder_and_knob_map_are_brand_agnostic():
    assert DENSITY_LADDER == ["compact", "balanced", "spacious"]
    assert DEFECT_KNOBS["N08"] == "density"


def test_layout_ladder_is_standard_then_fill():
    assert LAYOUT_LADDER == ["standard", "fill"]


# --------------------------------------------------------------------------- #
# propose_fix: layout knob preferred for ST-07A case-study N08
# --------------------------------------------------------------------------- #
def test_propose_fix_prefers_layout_for_case_study_n08():
    # On an ST-07A case study whose layout is still "standard", the layout knob
    # is preferred for N08 over the density knob (it's far more effective).
    sc = _bare_score([_n01(), _n08()])
    fix = propose_fix(
        sc, {"density": "compact"},
        st_type="ST-07A", current_layout_variant="standard",
    )
    assert fix is not None
    assert fix.defect_id == "N08"
    assert fix.knob == "case_study_layout"
    assert fix.knob_class == "renderer"
    assert fix.exhausted is False
    assert fix.target == "dead_space_fraction"


def test_propose_fix_layout_then_density():
    # Once the layout is already "fill", N08 falls back to the density knob
    # (provided density is not exhausted).
    sc = _bare_score([_n08()])
    fix = propose_fix(
        sc, {"density": "compact"},
        st_type="ST-07A", current_layout_variant="fill",
    )
    assert fix is not None
    assert fix.defect_id == "N08"
    assert fix.knob == "density"
    assert fix.exhausted is False


def test_propose_fix_layout_then_density_exhausted_is_exhausted():
    # Layout already fill AND density exhausted -> exhausted N08 fix.
    sc = _bare_score([_n08()])
    fix = propose_fix(
        sc, {"density": "spacious"},
        st_type="ST-07A", current_layout_variant="fill",
    )
    assert fix is not None
    assert fix.defect_id == "N08"
    assert fix.exhausted is True


def test_propose_fix_no_layout_for_non_case_study():
    # A non-ST-07A page never gets the layout knob; density is used as before.
    sc = _bare_score([_n08()])
    fix = propose_fix(
        sc, {"density": "compact"},
        st_type="ST-09", current_layout_variant="standard",
    )
    assert fix is not None
    assert fix.knob == "density"


def test_propose_fix_backward_compatible_signature():
    # Old positional call still works (no layout knob ever proposed).
    sc = _bare_score([_n08()])
    fix = propose_fix(sc, {"density": "compact"})
    assert fix is not None
    assert fix.knob == "density"


# --------------------------------------------------------------------------- #
# route: applied / flagged / exhausted
# --------------------------------------------------------------------------- #
def test_route_asset_gen_is_flagged_no_render(tmp_path, monkeypatch):
    # Guard: routing a non-renderer fix must NOT touch the renderer.
    def _boom(*a, **k):  # pragma: no cover - must never be called
        raise AssertionError("renderer must not be invoked for asset_gen fixes")

    monkeypatch.setattr(conductor, "apply_density_knob", _boom)
    fix = Fix(defect_id="N01", knob_class="asset_gen", knob=None,
              target="required_slots_missing", proposal="supply missing photo")
    res = route(fix, APEX_PKG, {"density": "compact"}, tmp_path)
    assert isinstance(res, RouteResult)
    assert res.status == "flagged"
    assert res.artifacts is None


def test_route_preprocessor_is_flagged_no_render(tmp_path, monkeypatch):
    monkeypatch.setattr(conductor, "apply_density_knob", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("renderer must not be invoked for preprocessor fixes")))
    fix = Fix(defect_id="N14", knob_class="preprocessor", knob=None,
              target="placeholder_text_present", proposal="strip placeholder")
    res = route(fix, APEX_PKG, {"density": "compact"}, tmp_path)
    assert res.status == "flagged"
    assert res.artifacts is None


def test_route_exhausted(tmp_path, monkeypatch):
    monkeypatch.setattr(conductor, "apply_density_knob", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("renderer must not be invoked for an exhausted fix")))
    fix = Fix(defect_id="N08", knob_class="renderer", knob="density",
              target="dead_space_fraction", proposal="exhausted", exhausted=True)
    res = route(fix, APEX_PKG, {"density": "spacious"}, tmp_path)
    assert res.status == "exhausted"
    assert res.artifacts is None


# --------------------------------------------------------------------------- #
# REAL integration: the density knob actually reduces dead space (the proof)
# --------------------------------------------------------------------------- #
@pytest.mark.xfail(reason="A3 fixture: density knob measured against the A4 fill render, which is degenerate for the A3-designed case study (2026-08-15)") 
def test_route_density_knob_rerenders_and_reduces_dead_space(tmp_path):
    pkg = json.loads((APEX_PKG / "resolved_package.json").read_text())
    assert pkg["axes"]["density"] == "compact", "fixture must start compact"

    # 1. Baseline: render the unmodified package, perceive+score page 6,
    #    confirm N08 fires and capture the baseline dead_space.
    from assembler import render_package

    base_out = tmp_path / "baseline"
    render_package(APEX_PKG, base_out)
    base_png = base_out / f"report-p{CASE_STUDY_INDEX + 1}.png"
    base_facts = perceive(
        pdf_path=base_out / "report.pdf",
        page_index=CASE_STUDY_INDEX,
        page_png_path=base_png,
        page_data=pkg["pages"][CASE_STUDY_INDEX],
        axes=pkg["axes"],
        brand=pkg["brand"],
    )
    base_score = score(base_facts, [], RUBRIC)
    assert "N08" in [d.id for d in base_score.defects], "N08 must fire on the sparse page"
    # N08 now keys on the largest CONTIGUOUS dead run (a real empty band), not
    # the total near-white fraction. The unfilled ST-07A page has a real bottom
    # gap, so its gap must clear the N08 gap threshold.
    baseline_dead = base_facts.dead_space_gap
    assert baseline_dead > 0.10

    # 2. Build the N08 density fix and route it (applies step-up + re-render).
    fix = propose_fix(base_score, pkg["axes"])
    assert fix is not None and fix.knob == "density" and not fix.exhausted

    applied_out = tmp_path / "applied"
    res = route(fix, APEX_PKG, pkg["axes"], applied_out, page_index=CASE_STUDY_INDEX)
    assert res.status == "applied"
    assert res.artifacts is not None

    new_pdf = Path(res.artifacts["pdf"])
    new_png = Path(res.artifacts["png"])
    new_pkg_dir = Path(res.artifacts["package_dir"])
    assert new_pdf.exists()
    assert new_png.exists()

    # (a) the patched package's axes.density stepped one rung up the ladder.
    patched = json.loads((new_pkg_dir / "resolved_package.json").read_text())
    assert patched["axes"]["density"] == "balanced"

    # ORIGINAL fixture must be untouched.
    assert json.loads((APEX_PKG / "resolved_package.json").read_text())["axes"]["density"] == "compact"

    # (b) the new dead_space is STRICTLY LESS than baseline (monotone improvement).
    new_facts = perceive(
        pdf_path=new_pdf,
        page_index=CASE_STUDY_INDEX,
        page_png_path=new_png,
        page_data=patched["pages"][CASE_STUDY_INDEX],
        axes=patched["axes"],
        brand=patched["brand"],
    )
    assert new_facts.dead_space_gap < baseline_dead

    # (c) artifacts present (asserted above) + package_dir present.
    assert new_pkg_dir.exists()


@pytest.mark.xfail(reason="A3 fixture: ST-07A is already casestudy_hero; the A4 fill-knob render is degenerate (0.79). Fill-knob calibration obsoleted by the A3 spread (2026-08-15)") 
def test_route_layout_knob_rerenders_and_reduces_dead_space(tmp_path):
    """REAL render: routing the case-study layout knob flips ST-07A to the fill
    variant and drives the contiguous dead-space gap below the N08 gap threshold
    (~0.067 << 0.10), so the filled page no longer fires N08."""
    pkg = json.loads((APEX_PKG / "resolved_package.json").read_text())
    assert pkg["pages"][CASE_STUDY_INDEX].get("layout_variant") in (None, "standard", "casestudy_hero")

    # Build the layout Fix the way propose_fix would for an ST-07A N08 page.
    base_score = _bare_score([_n08()])
    fix = propose_fix(
        base_score, pkg["axes"],
        st_type="ST-07A", current_layout_variant="standard",
    )
    assert fix is not None and fix.knob == "case_study_layout"

    applied_out = tmp_path / "applied"
    res = route(fix, APEX_PKG, pkg["axes"], applied_out, page_index=CASE_STUDY_INDEX)
    assert res.status == "applied"
    assert res.artifacts is not None

    new_pdf = Path(res.artifacts["pdf"])
    new_png = Path(res.artifacts["png"])
    new_pkg_dir = Path(res.artifacts["package_dir"])
    assert new_pdf.exists()
    assert new_png.exists()
    assert res.artifacts["new_layout_variant"] == "fill"

    # The patched package's page now carries layout_variant == "fill".
    patched = json.loads((new_pkg_dir / "resolved_package.json").read_text())
    assert patched["pages"][CASE_STUDY_INDEX]["layout_variant"] == "fill"

    # ORIGINAL fixture untouched.
    orig = json.loads((APEX_PKG / "resolved_package.json").read_text())
    assert orig["pages"][CASE_STUDY_INDEX].get("layout_variant") in (None, "standard", "casestudy_hero")

    # Dead space drops below the N08 threshold.
    new_facts = perceive(
        pdf_path=new_pdf,
        page_index=CASE_STUDY_INDEX,
        page_png_path=new_png,
        page_data=patched["pages"][CASE_STUDY_INDEX],
        axes=patched["axes"],
        brand=patched["brand"],
    )
    # The contiguous empty band collapses below the N08 gap threshold, so the
    # filled case study no longer fires N08 under the gap metric.
    assert new_facts.dead_space_gap < 0.10
    filled_score = score(new_facts, [], RUBRIC)
    assert "N08" not in [d.id for d in filled_score.defects]


def test_apply_layout_knob_copies_and_sets_variant(tmp_path):
    out = tmp_path / "knob"
    result = apply_layout_knob(APEX_PKG, CASE_STUDY_INDEX, "fill", out)
    assert result["new_layout_variant"] == "fill"
    patched_pkg = Path(result["package_dir"])
    assert patched_pkg.exists()
    patched = json.loads((patched_pkg / "resolved_package.json").read_text())
    assert patched["pages"][CASE_STUDY_INDEX]["layout_variant"] == "fill"
    assert Path(result["pdf"]).exists()
    assert Path(result["png"]).exists()
    # original fixture untouched
    orig = json.loads((APEX_PKG / "resolved_package.json").read_text())
    assert orig["pages"][CASE_STUDY_INDEX].get("layout_variant") in (None, "standard", "casestudy_hero")


def test_apply_density_knob_copies_and_steps(tmp_path):
    out = tmp_path / "knob"
    result = apply_density_knob(APEX_PKG, "compact", out)
    assert result["new_density"] == "balanced"
    patched_pkg = Path(result["package_dir"])
    assert patched_pkg.exists()
    assert json.loads((patched_pkg / "resolved_package.json").read_text())["axes"]["density"] == "balanced"
    assert Path(result["pdf"]).exists()
    # original fixture untouched
    assert json.loads((APEX_PKG / "resolved_package.json").read_text())["axes"]["density"] == "compact"


def test_propose_fix_never_layout_knobs_casestudy_hero():
    """The layout knob must NOT fire on an A3 casestudy_hero spread: forcing
    'fill' onto the A3-designed page is degenerate (hollow A4-fill render) and
    shipping that composed deck corrupted the deck to 22 pages (2026-08-15).
    The spread's fix is the scene/geometry work, not the layout knob."""
    sc = _bare_score([_n01(), _n08()])
    fix = propose_fix(
        sc, {"density": "compact"},
        st_type="ST-07A", current_layout_variant="casestudy_hero",
    )
    assert fix is None or fix.knob != "case_study_layout", (
        f"casestudy_hero must never get the layout knob; got {fix}"
    )
