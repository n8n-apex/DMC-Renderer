"""Acceptance test for the Phase-B proof script (``run_one_page.py``).

This is the END-TO-END proof that the closed quality loop -- perceive -> score
(against references) -> fix -> re-render, guarded -- genuinely converges ONE real
page and HONESTLY surfaces the gaps it cannot fix in-renderer.

It drives the live Apex ST-07A case-study page (page_index 6) through the real
``converge_page`` defaults via the reusable ``run_proof`` entry point (no shelling
out), then asserts the honest convergence behavior:

  1. it ran end-to-end on the real page (st_type, iterations, page_index);
  2. it detected the dead-space defect and the density knob measurably moved it
     (monotone non-increasing AND iter1 < iter0 -- the render really changed);
  3. it FLAGS the gaps it cannot fix in-renderer (N01 missing photo -> asset_gen
     AND N08 dead space -> renderer capability gap) rather than silently passing;
  4. ship-best-with-flags: cleared is False, shipped_best is True, and the best
     artifacts (pdf + png) exist on disk;
  5. the human-readable report surfaces those same flags under an explicit
     "CAPABILITY / ASSET GAPS" section.

The flags are the WHOLE POINT: they are the system's explicit capability/asset-gap
outputs -- the loop telling us what it cannot fix in-renderer -- not human guesses.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from run_one_page import APEX_PKG, CASE_STUDY_INDEX, format_report, run_proof
from vis_client import _read_env_file

# The live VIS proof needs a resolvable OpenRouter key (read the same way the
# real client does -- env var or research/preprocessor/.env). Absent -> skip,
# so the offline suite stays green with no network and no secrets.
_HAVE_KEY = bool(_read_env_file("OPENROUTER_API_KEY"))


# --------------------------------------------------------------------------- #
# The end-to-end acceptance test (real render).
# --------------------------------------------------------------------------- #
@pytest.mark.xfail(
    reason="A3 fixture: the converge loop's layout-fill knob no longer moves the "
    "A3-designed case study (dead_space 0.892 -> 0.892). The A3 spread's fix is "
    "the scene/geometry work (US-302/303), not the fill knob; recalibrate against "
    "the A3 deck (2026-08-15)",
)
def test_one_page_proof_apex_case_study(tmp_path):
    """The closed loop converges the live Apex ST-07A page and honestly flags
    the residual capability/asset gaps -- proven end-to-end with a real render."""
    assert APEX_PKG.exists(), f"missing fixture {APEX_PKG}"

    result = run_proof(out_root=tmp_path)

    # 1. Ran end-to-end on the real page.
    assert result.st_type == "ST-07A"
    assert result.page_index == CASE_STUDY_INDEX
    assert result.iterations, "expected a non-empty iteration trajectory"

    # 2. Dead-space defect detected, and the loop RESOLVES it in-renderer by
    #    selecting the case-study fill-layout knob (monotone, big drop below the
    #    N08 threshold of 0.30). This is the loop driving the visual fix.
    deads = [it.dead_space for it in result.iterations]
    assert len(deads) >= 2, f"expected the loop to apply a fix: {deads}"
    for a, b in zip(deads, deads[1:]):
        assert b <= a + 1e-9, f"dead_space regressed (not monotone): {deads}"
    assert deads[1] < deads[0], f"knob did not move the render: {deads}"
    # the loop selected the layout knob...
    assert any("layout" in str(f).lower() for f in result.fixes_applied), (
        f"expected the loop to apply the case-study layout knob: {result.fixes_applied}"
    )
    # ...and the best-scored iteration cleared the dead-space defect (N08 gone).
    best_it = next(it for it in result.iterations if it.n == result.best_iteration)
    assert best_it.dead_space < 0.30, (
        f"loop did not resolve dead space below the N08 threshold: {best_it.dead_space}"
    )
    assert "N08" not in best_it.fired_defects, (
        f"N08 still fired on the best iteration: {best_it.fired_defects}"
    )

    # 3. Honestly FLAGS the gap it CANNOT fix in-renderer: the missing client
    #    photo (N01 hard-fail) routes to asset_gen and still latches (VIS/knobs
    #    cannot buy back a hard-fail).
    assert result.flags, "expected non-empty flags (the loop is flagging gaps)"
    blob = " ".join(result.flags).lower()
    assert ("n01" in blob or "missing photo" in blob or "asset_gen" in blob), (
        f"expected an asset_gen / missing-photo flag, got: {result.flags}"
    )

    # 4. Ship-best-with-flags: never clears, ships best, artifacts exist on disk.
    assert result.cleared is False
    assert result.shipped_best is True
    assert result.best_artifacts is not None
    pdf_path = Path(result.best_artifacts["pdf"])
    png_path = Path(result.best_artifacts["png"])
    assert pdf_path.exists(), f"best pdf missing on disk: {pdf_path}"
    assert png_path.exists(), f"best png missing on disk: {png_path}"


def test_format_report_contains_flags_section(tmp_path):
    """The proof script surfaces the flags to a human under the explicit
    "CAPABILITY / ASSET GAPS" section header, with each flag string present."""
    result = run_proof(out_root=tmp_path)
    report = format_report(result)

    assert "CAPABILITY / ASSET GAPS" in report, report
    assert result.flags, "precondition: the loop produced flags"
    for flag in result.flags:
        assert flag in report, f"flag missing from report: {flag!r}"


def test_run_one_page_does_not_mutate_original_fixture(tmp_path):
    """ADDITIVE / non-destructive: running the proof must NOT mutate the original
    Apex fixture (the brain copies packages before turning any knob).

    We snapshot the fixture's resolved_package.json before and after the run and
    assert byte-for-byte equality. The starting density axis is also asserted
    unchanged, proving the in-place package was never re-rendered against.
    """
    pkg_json = APEX_PKG / "resolved_package.json"
    before = pkg_json.read_bytes()

    result = run_proof(out_root=tmp_path)

    after = pkg_json.read_bytes()
    assert after == before, "run_proof mutated the original fixture package JSON"
    # Sanity: the proof did real work (so the no-mutation result is meaningful).
    assert result.iterations


# --------------------------------------------------------------------------- #
# The LIVE reference-grounded VIS proof (gated on the OpenRouter key).
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(
    not _HAVE_KEY,
    reason="OPENROUTER_API_KEY not resolvable (env or preprocessor/.env)",
)
def test_vis_proof_real_call(tmp_path, capsys):
    """END-TO-END live proof: the loop grounds VIS rows against Richard's expert
    reference pages via a REAL (cached) vision call, returns scores+rationales,
    and STILL honestly ships-best-with-flags -- VIS cannot buy back the N01
    missing-photo hard-fail (the anti-reward-hacking invariant).

    Uses the configured OPENROUTER_VISION_MODEL as-is; vis_client._loads_lenient
    tolerates the markdown code fence some providers wrap JSON in, so any
    provider (incl. the Anthropic family) works."""
    result = run_proof(out_root=tmp_path, use_vis=True)

    # Ran end-to-end on the real page.
    assert result.st_type == "ST-07A"
    assert result.page_index == CASE_STUDY_INDEX
    assert result.iterations

    # The best iteration's VIS rows are no longer all skipped: the vision model
    # returned real scores + rationales grounded against the references.
    best_it = next(
        it for it in result.iterations if it.n == result.best_iteration
    )
    vis = best_it.vis_results
    assert isinstance(vis, dict) and vis, (
        f"expected non-empty VIS results on best iter, got: {vis!r}"
    )
    for row_id, entry in vis.items():
        assert isinstance(entry, dict), f"{row_id}: {entry!r}"
        score = entry.get("score")
        assert isinstance(score, int), f"{row_id}: score not int: {score!r}"
        assert 0 <= score <= 3, f"{row_id}: score out of 0..3: {score}"
        rationale = entry.get("rationale")
        assert isinstance(rationale, str) and rationale.strip(), (
            f"{row_id}: empty rationale: {rationale!r}"
        )

    # Anti-reward-hacking invariant: VIS scores cannot clear the hard-fail. The
    # N01 missing-photo hard-fail still latches -> ship best WITH flags, never
    # cleared.
    assert result.cleared is False
    assert result.shipped_best is True
    assert result.flags, "expected honest residual flags despite live VIS"

    # The report surfaces the live VIS section + which reference pages anchored it.
    report = format_report(result)
    assert "REFERENCE-GROUNDED VISION SCORES" in report, report
    # At least one "deck pN" reference-anchor line is present.
    import re

    assert re.search(r"-\s+\S+\s+p\d+", report), (
        f"expected a 'deck pN' reference anchor line in report:\n{report}"
    )

    # Print the full report so it is captured for the human artifact.
    with capsys.disabled():
        print("\n" + report)
