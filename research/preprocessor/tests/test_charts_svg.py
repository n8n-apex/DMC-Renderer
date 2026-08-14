"""Tests for stages/charts_svg.py — pure, deterministic, brand-agnostic SVG
renderers for all six chart-spec types + the dispatcher + ChartTheme.

Every test asserts the SVG is WELL-FORMED via xml.etree.ElementTree.fromstring.
Theme colors are passed as params (no client/brand literals).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from models_charts import (
    BeforeAfterBars,
    ComparisonColumns,
    CostMathStrip,
    Donut,
    DonutSegment,
    LineCompare,
    LineSeries,
    MoneyInfographic,
    MoneyItem,
)
from stages.charts_svg import ChartTheme, render_chart_svg

THEME = ChartTheme(
    ink="#1A2540",
    paper="#F5EFE3",
    primary="#1A2540",
    accent="#E97E47",
    muted="#9aa0ad",
)


def _root(svg: str) -> ET.Element:
    root = ET.fromstring(svg)  # raises if not well-formed XML
    assert root.tag.endswith("svg")
    assert root.get("viewBox")
    return root


def _rects(root: ET.Element) -> list[ET.Element]:
    return [e for e in root.iter() if e.tag.endswith("rect")]


def _paths(root: ET.Element) -> list[ET.Element]:
    return [e for e in root.iter() if e.tag.endswith("path")]


def _polylines(root: ET.Element) -> list[ET.Element]:
    return [e for e in root.iter() if e.tag.endswith("polyline")]


# --------------------------------------------------------------------------
# Producer-side contract: every chart SVG carries the selection marker
# --------------------------------------------------------------------------
def test_every_chart_svg_carries_the_chart_marker():
    # The renderer selects chart components by this sentinel (v7-renderer
    # base.py CHART_SVG_MARKER / _select_chart_svgs), not by tail position. So
    # every chart SVG MUST carry it, as an inert XML comment that renders nothing
    # and keeps the SVG well-formed. A _frame refactor that drops it breaks the
    # cross-package contract silently -- this pins it.
    from stages.charts_svg import CHART_SVG_MARKER

    spec = BeforeAfterBars(
        title="Aufwand", unit="h",
        before_label="Vorher", before_value=20,
        after_label="Nachher", after_value=4,
    )
    svg = render_chart_svg(spec, THEME)
    assert f"<!-- {CHART_SVG_MARKER} -->" in svg
    _root(svg)  # still well-formed XML with the comment embedded


# --------------------------------------------------------------------------
# Task 1 — BeforeAfterBars
# --------------------------------------------------------------------------
def test_before_after_bars_svg_wellformed_and_themed():
    spec = BeforeAfterBars(
        title="Aufwand",
        unit="h",
        before_label="Vorher",
        before_value=20,
        after_label="Nachher",
        after_value=4,
    )
    svg = render_chart_svg(spec, THEME)
    root = _root(svg)
    assert "Vorher" in svg and "Nachher" in svg
    assert "20" in svg and "4" in svg
    assert "h" in svg  # unit
    assert THEME.accent in svg  # accent on the after bar
    rects = _rects(root)
    assert len(rects) >= 2


def test_before_after_bars_after_bar_smaller_when_value_smaller():
    spec = BeforeAfterBars(
        before_label="Vorher",
        before_value=20,
        after_label="Nachher",
        after_value=4,
    )
    svg = render_chart_svg(spec, THEME)
    root = _root(svg)
    rects = _rects(root)
    # Identify the two data bars by accent (after) vs ink/primary (before).
    after = [r for r in rects if r.get("fill") == THEME.accent]
    before = [r for r in rects if r.get("fill") in (THEME.ink, THEME.primary)]
    assert after and before
    after_h = max(float(r.get("height", 0)) for r in after)
    before_h = max(float(r.get("height", 0)) for r in before)
    assert after_h < before_h  # 4 < 20 → visibly smaller


def test_before_after_bars_empty_is_graceful():
    spec = BeforeAfterBars(title="Leer")
    svg = render_chart_svg(spec, THEME)
    root = _root(svg)  # must not crash, still well-formed
    assert "Leer" in svg


def test_before_after_bars_zero_values_no_crash():
    spec = BeforeAfterBars(before_value=0, after_value=0)
    svg = render_chart_svg(spec, THEME)
    _root(svg)  # no div-by-zero crash


# --------------------------------------------------------------------------
# Theme colors propagate
# --------------------------------------------------------------------------
def test_theme_colors_appear_in_output():
    spec = BeforeAfterBars(before_value=10, after_value=5)
    svg = render_chart_svg(spec, THEME)
    assert THEME.accent in svg
    assert THEME.primary in svg or THEME.ink in svg


def test_theme_font_family_default():
    t = ChartTheme(ink="#000", paper="#fff", primary="#111", accent="#222", muted="#333")
    assert t.font_family == "inherit"
    spec = BeforeAfterBars(before_value=10, after_value=5)
    svg = render_chart_svg(spec, t)
    assert 'font-family="inherit"' in svg


# --------------------------------------------------------------------------
# Task 2 — ComparisonColumns
# --------------------------------------------------------------------------
def test_comparison_columns_two_columns_all_strings_present():
    spec = ComparisonColumns(
        title="Ohne vs Mit",
        ohne=["Chaos", "Langsam"],
        mit=["Klar", "Schnell", "Skalierbar"],
    )
    svg = render_chart_svg(spec, THEME)
    root = _root(svg)
    for s in ["Chaos", "Langsam", "Klar", "Schnell", "Skalierbar"]:
        assert s in svg
    # Two column panels (rects/group backgrounds).
    rects = _rects(root)
    assert len(rects) >= 2
    # Themed: accent used for the "mit" (positive) column.
    assert THEME.accent in svg
    assert THEME.ink in svg or THEME.muted in svg


def test_comparison_columns_empty_graceful():
    spec = ComparisonColumns(title="Leer", ohne=[], mit=[])
    svg = render_chart_svg(spec, THEME)
    root = _root(svg)
    assert "Leer" in svg


# --------------------------------------------------------------------------
# Task 2 — Donut
# --------------------------------------------------------------------------
def test_donut_two_segments_proportional_arcs():
    spec = Donut(
        title="Anteile",
        segments=[DonutSegment(label="A", value=60), DonutSegment(label="B", value=40)],
    )
    svg = render_chart_svg(spec, THEME)
    root = _root(svg)
    paths = _paths(root)
    assert len(paths) >= 2  # one arc per segment
    assert "A" in svg and "B" in svg  # labels
    assert "60" in svg and "40" in svg  # values
    assert THEME.accent in svg


def test_donut_single_segment_full_ring():
    spec = Donut(title="Voll", segments=[DonutSegment(label="Alles", value=100)])
    svg = render_chart_svg(spec, THEME)
    root = _root(svg)
    # A single 100% segment renders a full ring (circle or a path).
    rings = [
        e
        for e in root.iter()
        if e.tag.endswith("circle") or e.tag.endswith("path")
    ]
    assert rings
    assert "Alles" in svg and "100" in svg


def test_donut_empty_graceful():
    spec = Donut(title="Leer", segments=[])
    svg = render_chart_svg(spec, THEME)
    root = _root(svg)
    assert "Leer" in svg


def test_donut_all_zero_no_crash():
    spec = Donut(
        segments=[DonutSegment(label="A", value=0), DonutSegment(label="B", value=0)]
    )
    svg = render_chart_svg(spec, THEME)
    _root(svg)  # div-by-zero guard


# --------------------------------------------------------------------------
# Task 3 — LineCompare
# --------------------------------------------------------------------------
def test_line_compare_one_line_per_series_with_legend():
    spec = LineCompare(
        title="Verlauf",
        x_labels=["Q1", "Q2", "Q3"],
        series=[
            LineSeries(name="A", points=[1, 2, 3]),
            LineSeries(name="B", points=[3, 2, 1]),
        ],
    )
    svg = render_chart_svg(spec, THEME)
    root = _root(svg)
    lines = _polylines(root) + [p for p in _paths(root)]
    assert len(lines) >= 2  # one polyline/path per series
    for lbl in ["Q1", "Q2", "Q3"]:
        assert lbl in svg  # x labels
    assert "A" in svg and "B" in svg  # legend series names
    assert THEME.primary in svg and THEME.accent in svg  # both colors


def test_line_compare_empty_graceful():
    spec = LineCompare(title="Leer", x_labels=[], series=[])
    svg = render_chart_svg(spec, THEME)
    root = _root(svg)
    assert "Leer" in svg


def test_line_compare_flat_series_no_crash():
    spec = LineCompare(
        x_labels=["A", "B"],
        series=[LineSeries(name="Flat", points=[0, 0])],
    )
    svg = render_chart_svg(spec, THEME)
    _root(svg)  # zero-range guard


# --------------------------------------------------------------------------
# Task 3 — MoneyInfographic
# --------------------------------------------------------------------------
def test_money_infographic_labels_currency_values_proportional():
    spec = MoneyInfographic(
        title="Investition",
        currency="€",
        items=[
            MoneyItem(label="Setup", value=5000),
            MoneyItem(label="Monat", value=900),
        ],
    )
    svg = render_chart_svg(spec, THEME)
    root = _root(svg)
    assert "Setup" in svg and "Monat" in svg
    # Currency-prefixed values.
    assert "€5000" in svg or "€ 5000" in svg
    assert "€900" in svg or "€ 900" in svg
    rects = _rects(root)
    data_bars = [r for r in rects if r.get("fill") in (THEME.primary, THEME.accent, THEME.ink)]
    assert len(data_bars) >= 2
    # Proportional: the 5000 bar wider than the 900 bar.
    widths = sorted(float(r.get("width", 0)) for r in data_bars)
    assert widths[-1] > widths[0]


def test_money_infographic_empty_graceful():
    spec = MoneyInfographic(title="Leer", currency="€", items=[])
    svg = render_chart_svg(spec, THEME)
    root = _root(svg)
    assert "Leer" in svg


def test_money_infographic_all_zero_no_crash():
    spec = MoneyInfographic(
        currency="$", items=[MoneyItem(label="A", value=0), MoneyItem(label="B", value=0)]
    )
    svg = render_chart_svg(spec, THEME)
    _root(svg)


# --------------------------------------------------------------------------
# Task 3 — CostMathStrip (VERBATIM — no arithmetic)
# --------------------------------------------------------------------------
def test_cost_math_strip_renders_verbatim():
    spec = CostMathStrip(
        title="Rechnung",
        operands=[3, 4],
        operators=["×"],
        result=12,
        unit="h",
    )
    svg = render_chart_svg(spec, THEME)
    root = _root(svg)
    for token in ["3", "×", "4", "12", "h"]:
        assert token in svg


def test_cost_math_strip_does_not_recompute():
    # operands 3 × 4 would be 12, but result is given as 99 -> SVG must show 99.
    spec = CostMathStrip(operands=[3, 4], operators=["×"], result=99, unit="h")
    svg = render_chart_svg(spec, THEME)
    _root(svg)
    assert "99" in svg  # renders given result verbatim
    assert "= 12" not in svg  # never computed 3*4


def test_cost_math_strip_empty_graceful():
    spec = CostMathStrip(title="Leer", operands=[], operators=[], result=None)
    svg = render_chart_svg(spec, THEME)
    root = _root(svg)
    assert "Leer" in svg


def test_cost_math_strip_long_result_not_clipped():
    """Regression: a long result like '1040 h/Jahr' must not overflow the
    viewBox (the fixed-72px result tile clipped it). Every tile rect must fit
    within the (now width-adaptive) viewBox."""
    spec = CostMathStrip(operands=[20, 52], operators=["×"], result=1040, unit="h/Jahr")
    svg = render_chart_svg(spec, THEME)
    root = ET.fromstring(svg)
    W = float(root.get("viewBox").split()[2])
    for r in root.iter():
        if r.tag.endswith("rect") and r.get("x") is not None and r.get("width"):
            right = float(r.get("x")) + float(r.get("width"))
            assert right <= W + 0.5, f"tile overflows viewBox ({right} > {W}) — clipped"
    assert "1040 h/Jahr" in svg
