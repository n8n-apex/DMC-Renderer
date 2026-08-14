"""Proof for the deck-level convergence report (``run_deck.py``).

The brain's ``converge_deck`` runs the proven per-page loop across the WHOLE
deck and aggregates a deck-level report -- the system adjudicating every page,
replacing the manual per-page knob-spray. This file proves two things:

  1. ``format_deck_report`` renders a DeckResult to a human-readable report whose
     "DECK FLAGS BY OWNER" section groups every page's flags under the owner who
     must fix them (renderer / preprocessor / asset_gen / other) -- fast, fake.

  2. ``run_deck`` on the REAL Apex package converges all 20 pages with a real
     render (NO vision), and the aggregated deck_flags carry the expected honest
     gaps: an N15 prose-stat (preprocessor) flag on a case study (page 11) and an
     N01 missing-photo (asset_gen) flag on case studies. This is SLOW -- it is
     marked ``@pytest.mark.slow`` so the fast iteration run can skip it via
     ``-m "not slow"`` -- but it MUST be runnable and is the deliverable artifact.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from brain import DeckResult, PageResult
from run_deck import APEX_PKG, format_deck_report, run_deck


# --------------------------------------------------------------------------- #
# Fake DeckResult builder (no real render; fast).
# --------------------------------------------------------------------------- #
def _page(page_index: int, st_type: str, *, cleared: bool, reward: float,
          flags: list[str]) -> PageResult:
    return PageResult(
        page_index=page_index,
        st_type=st_type,
        cleared=cleared,
        best_reward=reward,
        best_iteration=0,
        iterations=[],
        fixes_applied=[],
        flags=flags,
        shipped_best=True,
        best_artifacts=None,
    )


def _deck_result(pages: list[PageResult]) -> DeckResult:
    """Build a DeckResult the way converge_deck would -- aggregating flags."""
    deck_flags: list[dict] = []
    seen: set[tuple[int, str]] = set()
    for p in pages:
        for flag in p.flags:
            key = (p.page_index, flag)
            if key in seen:
                continue
            seen.add(key)
            deck_flags.append(
                {"page_index": p.page_index, "st_type": p.st_type, "flag": flag}
            )
    return DeckResult(
        pages=pages,
        deck_flags=deck_flags,
        cleared_count=sum(1 for p in pages if p.cleared),
        total=len(pages),
    )


# --------------------------------------------------------------------------- #
# 5. format_deck_report groups flags by owner (fast, fake-driven).
# --------------------------------------------------------------------------- #
def test_format_deck_report_groups_by_owner():
    """A DeckResult whose flags span asset_gen + preprocessor + renderer must
    render a "DECK FLAGS BY OWNER" section listing those three owners with the
    flags grouped under each."""
    asset_flag = "N01 required_slots_missing -> asset_gen"
    prep_flag = "N15 non_numeral_stat_values -> preprocessor"
    rend_flag = "N08 residual after density exhausted -> renderer capability gap"

    pages = [
        _page(0, "ST-01", cleared=True, reward=960_000.0, flags=[]),
        _page(6, "ST-07A", cleared=False, reward=400_000.0,
              flags=[asset_flag, rend_flag]),
        _page(11, "ST-07A", cleared=False, reward=380_000.0,
              flags=[asset_flag, prep_flag]),
    ]
    result = _deck_result(pages)
    report = format_deck_report(result)

    # The per-page table is present with each page's index + st_type.
    assert "ST-07A" in report
    assert "11" in report

    # The owner-grouped section header is present.
    assert "DECK FLAGS BY OWNER" in report, report

    # Each owner heading appears...
    for owner in ("renderer", "preprocessor", "asset_gen"):
        assert owner in report, f"missing owner heading {owner!r} in:\n{report}"

    # ...and each owner's flag text is grouped under the report.
    assert "N01" in report
    assert "N15" in report
    assert "N08" in report

    # The asset_gen flag (on two pages) must appear under asset_gen, with the
    # preprocessor + renderer flags under their owners. Verify ordering: the
    # owner heading precedes its flag's defect id.
    def _idx(needle: str) -> int:
        return report.index(needle)

    assert _idx("preprocessor") < _idx("N15")
    assert _idx("asset_gen") < report.rindex("N01")
    assert _idx("renderer") < _idx("N08")


def test_format_deck_report_unknown_owner_goes_to_other():
    """A flag string with no parseable owner falls under an 'other' grouping so
    nothing is silently dropped from the report."""
    weird = "no-progress / oscillation: fired-defect set unchanged"
    pages = [_page(3, "ST-09", cleared=False, reward=200_000.0, flags=[weird])]
    report = format_deck_report(_deck_result(pages))

    assert "other" in report.lower()
    assert "oscillation" in report


# --------------------------------------------------------------------------- #
# 6. REAL deck render (slow; NO vis). The whole-deck proof artifact.
# --------------------------------------------------------------------------- #
@pytest.mark.slow
def test_real_deck_converges_all_pages(tmp_path, capsys):
    """Run the REAL Apex package through converge_deck (NO vision) -- the system
    adjudicates every one of the 20 pages. The aggregated deck_flags must carry
    the honest gaps: an N15 prose-stat (preprocessor) flag on case study page 11,
    and an N01 missing-photo (asset_gen) flag on case studies. Prints the deck
    report so it is captured as the human artifact."""
    assert APEX_PKG.exists(), f"missing fixture {APEX_PKG}"

    result = run_deck(out_root=tmp_path)

    # Adjudicated all 20 pages, one PageResult each, in page order.
    assert result.total == 20
    assert len(result.pages) == 20
    assert [p.page_index for p in result.pages] == list(range(20))

    # N15 prose-stat preprocessor flag on case study page 11.
    p11_flags = [e for e in result.deck_flags if e["page_index"] == 11]
    assert any("N15" in e["flag"] for e in p11_flags), p11_flags
    assert any("preprocessor" in e["flag"] for e in p11_flags), p11_flags

    # N01 missing-photo asset_gen flag on at least one case study (ST-07A).
    n01_case_study = [
        e for e in result.deck_flags
        if "N01" in e["flag"] and "asset_gen" in e["flag"]
        and e["st_type"] == "ST-07A"
    ]
    assert n01_case_study, (
        "expected an N01 asset_gen flag on a case study; "
        f"deck_flags={result.deck_flags}"
    )

    # Print the whole-deck report (the deliverable artifact).
    with capsys.disabled():
        print("\n" + format_deck_report(result))
