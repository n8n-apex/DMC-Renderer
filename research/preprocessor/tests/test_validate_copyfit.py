"""Tests for Stage 3.5 — validate_copyfit (heuristic copy-fit pre-check)."""

from __future__ import annotations

from models import CopyWarning, ReportPage
from stages.validate_copyfit import ST_COPY_BUDGET_CHARS, validate_copyfit


def _page(slot: int, ptype: str, data: dict) -> dict:
    return {"slot": slot, "type": ptype, "data": data}


def test_under_budget_no_warning() -> None:
    pages = [_page(8, "ST-08", {"body": "Short FAQ answer."})]
    assert validate_copyfit(pages) == []


def test_over_budget_flags_overflow_risk() -> None:
    # ST-31 (Atemseite) budget is tiny (350); blow well past it.
    pages = [_page(7, "ST-31", {"body": "x" * 900})]
    warnings = validate_copyfit(pages)
    assert len(warnings) == 1
    w = warnings[0]
    assert isinstance(w, CopyWarning)
    assert w.rule == "copy_overflow_risk"
    assert w.page_slot == 7
    assert w.page_type == "ST-31"
    assert "900" in w.detail and "350" in w.detail


def test_total_is_summed_across_nested_fields() -> None:
    # ST-03 budget is 400; spread the text across nested structures.
    data = {"headline": "y" * 200, "block": {"a": "y" * 150, "b": ["y" * 120]}}
    pages = [_page(20, "ST-03", data)]  # total 470 > 400
    warnings = validate_copyfit(pages)
    assert len(warnings) == 1
    assert warnings[0].page_type == "ST-03"


def test_unknown_st_type_skipped() -> None:
    pages = [_page(9, "ST-99", {"body": "z" * 99999})]
    assert validate_copyfit(pages) == []


def test_empty_or_missing_data_no_crash() -> None:
    pages = [
        _page(1, "ST-01", {}),
        {"slot": 2, "type": "ST-02"},          # missing data key
        _page(3, "ST-09", {"body": "   "}),
    ]
    assert validate_copyfit(pages) == []


def test_pydantic_pages_accepted() -> None:
    pages = [ReportPage(slot=8, type="ST-08", data={"body": "w" * 2500})]
    warnings = validate_copyfit(pages)
    assert any(w.rule == "copy_overflow_risk" for w in warnings)


def test_budget_table_covers_known_st_types() -> None:
    # Sanity: the budget table is non-empty and uses int char counts.
    assert ST_COPY_BUDGET_CHARS["ST-07A"] > 0
    assert all(isinstance(v, int) for v in ST_COPY_BUDGET_CHARS.values())
