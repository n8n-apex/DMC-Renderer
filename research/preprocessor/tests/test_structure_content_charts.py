"""Task 4 — conservative prose→chart extraction in structure_content.

Each extractor is gated on an EXPLICIT signal (a field name / token); the
cardinal NO-FABRICATION rule (spec §3) is exercised by the guard tests:
two unrelated numbers must NEVER become a chart, a plain number list must
not become a Donut, and a CostMathStrip renders the GIVEN result verbatim
(never recomputed). Numbers parse via parse_german_number — never computed.
"""
from __future__ import annotations

from types import SimpleNamespace

from models_charts import (
    ComparisonColumns,
    CostMathStrip,
    Donut,
    LineCompare,
    MoneyInfographic,
)
from stages.structure_content import structure_content


def _page(slot, type_, data):
    return SimpleNamespace(slot=slot, type=type_, data=data)


def _charts(data, slot=6, type_="ST-06"):
    return structure_content([_page(slot, type_, data)]).pages[0].charts


# ─────────────────────────────────────────────────────────────────────────
# NO-FABRICATION GUARDS (spec §3 — load-bearing)
# ─────────────────────────────────────────────────────────────────────────


def test_guard_two_unrelated_numbers_no_chart() -> None:
    """(a) Two unrelated numbers ("50 Kunden", "10 Jahre") → NO chart."""
    assert _charts({
        "stats": [
            {"label": "Kunden", "value": "50"},
            {"label": "Jahre", "value": "10"},
        ],
    }, slot=5, type_="ST-05") == []


def test_guard_plain_number_list_no_donut() -> None:
    """(b) A plain list of unrelated numbers is NOT a parts-of-whole → no Donut."""
    charts = _charts({"numbers": [10, 20, 30]})
    assert charts == []
    assert not any(isinstance(c, Donut) for c in charts)


# ─────────────────────────────────────────────────────────────────────────
# ComparisonColumns ← explicit ohne/mit (without/with)
# ─────────────────────────────────────────────────────────────────────────


def test_comparison_columns_from_ohne_mit() -> None:
    """(c) Explicit ohne/mit string lists → ComparisonColumns."""
    charts = _charts({
        "ohne": ["Excel-Chaos", "manuelle Pflege"],
        "mit": ["Live-Dashboard", "ein Klick", "Single Source"],
    })
    assert len(charts) == 1
    c = charts[0]
    assert isinstance(c, ComparisonColumns)
    assert c.ohne == ["Excel-Chaos", "manuelle Pflege"]
    assert c.mit == ["Live-Dashboard", "ein Klick", "Single Source"]


def test_comparison_columns_from_without_with_aliases() -> None:
    """English aliases without/with also work."""
    charts = _charts({"without": ["A"], "with": ["B"]})
    assert len(charts) == 1
    assert isinstance(charts[0], ComparisonColumns)
    assert charts[0].ohne == ["A"]
    assert charts[0].mit == ["B"]


def test_no_comparison_columns_without_keys() -> None:
    """No ohne/mit keys → no ComparisonColumns."""
    assert not any(
        isinstance(c, ComparisonColumns) for c in _charts({"title": "x"})
    )


# ─────────────────────────────────────────────────────────────────────────
# Donut ← explicit parts-of-whole breakdown/segments/anteile
# ─────────────────────────────────────────────────────────────────────────


def test_donut_from_explicit_breakdown() -> None:
    """(d) Explicit breakdown list of {label,value} → Donut, values parsed."""
    charts = _charts({
        "breakdown": [
            {"label": "Recherche", "value": "60"},
            {"label": "Schreiben", "value": "40"},
        ],
    })
    assert len(charts) == 1
    d = charts[0]
    assert isinstance(d, Donut)
    assert [s.label for s in d.segments] == ["Recherche", "Schreiben"]
    assert [s.value for s in d.segments] == [60.0, 40.0]


