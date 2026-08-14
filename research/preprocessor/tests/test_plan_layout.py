"""Tests for Stage 7 — plan_layout (grammar §1.2, §1.4)."""

from __future__ import annotations

import pytest

from stages.plan_layout import (
    LayoutPlan,
    ST_TO_TEMPLATE,
    layout_plan_to_summary,
    plan_layout,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixture builders
# ─────────────────────────────────────────────────────────────────────────────


def _page(slot: int, st_type: str, data: dict | None = None) -> dict:
    return {"slot": slot, "type": st_type, "data": data or {}}


def _well_formed_20_page_plan() -> list[dict]:
    """A grammar-conforming 20-page report.

    Layout:
      1  ST-01  Cover                          (FIXED)
      2  ST-02  Outlook                        (soft CTA in footer)
      3  ST-05  About
      4  ST-09  Status quo
      5  ST-09  Status quo
      6  ST-14  False beliefs
      7  ST-31  Atemseite                      (breathing relief)
      8  ST-06  Mechanism
      9  ST-22  Collaboration                  (mid CTA)
     10  ST-07A Case study 1
     11  ST-07B Theory pairing for CS1
     12  ST-07A Case study 2
     13  ST-07B Theory pairing for CS2
     14  ST-32  Breathing                       (breathing relief)
     15  ST-07A Case study 3
     16  ST-07B Theory pairing for CS3
     17  ST-08  FAQ
     18  ST-22  Collaboration                   (mid CTA)
     19  ST-FAZIT Summary
     20  ST-03  Hard CTA / QR                   (FIXED)
    """
    return [
        _page(1,  "ST-01"),
        _page(2,  "ST-02", {"cta_url": "https://example.de"}),
        _page(3,  "ST-05"),
        _page(4,  "ST-09"),
        _page(5,  "ST-09"),
        _page(6,  "ST-14"),
        _page(7,  "ST-31"),
        _page(8,  "ST-06"),
        _page(9,  "ST-22"),
        _page(10, "ST-07A"),
        _page(11, "ST-07B"),
        _page(12, "ST-07A"),
        _page(13, "ST-07B"),
        _page(14, "ST-32"),
        _page(15, "ST-07A"),
        _page(16, "ST-07B"),
        _page(17, "ST-08"),
        _page(18, "ST-22"),
        _page(19, "ST-FAZIT"),
        _page(20, "ST-03"),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# The 12 spec test cases
# ─────────────────────────────────────────────────────────────────────────────


def test_1_valid_20_page_plan_no_warnings() -> None:
    """A well-formed 20-page report → no structural warnings."""
    pages = _well_formed_20_page_plan()
    plan = plan_layout(pages, components={}, page_count_target=20)
    assert plan.warnings == [], f"expected no warnings, got: {plan.warnings}"
    assert plan.page_count == 20
    assert plan.page_count_target == 20


def test_2_slot_1_not_st01_warns() -> None:
    """If slot 1 is anything other than ST-01 → warning."""
    pages = _well_formed_20_page_plan()
    pages[0] = _page(1, "ST-02")
    plan = plan_layout(pages, components={}, page_count_target=20)
    assert any("slot 1 should be ST-01" in w for w in plan.warnings), plan.warnings


def test_3_final_slot_not_st03_warns() -> None:
    """If the final slot is anything other than ST-03 → warning."""
    pages = _well_formed_20_page_plan()
    pages[-1] = _page(20, "ST-08")
    plan = plan_layout(pages, components={}, page_count_target=20)
    assert any("final slot should be ST-03" in w for w in plan.warnings), plan.warnings


def test_4_only_two_case_studies_warns() -> None:
    """Fewer than 3 ST-07A → warning from Stage 7 (separate from Stage 1)."""
    pages = _well_formed_20_page_plan()
    # Replace the third case study (slots 15,16) with non-case-study pages
    pages[14] = _page(15, "ST-09")
    pages[15] = _page(16, "ST-09")
    plan = plan_layout(pages, components={}, page_count_target=20)
    assert any("only 2 ST-07A" in w or "only 2 ST-07A case studies" in w
               for w in plan.warnings), plan.warnings


def test_5_no_mid_report_cta_warns() -> None:
    """If no CTA between S3 and the final slot → warning."""
    pages = _well_formed_20_page_plan()
    # Strip CTA-host types from the middle of the report
    for i, p in enumerate(pages):
        if 2 < p["slot"] < 20 and p["type"] in ("ST-22", "ST-08"):
            pages[i] = _page(p["slot"], "ST-09")
    plan = plan_layout(pages, components={}, page_count_target=20)
    assert any("no CTA element found" in w for w in plan.warnings), plan.warnings


def test_6_long_dense_stretch_warns() -> None:
    """A stretch of 9+ consecutive dense pages → warning."""
    # 9 dense pages (ST-09) followed by ST-03
    pages = [_page(1, "ST-01")]
    pages += [_page(i, "ST-09") for i in range(2, 11)]  # 9 dense pages
    pages.append(_page(11, "ST-03"))
    plan = plan_layout(pages, components={}, page_count_target=11)
    assert any("consecutive dense pages" in w for w in plan.warnings), plan.warnings


def test_7_adjacent_breathing_pages_warns() -> None:
    """Two breathing pages back-to-back (S6=ST-32 and S7=ST-32) → warning."""
    pages = _well_formed_20_page_plan()
    # Replace slot-7 with another breathing page to force adjacency
    pages[5] = _page(6, "ST-32")
    pages[6] = _page(7, "ST-32")
    plan = plan_layout(pages, components={}, page_count_target=20)
    assert any("adjacent" in w and "Atemseite" in w
               for w in plan.warnings), plan.warnings


def test_8_page_count_mismatch_warns() -> None:
    """20 pages in array, target is 24 → warning."""
    pages = _well_formed_20_page_plan()
    plan = plan_layout(pages, components={}, page_count_target=24)
    assert any("page count mismatch" in w for w in plan.warnings), plan.warnings


def test_9_unknown_st_type_gets_generic_template_and_warns() -> None:
    """Unknown ST-99 → 'generic' template + warning."""
    pages = _well_formed_20_page_plan()
    pages[3] = _page(4, "ST-99")
    plan = plan_layout(pages, components={}, page_count_target=20)
    odd_page = next(p for p in plan.pages if p.slot == 4)
    assert odd_page.css_template == "generic"
    assert any("ST-99" in w and "generic" in w for w in plan.warnings), plan.warnings


def test_10_every_page_gets_a_css_template_name() -> None:
    """No page is left without a css_template."""
    pages = _well_formed_20_page_plan()
    plan = plan_layout(pages, components={}, page_count_target=20)
    for pp in plan.pages:
        assert pp.css_template, f"slot {pp.slot} has no css_template"
        # Known ST type should NOT get 'generic'
        if pp.st_type in ST_TO_TEMPLATE:
            assert pp.css_template == ST_TO_TEMPLATE[pp.st_type]


def test_11_component_attachment() -> None:
    """If Stage 6 produces SVGs for slot 6 → PlannedPage(slot=6) carries
    them in its components list.
    """
    pages = _well_formed_20_page_plan()
    components = {
        6: ["<svg>SLOT6_A</svg>", "<svg>SLOT6_B</svg>"],
        10: ["<svg>SLOT10</svg>"],
    }
    plan = plan_layout(pages, components=components, page_count_target=20)
    slot_6 = next(p for p in plan.pages if p.slot == 6)
    slot_10 = next(p for p in plan.pages if p.slot == 10)
    slot_3 = next(p for p in plan.pages if p.slot == 3)
    assert slot_6.components == ["<svg>SLOT6_A</svg>", "<svg>SLOT6_B</svg>"]
    assert slot_10.components == ["<svg>SLOT10</svg>"]
    assert slot_3.components == []


def test_12_empty_components_dict_no_crash() -> None:
    """Empty components dict → every page has [] components, no crash."""
    pages = _well_formed_20_page_plan()
    plan = plan_layout(pages, components={}, page_count_target=20)
    for pp in plan.pages:
        assert pp.components == []


# ─────────────────────────────────────────────────────────────────────────────
# Additional coverage
# ─────────────────────────────────────────────────────────────────────────────


def test_cta_positions_lists_all_cta_slots() -> None:
    """cta_positions reflects every page that carries a CTA."""
    pages = _well_formed_20_page_plan()
    plan = plan_layout(pages, components={}, page_count_target=20)
    # Slots 2 (cta_url), 9 (ST-22), 17 (ST-08), 18 (ST-22), 20 (ST-03)
    assert set(plan.cta_positions) >= {2, 9, 17, 18, 20}


def test_breathing_positions_correct() -> None:
    """breathing_positions tracks ST-31 / ST-32 slots."""
    pages = _well_formed_20_page_plan()
    plan = plan_layout(pages, components={}, page_count_target=20)
    assert plan.breathing_positions == [7, 14]


def test_layout_plan_summary_excludes_heavy_fields() -> None:
    """The summary view drops `data` and the SVG strings but keeps the
    routing metadata + component_count.
    """
    pages = _well_formed_20_page_plan()
    components = {6: ["<svg/>"]}
    plan = plan_layout(pages, components=components, page_count_target=20)
    summary = layout_plan_to_summary(plan)
    assert summary["page_count"] == 20
    assert summary["page_count_target"] == 20
    page_6_view = next(p for p in summary["pages"] if p["slot"] == 6)
    assert page_6_view["component_count"] == 1
    # Summary view does NOT carry the SVG strings or data blob
    assert "components" not in page_6_view
    assert "data" not in page_6_view


def test_pydantic_pages_accepted() -> None:
    """plan_layout accepts a list of Pydantic ReportPage objects."""
    from models import ReportPage
    pages_pyd = [
        ReportPage(slot=1, type="ST-01", data={}),
        ReportPage(slot=2, type="ST-22", data={"cta_url": "x"}),
        ReportPage(slot=3, type="ST-03", data={}),
    ]
    plan = plan_layout(pages_pyd, components={}, page_count_target=3)
    assert plan.page_count == 3
    assert 2 in plan.cta_positions


def test_page_numbers_flows_to_planned_page() -> None:
    """page_numbers on the input page is copied onto the PlannedPage."""
    pages = [
        {"slot": 1, "type": "ST-01", "data": {}, "page_numbers": "1"},
        {"slot": 2, "type": "ST-02", "data": {}, "page_numbers": "2-3"},
    ]
    plan = plan_layout(pages, components={}, page_count_target=20)
    by_slot = {p.slot: p for p in plan.pages}
    assert by_slot[1].page_numbers == "1"
    assert by_slot[2].page_numbers == "2-3"


def test_page_numbers_defaults_to_none_when_absent() -> None:
    """A page without page_numbers yields PlannedPage.page_numbers == None."""
    plan = plan_layout(
        [{"slot": 1, "type": "ST-01", "data": {}}],
        components={},
        page_count_target=20,
    )
    assert plan.pages[0].page_numbers is None


# ─────────────────────────────────────────────────────────────────────────────
# Layout-variant policy (ST-07A default "fill" + explicit per-page override)
# ─────────────────────────────────────────────────────────────────────────────


def test_st07a_defaults_to_fill_layout_variant() -> None:
    """An ST-07A page with no explicit hint defaults to layout_variant='fill'."""
    plan = plan_layout(
        [_page(1, "ST-07A")], components={}, page_count_target=20,
    )
    assert plan.pages[0].layout_variant == "fill"


def test_fill_default_extended_to_07b_22_fazit() -> None:
    """ST-07B / ST-22 / ST-FAZIT now DEFAULT to layout_variant='fill' (each
    implements a full-height authority/timeline composition that kills the dead
    bottom band the sparse 'standard' leaves). ST-07A stays fill; ST-09 etc. stay
    None (covered by the non-fill tests below)."""
    for st_type in ("ST-07B", "ST-22", "ST-FAZIT"):
        plan = plan_layout([_page(1, st_type)], components={}, page_count_target=20)
        assert plan.pages[0].layout_variant == "fill", st_type


def test_st07a_explicit_standard_override_respected() -> None:
    """An explicit top-level layout_variant on an ST-07A page wins over the
    'fill' default."""
    page = _page(1, "ST-07A")
    page["layout_variant"] = "standard"
    plan = plan_layout([page], components={}, page_count_target=20)
    assert plan.pages[0].layout_variant == "standard"


def test_explicit_hint_in_data_block_respected() -> None:
    """A layout_variant hint nested in the page `data` block is honoured."""
    page = _page(1, "ST-07A", {"layout_variant": "standard"})
    plan = plan_layout([page], components={}, page_count_target=20)
    assert plan.pages[0].layout_variant == "standard"


def test_non_st07a_gets_no_forced_layout_variant() -> None:
    """A non-ST-07A page with no explicit hint gets layout_variant=None (the
    package must NOT force a variant onto other ST types)."""
    plan = plan_layout([_page(1, "ST-09")], components={}, page_count_target=20)
    assert plan.pages[0].layout_variant is None


def test_non_st07a_explicit_hint_respected() -> None:
    """A non-ST-07A page CAN opt into a variant via an explicit hint."""
    page = _page(1, "ST-09")
    page["layout_variant"] = "fill"
    plan = plan_layout([page], components={}, page_count_target=20)
    assert plan.pages[0].layout_variant == "fill"


def test_unknown_layout_variant_hint_ignored() -> None:
    """A typo'd/unknown hint is ignored; ST-07A falls back to its 'fill'
    default, a non-fill type falls back to None."""
    cs = _page(1, "ST-07A")
    cs["layout_variant"] = "bogus"
    other = _page(2, "ST-09")
    other["layout_variant"] = "bogus"
    plan = plan_layout([cs, other], components={}, page_count_target=20)
    by_slot = {p.slot: p for p in plan.pages}
    assert by_slot[1].layout_variant == "fill"
    assert by_slot[2].layout_variant is None


def test_layout_variant_from_pydantic_page() -> None:
    """A Pydantic ReportPage carrying an explicit top-level layout_variant
    (extra='allow') is honoured."""
    from models import ReportPage

    pages = [
        ReportPage(slot=1, type="ST-07A", data={}, layout_variant="standard"),
        ReportPage(slot=2, type="ST-07A", data={}),
    ]
    plan = plan_layout(pages, components={}, page_count_target=20)
    by_slot = {p.slot: p for p in plan.pages}
    assert by_slot[1].layout_variant == "standard"  # explicit
    assert by_slot[2].layout_variant == "fill"       # default


def test_casestudy_hero_spread_hint_stamps_a3_format() -> None:
    """A casestudy_hero hint is recognised (was previously ignored as
    unknown) and stamps page_format='a3' — the A3-landscape spread sheet —
    on the planned page."""
    cs = _page(1, "ST-07A")
    cs["layout_variant"] = "casestudy_hero"
    plan = plan_layout([cs], components={}, page_count_target=20)
    assert plan.pages[0].layout_variant == "casestudy_hero"
    assert plan.pages[0].page_format == "a3"


def test_non_spread_variants_stay_a4() -> None:
    """'fill' / 'standard' pages never get an a3 sheet stamp — the renderer
    keeps its A4 default."""
    for variant in ("fill", "standard"):
        page = _page(1, "ST-07A")
        page["layout_variant"] = variant
        plan = plan_layout([page], components={}, page_count_target=20)
        assert plan.pages[0].page_format is None, variant
