"""Tests for rhetorical chart-data models + parse_chart dispatch."""
from __future__ import annotations

from models_charts import (
    BeforeAfterBars,
    ComparisonColumns,
    Donut,
    parse_chart,
)


def test_before_after_constructs_with_kind() -> None:
    c = BeforeAfterBars(before_value=172549.0, after_value=290100.0, unit="€")
    assert c.kind == "before_after_bars"
    assert c.after_value == 290100.0


def test_parse_before_after_from_dict() -> None:
    c, warn = parse_chart({
        "kind": "before_after_bars", "unit": "€",
        "before_label": "vorher", "before_value": 172549,
        "after_label": "nachher", "after_value": 290100,
    })
    assert warn is None
    assert isinstance(c, BeforeAfterBars)
    assert c.before_value == 172549.0
    assert c.before_label == "vorher"
    assert c.after_label == "nachher"


def test_parse_comparison_columns() -> None:
    c, warn = parse_chart({"kind": "comparison_columns",
                           "ohne": ["langsam", "teuer"], "mit": ["schnell", "guenstig"]})
    assert warn is None
    assert isinstance(c, ComparisonColumns)
    assert c.ohne == ["langsam", "teuer"]
    assert c.mit == ["schnell", "guenstig"]


def test_parse_cost_math_strip() -> None:
    c, warn = parse_chart({"kind": "cost_math_strip",
                           "operands": [100, 48, 220, 43.40], "operators": ["×", "×", "×"],
                           "result": 763840.0, "unit": "€"})
    assert warn is None
    assert c.kind == "cost_math_strip"
    assert c.result == 763840.0


def test_unknown_kind_returns_warning() -> None:
    c, warn = parse_chart({"kind": "pie_3d"})
    assert c is None
    assert warn is not None and "pie_3d" in warn


def test_missing_kind_returns_warning() -> None:
    c, warn = parse_chart({"before_value": 1})
    assert c is None
    assert warn is not None


def test_mistagged_chart_with_extra_fields_rejected() -> None:
    """A mis-tagged chart (donut carrying stray before/after fields) must NOT
    validate silently — charts are validated specs (PRD §5: extra=forbid)."""
    c, warn = parse_chart({"kind": "donut", "before_value": 5, "after_value": 9})
    assert c is None
    assert warn is not None and "donut" in warn


def test_well_formed_donut_still_parses() -> None:
    """extra=forbid must not break a legitimate, well-formed chart."""
    c, warn = parse_chart({"kind": "donut", "title": "Split",
                           "segments": [{"label": "A", "value": 60}, {"label": "B", "value": 40}]})
    assert warn is None
    assert isinstance(c, Donut)
    assert c.segments[0].label == "A"