def test_donut_from_anteile_german_numbers() -> None:
    """anteile alias + German-formatted values parse correctly."""
    charts = _charts({
        "anteile": [
            {"label": "Setup", "value": "1.250"},
            {"label": "Betrieb", "value": "750"},
        ],
    })
    assert len(charts) == 1
    d = charts[0]
    assert isinstance(d, Donut)
    assert [s.value for s in d.segments] == [1250.0, 750.0]


# ─────────────────────────────────────────────────────────────────────────
# CostMathStrip ← explicit operands+operators(+result), VERBATIM result
# ─────────────────────────────────────────────────────────────────────────


def test_cost_math_strip_verbatim_result() -> None:
    """(e) Explicit math struct with result=99 → CostMathStrip carrying the
    GIVEN result (99) verbatim — NOT recomputed (3*4=12 != 99)."""
    charts = _charts({
        "rechnung": {
            "operands": ["3", "4"],
            "operators": ["×"],
            "result": "99",
            "unit": "h",
        },
    })
    assert len(charts) == 1
    m = charts[0]
    assert isinstance(m, CostMathStrip)
    assert m.operands == [3.0, 4.0]
    assert m.operators == ["×"]
    assert m.result == 99.0  # verbatim, never recomputed
    assert m.unit == "h"


def test_no_cost_math_strip_without_operands() -> None:
    """A bare result with no operands → no CostMathStrip (ambiguous)."""
    assert not any(
        isinstance(c, CostMathStrip) for c in _charts({"math": {"result": "5"}})
    )


# ─────────────────────────────────────────────────────────────────────────
# MoneyInfographic ← explicit currency items
# ─────────────────────────────────────────────────────────────────────────


def test_money_infographic_from_kosten_items() -> None:
    """(f) Currency items under `kosten` → MoneyInfographic."""
    charts = _charts({
        "kosten": [
            {"label": "Setup", "value": "5.000 €"},
            {"label": "Monat", "value": "900 €"},
        ],
    })
    assert len(charts) == 1
    mi = charts[0]
    assert isinstance(mi, MoneyInfographic)
    assert [it.label for it in mi.items] == ["Setup", "Monat"]
    assert [it.value for it in mi.items] == [5000.0, 900.0]


def test_money_infographic_picks_up_currency_symbol() -> None:
    """The currency symbol present in the values is carried on the spec."""
    charts = _charts({
        "investment": [
            {"label": "Lizenz", "value": "1.200 €"},
        ],
    })
    assert len(charts) == 1
    assert isinstance(charts[0], MoneyInfographic)
    assert charts[0].currency == "€"


def test_no_money_without_currency_signal() -> None:
    """Items with NO currency signal → no MoneyInfographic."""
    assert not any(
        isinstance(c, MoneyInfographic)
        for c in _charts({"items": [{"label": "A", "value": "10"}]})
    )


# ─────────────────────────────────────────────────────────────────────────
# LineCompare ← explicit multi-point series
# ─────────────────────────────────────────────────────────────────────────


def test_line_compare_from_explicit_series() -> None:
    """(g) Explicit series struct (x_labels + named point lists) → LineCompare."""
    charts = _charts({
        "series": {
            "x_labels": ["Q1", "Q2", "Q3"],
            "series": [
                {"name": "Vorher", "points": ["1", "2", "3"]},
                {"name": "Nachher", "points": ["3", "2", "1"]},
            ],
        },
    })
    assert len(charts) == 1
    lc = charts[0]
    assert isinstance(lc, LineCompare)
    assert lc.x_labels == ["Q1", "Q2", "Q3"]
    assert [s.name for s in lc.series] == ["Vorher", "Nachher"]
    assert lc.series[0].points == [1.0, 2.0, 3.0]


def test_line_compare_verlauf_alias() -> None:
    """`verlauf` alias works."""
    charts = _charts({
        "verlauf": {
            "x_labels": ["A", "B"],
            "series": [{"name": "S", "points": ["10", "20"]}],
        },
    })
    assert len(charts) == 1
    assert isinstance(charts[0], LineCompare)


def test_no_line_compare_without_series_struct() -> None:
    """No series struct → no LineCompare."""
    assert not any(
        isinstance(c, LineCompare) for c in _charts({"x_labels": ["A", "B"]})
    )
