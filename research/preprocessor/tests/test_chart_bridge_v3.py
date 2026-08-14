"""SVG charts must draw the client's approved figures, never a reformat."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
RENDERER = ROOT / "research" / "v7-renderer"
if str(RENDERER) not in sys.path:
    sys.path.insert(0, str(RENDERER))

from contracts_v3.render_contract import (  # noqa: E402
    CompositionBreakdownElement,
    FormulaLadderElement,
    GroupedComparisonElement,
    ShareElement,
    TimeSeriesElement,
)
from families import chart_bridge  # noqa: E402


@pytest.mark.parametrize(
    "verbatim,expected",
    [
        ("13.160 €", 13160.0),   # German thousands dot
        ("4,9 von 5", 4.9),      # German decimal comma
        ("30 Minuten", 30.0),
        ("70 %", 70.0),
        ("1.234.567", 1234567.0),
        ("keine Zahl", None),
    ],
)
def test_german_figures_parse_to_the_right_magnitude(verbatim, expected) -> None:
    assert chart_bridge.magnitude(verbatim) == expected


def test_a_transition_prints_both_figures_exactly_as_written() -> None:
    element = GroupedComparisonElement(
        element_id="face.01.rail.gc.01", region_id="rail",
        before_claim_id="b", after_claim_id="a",
        label_content_ref="l", required_visibility=True,
    )
    svg = chart_bridge.render(
        element,
        content_by_ref={"l": "Onboarding-Zeit"},
        claim_values={"b": "30 Minuten", "a": "2 Minuten"},
    )

    assert svg.startswith("<svg") and "30 Minuten" in svg and "2 Minuten" in svg
    # The reformatted forms must NOT appear.
    assert ">30<" not in svg


def test_a_money_ladder_keeps_its_thousands_separators() -> None:
    """13.160 must never print as 13160."""
    element = FormulaLadderElement(
        element_id="face.01.rail.fl.01", region_id="rail",
        operand_claim_ids=("o1", "o2"), result_claim_id="r",
        label_content_ref="l", required_visibility=True,
    )
    svg = chart_bridge.render(
        element,
        content_by_ref={"l": "Jahreskosten"},
        claim_values={"o1": "13.160 €", "o2": "12", "r": "157.920 €"},
    )

    assert "13.160 €" in svg and "157.920 €" in svg
    assert "13160" not in svg and "157920" not in svg


def test_a_money_breakdown_becomes_the_money_infographic() -> None:
    element = CompositionBreakdownElement(
        element_id="face.01.rail.cb.01", region_id="rail",
        part_claim_ids=("p1", "p2"),
        label_content_ref="l", required_visibility=True,
    )
    spec = chart_bridge.spec_for(
        element,
        content_by_ref={"l": "Kostenblöcke"},
        claim_values={"p1": "13.160 €", "p2": "4.200 €"},
    )

    assert spec.kind == "money_infographic"


def test_a_percent_breakdown_becomes_a_ring_not_money() -> None:
    element = CompositionBreakdownElement(
        element_id="face.01.rail.cb.01", region_id="rail",
        part_claim_ids=("p1", "p2"),
        label_content_ref="l", required_visibility=True,
    )
    spec = chart_bridge.spec_for(
        element,
        content_by_ref={"l": "Anteile"},
        claim_values={"p1": "30 %", "p2": "50 %"},
    )

    assert spec.kind == "donut"


def test_an_unreadable_figure_draws_nothing_rather_than_inventing_one() -> None:
    element = ShareElement(
        element_id="face.01.rail.share.01", region_id="rail",
        claim_id="c", label_content_ref="l", required_visibility=True,
    )

    assert chart_bridge.render(
        element,
        content_by_ref={"l": "Anteil"},
        claim_values={"c": "ein grosser Teil"},
    ) == ""


def test_a_series_plots_every_point_it_was_given() -> None:
    element = TimeSeriesElement(
        element_id="face.01.rail.ts.01", region_id="rail",
        point_claim_ids=("a", "b", "c"),
        label_content_ref="l", required_visibility=True,
    )
    svg = chart_bridge.render(
        element,
        content_by_ref={"l": "Angebote"},
        claim_values={"a": "310", "b": "540", "c": "780"},
    )

    assert svg.startswith("<svg")
    for figure in ("310", "540", "780"):
        assert figure in svg


def test_charts_use_brand_tokens_not_hardcoded_colour() -> None:
    """An off-brand chart is a defect even when the numbers are right."""
    element = ShareElement(
        element_id="face.01.rail.share.01", region_id="rail",
        claim_id="c", label_content_ref="l", required_visibility=True,
    )
    svg = chart_bridge.render(
        element, content_by_ref={"l": "Anteil"}, claim_values={"c": "70 %"}
    )

    assert "var(--" in svg
    assert "#" not in svg
