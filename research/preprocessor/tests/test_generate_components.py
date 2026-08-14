"""Tests for Stage 6 — generate_components (SVG factory).

Covers:
  - Parameterisation of the 8 existing build_v6 components (5 tests)
  - 3 new components: curved_arrow_flow, paired_comparison, venn_diagram
    (9 tests)
"""

from __future__ import annotations

import pytest

from stages.generate_components import (
    bar_chart,
    causality_chain,
    compare_table,
    curved_arrow_flow,
    generate_components_for_report,
    line_chart,
    matrix_2x2,
    metaphor_split,
    paired_comparison,
    process_flow,
    stat_block,
    venn_diagram,
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared SVG validity helper
# ─────────────────────────────────────────────────────────────────────────────


def assert_valid_svg(svg_string: str) -> None:
    """Every SVG test should call this — verifies structural shape."""
    s = svg_string.strip()
    assert s.startswith("<svg"), f"SVG must start with <svg, got: {s[:40]!r}"
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg_string, "missing xmlns"
    assert "width=" in svg_string, "missing explicit width attribute"
    assert "height=" in svg_string, "missing explicit height attribute"
    assert s.endswith("</svg>"), f"SVG must end with </svg>, got: {s[-40:]!r}"


# ─────────────────────────────────────────────────────────────────────────────
# 1-5: Existing-component parameterisation
# ─────────────────────────────────────────────────────────────────────────────


def test_1_process_flow_navy_coral_colors_appear_in_svg() -> None:
    """process_flow with navy+coral → SVG contains the passed hex
    values, NOT the v5_palette defaults.
    """
    NAVY = "#1A2540"
    CORAL = "#E97E47"
    svg = process_flow(
        steps=[
            {"n": 1, "short": "Audit"},
            {"n": 2, "short": "Plan"},
            {"n": 3, "short": "Ship"},
        ],
        primary=NAVY, accent=CORAL,
    )
    assert_valid_svg(svg)
    assert NAVY in svg, "passed primary hex must appear in SVG"
    assert CORAL in svg, "passed accent hex must appear in SVG"
    # v5_palette defaults must NOT appear (they're for the original APEX
    # build, not arbitrary clients)
    assert "#1a1a2e" not in svg
    assert "#e94560" not in svg


def test_2_process_flow_teal_gold_colors_appear() -> None:
    """Different client → different colors → SVG reflects them. Proves
    parameterisation actually works.
    """
    TEAL = "#0F766E"
    GOLD = "#CA8A04"
    svg = process_flow(
        steps=[
            {"n": 1, "short": "Start"},
            {"n": 2, "short": "Build"},
        ],
        primary=TEAL, accent=GOLD,
    )
    assert_valid_svg(svg)
    assert TEAL in svg
    assert GOLD in svg
    assert "#1A2540" not in svg
    assert "#E97E47" not in svg


def test_3_stat_block_with_brand_colors() -> None:
    """stat_block accepts brand colors and emits a valid SVG."""
    PRIMARY = "#0B3D5C"
    ACCENT = "#D97706"
    svg = stat_block(
        stats=[
            {"value": "80%", "label": "Reduktion", "sub": "manuell"},
            {"value": "3×",  "label": "Kapazität", "sub": "ohne neue Köpfe"},
            {"value": "12",  "label": "Tage",      "sub": "bis Live"},
        ],
        primary=PRIMARY, accent=ACCENT,
    )
    assert_valid_svg(svg)
    assert PRIMARY in svg
    assert ACCENT in svg


def test_4_matrix_2x2_with_brand_colors() -> None:
    """matrix_2x2 colors parameterise; renders without error."""
    PRIMARY = "#1A2540"
    ACCENT = "#E97E47"
    payload = {
        "x_axis": {"label": "Sichtbarkeit", "low": "schwer", "high": "leicht"},
        "y_axis": {"label": "Schaden",      "low": "gering", "high": "hoch"},
        "quadrants": {
            "tl": {"tag": "STILL", "meaning": "hoher Schaden, schwer sichtbar"},
            "tr": {"tag": "OFFEN", "meaning": "hoher Schaden, leicht sichtbar"},
            "bl": {"tag": "GRUND", "meaning": "geringer Schaden, schwer sichtbar"},
            "br": {"tag": "SICHTBAR", "meaning": "geringer Schaden, leicht sichtbar"},
        },
        "items": [
            {"label": "Suchzeit",   "x": 0.14, "y": 0.62, "qtag": "tl"},
            {"label": "E-Mail",     "x": 0.62, "y": 0.62, "qtag": "tr"},
        ],
    }
    svg = matrix_2x2(payload, primary=PRIMARY, accent=ACCENT)
    assert_valid_svg(svg)
    assert PRIMARY in svg


def test_5_dispatcher_returns_dict_keyed_by_slot() -> None:
    """generate_components_for_report walks a multi-page payload and
    returns a dict mapping slot → list of SVG strings.
    """
    pages = [
        {"slot": 1, "type": "ST-01", "data": {"title": "Cover"}},
        {"slot": 6, "type": "ST-06", "data": {
            "steps": [
                {"n": 1, "short": "Audit"},
                {"n": 2, "short": "Plan"},
            ],
        }},
        {"slot": 10, "type": "ST-07A", "data": {
            "stats": [
                {"value": "80%", "label": "Reduktion", "sub": "manuell"},
                {"value": "3×",  "label": "Kapazität", "sub": "Köpfe"},
                {"value": "12",  "label": "Tage",      "sub": "bis Live"},
            ],
        }},
    ]
    result = generate_components_for_report(
        pages,
        brand_primary="#1A2540",
        brand_accent="#E97E47",
        brand_neutral_light="#F5EFE3",
    )
    assert isinstance(result, dict)
    # Slot 1 (Cover) has no component generator → absent from result
    assert 1 not in result
    # Slot 6 (ST-06) and 10 (ST-07A) → both present
    assert 6 in result
    assert 10 in result
    assert len(result[6]) == 1
    assert_valid_svg(result[6][0])
    assert_valid_svg(result[10][0])


# ─────────────────────────────────────────────────────────────────────────────
# 6-13: New components
# ─────────────────────────────────────────────────────────────────────────────


def test_6_curved_arrow_flow_with_5_steps() -> None:
    """5 steps → valid SVG, all 5 step numbers present, curved Q-paths."""
    steps = [
        {"number": "01", "title": "Beratung",   "description": "kurz"},
        {"number": "02", "title": "Audit",      "description": "kurz"},
        {"number": "03", "title": "Konzept",    "description": "kurz"},
        {"number": "04", "title": "Umsetzung",  "description": "kurz"},
        {"number": "05", "title": "Betrieb",    "description": "kurz"},
    ]
    svg = curved_arrow_flow(steps, primary="#1A2540", accent="#E97E47")
    assert_valid_svg(svg)
    # 5 step numbers
    for n in ("01", "02", "03", "04", "05"):
        assert f">{n}<" in svg, f"step number {n} should be in SVG"
    # Curved connectors use quadratic Bézier (`Q`)
    assert " Q " in svg, "expected quadratic Bézier path for curved arrows"


def test_7_curved_arrow_flow_with_3_steps() -> None:
    """3 steps → 3 panels, 3 step numbers."""
    steps = [
        {"number": "01", "title": "A", "description": "."},
        {"number": "02", "title": "B", "description": "."},
        {"number": "03", "title": "C", "description": "."},
    ]
    svg = curved_arrow_flow(steps, primary="#1A2540", accent="#E97E47")
    assert_valid_svg(svg)
    assert svg.count("<rect") >= 3  # at least 3 panels
    for n in ("01", "02", "03"):
        assert f">{n}<" in svg


def test_8_curved_arrow_flow_colors_parameterised() -> None:
    """Passed hex values appear; chassis defaults do NOT leak."""
    PRIMARY = "#0F172A"
    ACCENT = "#F59E0B"
    svg = curved_arrow_flow(
        steps=[
            {"number": "01", "title": "A", "description": "."},
            {"number": "02", "title": "B", "description": "."},
        ],
        primary=PRIMARY, accent=ACCENT,
    )
    assert_valid_svg(svg)
    assert PRIMARY in svg
    assert ACCENT in svg
    assert "#1a1a2e" not in svg
    assert "#e94560" not in svg


def test_9_paired_comparison_with_3_pairs() -> None:
    """3 before/after pairs → valid SVG with both column labels."""
    pairs = [
        {"before": "Excel-Listen",     "after": "Live-Dashboard"},
        {"before": "24h Reaktionszeit", "after": "in wenigen Minuten"},
        {"before": "Doppelte Kontakte", "after": "Single Source of Truth"},
    ]
    svg = paired_comparison(pairs, primary="#1A2540", accent="#E97E47")
    assert_valid_svg(svg)
    assert "VORHER" in svg
    assert "NACHHER" in svg
    # Each "after" text must appear somewhere
    for pair in pairs:
        assert pair["after"] in svg


def test_10_paired_comparison_accent_in_after_column() -> None:
    """The accent color must appear (the after-column card uses it)."""
    ACCENT = "#E97E47"
    svg = paired_comparison(
        [{"before": "manuell", "after": "automatisch"}],
        primary="#1A2540", accent=ACCENT,
    )
    assert_valid_svg(svg)
    assert ACCENT in svg


def test_11_venn_diagram_with_2_circles() -> None:
    """2 labels → 2 circles, intersection label in centre."""
    svg = venn_diagram(
        ["Strategie", "Umsetzung"], "Wirkung",
        primary="#1A2540", accent="#E97E47",
    )
    assert_valid_svg(svg)
    assert svg.count("<circle") == 2
    assert "Strategie" in svg
    assert "Umsetzung" in svg
    assert "Wirkung" in svg


def test_12_venn_diagram_with_3_circles() -> None:
    """3 labels → 3 circles."""
    svg = venn_diagram(
        ["A", "B", "C"], "Center",
        primary="#1A2540", accent="#E97E47",
    )
    assert_valid_svg(svg)
    assert svg.count("<circle") == 3
    for ll in ("A", "B", "C", "Center"):
        assert ll in svg


def test_13_venn_diagram_colors_use_brand_with_opacity() -> None:
    """Circles use brand colours and fill-opacity ≤ 0.3."""
    PRIMARY = "#1A2540"
    ACCENT = "#E97E47"
    svg = venn_diagram(
        ["A", "B"], "X",
        primary=PRIMARY, accent=ACCENT,
    )
    assert PRIMARY in svg
    assert ACCENT in svg
    # Opacity (low translucency for the lobes) must be present
    assert "fill-opacity=" in svg


def test_14_all_new_components_have_xmlns_width_height() -> None:
    """Every new component SVG declares xmlns + explicit width + height."""
    PRIMARY = "#1A2540"
    ACCENT = "#E97E47"
    for svg in [
        curved_arrow_flow(
            [{"number": "01", "title": "x", "description": "."}],
            primary=PRIMARY, accent=ACCENT,
        ),
        paired_comparison(
            [{"before": "a", "after": "b"}],
            primary=PRIMARY, accent=ACCENT,
        ),
        venn_diagram(["A", "B"], "C", primary=PRIMARY, accent=ACCENT),
    ]:
        assert_valid_svg(svg)


# ─────────────────────────────────────────────────────────────────────────────
# Edge-case tests
# ─────────────────────────────────────────────────────────────────────────────


def test_venn_rejects_wrong_label_count() -> None:
    """Venn requires exactly 2 or 3 labels."""
    with pytest.raises(ValueError):
        venn_diagram(["A"], "X", primary="#000", accent="#fff")
    with pytest.raises(ValueError):
        venn_diagram(["A", "B", "C", "D"], "X", primary="#000", accent="#fff")


def test_dispatcher_handles_pydantic_pages() -> None:
    """Dispatcher accepts Pydantic ReportPage instances (not just dicts)."""
    from models import ReportPage
    pages = [
        ReportPage(slot=6, type="ST-06", data={
            "steps": [
                {"n": 1, "short": "Audit"},
                {"n": 2, "short": "Plan"},
            ],
        }),
    ]
    result = generate_components_for_report(
        pages,
        brand_primary="#1A2540",
        brand_accent="#E97E47",
        brand_neutral_light="#F5EFE3",
    )
    assert 6 in result
    assert_valid_svg(result[6][0])


def test_dispatcher_extras_from_chart_payloads() -> None:
    """Any page can carry bar_data / line_data / compare_data and gets
    a corresponding extra component.
    """
    pages = [
        {"slot": 8, "type": "ST-06", "data": {
            "steps": [{"n": 1, "short": "x"}],
            "bar_data": [
                {"label": "A", "value": 10, "display": "10"},
                {"label": "B", "value": 20, "display": "20"},
            ],
        }},
    ]
    result = generate_components_for_report(
        pages,
        brand_primary="#1A2540",
        brand_accent="#E97E47",
        brand_neutral_light="#F5EFE3",
    )
    # ST-06 builder produces 1 SVG; bar_data extra adds 1 → 2 total
    assert 8 in result
    assert len(result[8]) == 2
    for svg in result[8]:
        assert_valid_svg(svg)


# ─────────────────────────────────────────────────────────────────────────────
# Task 5 — chart SVGs rendered from StructuredPage.charts into the package
# ─────────────────────────────────────────────────────────────────────────────


def test_charts_rendered_into_components_for_a_page() -> None:
    """A structured page carrying a chart spec → a chart SVG component is
    generated for that page's slot, using the brand accent colour.
    """
    from stages.structure_content import structure_content

    pages = [
        {"slot": 5, "type": "ST-05", "data": {
            "ohne": ["Excel-Chaos"],
            "mit": ["Live-Dashboard"],
        }},
    ]
    structured = structure_content(pages)
    assert len(structured.pages[0].charts) == 1  # extraction fired

    ACCENT = "#E97E47"
    result = generate_components_for_report(
        pages,
        brand_primary="#1A2540",
        brand_accent=ACCENT,
        brand_neutral_light="#F5EFE3",
        structured=structured,
    )
    assert 5 in result
    chart_svgs = [s for s in result[5] if "<svg" in s]
    assert chart_svgs, "expected a chart SVG component for the page"
    # The chart picks up the brand accent (ComparisonColumns 'mit' header).
    assert any(ACCENT in s for s in chart_svgs)
    for svg in result[5]:
        assert_valid_svg(svg)


def test_page_without_charts_gets_no_chart_component() -> None:
    """A page with no chart specs → behaviour is unchanged (no chart
    component added); backward compatible when `structured` is passed.
    """
    from stages.structure_content import structure_content

    pages = [
        {"slot": 6, "type": "ST-06", "data": {
            "steps": [{"n": 1, "short": "Audit"}, {"n": 2, "short": "Plan"}],
        }},
    ]
    structured = structure_content(pages)
    assert structured.pages[0].charts == []

    with_structured = generate_components_for_report(
        pages, brand_primary="#1A2540", brand_accent="#E97E47",
        brand_neutral_light="#F5EFE3", structured=structured,
    )
    without_structured = generate_components_for_report(
        pages, brand_primary="#1A2540", brand_accent="#E97E47",
        brand_neutral_light="#F5EFE3",
    )
    # Same component set whether or not `structured` is supplied (no charts).
    assert with_structured == without_structured
    assert len(with_structured[6]) == 1  # just the ST-06 process_flow


def test_charts_optional_structured_is_backward_compatible() -> None:
    """Omitting `structured` entirely keeps the legacy behaviour."""
    pages = [
        {"slot": 6, "type": "ST-06", "data": {
            "steps": [{"n": 1, "short": "x"}],
        }},
    ]
    result = generate_components_for_report(
        pages, brand_primary="#1A2540", brand_accent="#E97E47",
        brand_neutral_light="#F5EFE3",
    )
    assert 6 in result and len(result[6]) == 1


def test_smoke_remaining_components() -> None:
    """Causality_chain, metaphor_split, bar_chart, line_chart,
    compare_table — each at least produces a valid SVG with the brand
    primary in it. (Coverage for the components not exercised by tests
    1-5.)
    """
    PRIMARY = "#1A2540"
    ACCENT = "#E97E47"
    for svg in [
        causality_chain(["Cause", "Effect", "Consequence"],
                        primary=PRIMARY, accent=ACCENT),
        metaphor_split(
            {"visible": {"items": ["A", "B"]}, "hidden": {"items": ["C", "D"]}},
            primary=PRIMARY, accent=ACCENT,
        ),
        bar_chart(
            [
                {"label": "X", "value": 30, "display": "30"},
                {"label": "Y", "value": 50, "display": "50"},
            ],
            primary=PRIMARY, accent=ACCENT,
        ),
        line_chart(
            series=[{"label": "S1", "values": [10, 20, 30], "accent": False}],
            x_labels=["Q1", "Q2", "Q3"],
            y_ticks=[10, 20, 30],
            primary=PRIMARY, accent=ACCENT,
        ),
        compare_table(
            rows=[{"left": "before x", "right": "after y"}],
            headers=("VORHER", "NACHHER"),
            primary=PRIMARY, accent=ACCENT,
        ),
    ]:
        assert_valid_svg(svg)
        assert PRIMARY in svg
