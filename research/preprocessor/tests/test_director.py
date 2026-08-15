"""Director tests: reference selection, visual job, generator brief.

The Director is the organism's decision layer: the selector's reference choice
plus a deterministic visual job and a no-fabrication generator brief drive the
fal prompt. These tests pin the determinism and the verbatim-subject rule.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stages.director import (  # noqa: E402
    compose_generator_brief,
    compose_rationale,
    compose_visual_job,
)


def _case_data(figures: list[str] | None = None) -> dict:
    return {
        "fallstudie_number": 1,
        "ergebnis_headline": "Von operativem Chaos zu skalierbarer KI-Infrastruktur",
        "kunde": {"name": "Martina Ammon", "funktion": "Gründerin"},
        "ergebnis_metrics": figures
        or [
            {"label": "Support-Reaktionszeit", "value": "24 Std. → Minuten"},
            {"label": "Support-Einsparung / Jahr", "value": "> 200.000 €"},
        ],
        "ausgangsproblem": "Rapides Wachstum…",
    }


def test_visual_job_detects_transformation() -> None:
    """A before/after metric (24 Std. -> Minuten) yields the transformation job —
    the visual must show the change, not just fill space."""
    assert compose_visual_job("ST-07A", _case_data()) == "transformation"


def test_visual_job_detects_completion() -> None:
    data = _case_data([{"label": "Automatisierte Kernprozesse", "value": "6 von 6"}])
    assert compose_visual_job("ST-07A", data) == "completion"


def test_visual_job_detects_scale_from_headline() -> None:
    data = {
        **_case_data([{"label": "Kapazitätslimit", "value": "verschoben"}]),
        "ergebnis_headline": "6 manuelle Prozesse automatisiert, Kapazität verdoppelt",
    }
    assert compose_visual_job("ST-07A", data) == "scale"


def test_generator_brief_subject_is_verbatim_page_data() -> None:
    """The fal prompt's subject comes VERBATIM from the page (kunde name) —
    never an invented subject."""
    brief = compose_generator_brief("ST-07A", _case_data())
    assert "Martina Ammon" in brief["subject"]
    assert "Martina Ammon" in brief["concept"]
    assert "transformation" in brief["visual_job"]


def test_generator_brief_never_fabricates_a_figure() -> None:
    """US-407 binding: the concept is an IMAGE-TO-IMAGE instruction (preserve
    the reference grammar, place the subject) and NEVER names figures — data
    is renderer-native, and naming numbers in the art invites hallucinated
    text/diagrams. The negative forbids numbers/text/faces."""
    brief = compose_generator_brief("ST-07A", _case_data())
    assert "input reference image" in brief["concept"], brief["concept"]
    assert "figures" not in brief["concept"], "data must never appear in the art"
    assert "numbers" in brief["negative"] and "text" in brief["negative"]


def test_generator_brief_uses_reference_style_when_selected() -> None:
    reference = {
        "report": "buchagentur", "page_no": 8, "face_index": 0,
        "format": "a4", "density": "dense",
        "mechanism": "proof dashboard with metrics",
        "devices": "stat_strip,quote",
    }
    brief = compose_generator_brief(
        "ST-07A", _case_data(), reference=reference,
        brand_primary="#1A2540", brand_accent="#E97E47",
    )
    assert "proof dashboard" in brief["style"]
    assert "#1A2540" in brief["style"]
    assert "E97E47" in brief["style"]


def test_rationale_records_why_and_degrades_honestly() -> None:
    reference = {
        "report": "niklas", "page_no": 8, "face_index": 0,
        "format": "a4", "density": "dense", "mechanism": "portrait evidence rail",
    }
    rationale = compose_rationale("ST-07A", reference, "transformation")
    assert "niklas" in rationale and "transformation" in rationale
    alone = compose_rationale("ST-07A", None, "system")
    assert "no matching reference" in alone


def test_breather_job_is_atmosphere() -> None:
    assert compose_visual_job("ST-31", {"phrase": "Innehalten"}) == "atmosphere"


def test_allocate_references_spreads_across_distinct_pages() -> None:
    """Reference diversification: 5 case studies each request k=3 candidates;
    the allocator assigns a DISTINCT reference (different report+page) per
    case study so the deck does not anchor on one Richard page."""
    from stages.director import allocate_references

    candidates_by_key = {
        "slot.07": [
            {"report": "niklas", "page_no": 8, "face_index": 0, "id": 1},
            {"report": "buchagentur", "page_no": 5, "face_index": 0, "id": 2},
            {"report": "boss", "page_no": 5, "face_index": 0, "id": 3},
        ],
        "slot.09": [
            {"report": "niklas", "page_no": 8, "face_index": 0, "id": 1},
            {"report": "buchagentur", "page_no": 6, "face_index": 0, "id": 4},
            {"report": "werkzeugkoffer", "page_no": 6, "face_index": 0, "id": 5},
        ],
        "slot.12": [
            {"report": "niklas", "page_no": 8, "face_index": 0, "id": 1},
            {"report": "boss", "page_no": 6, "face_index": 0, "id": 6},
            {"report": "aerztepartner", "page_no": 5, "face_index": 0, "id": 7},
        ],
        "slot.14": [
            {"report": "niklas", "page_no": 8, "face_index": 0, "id": 1},
            {"report": "boss", "page_no": 5, "face_index": 0, "id": 3},
            {"report": "buchagentur", "page_no": 7, "face_index": 0, "id": 8},
        ],
        "slot.15": [
            {"report": "niklas", "page_no": 8, "face_index": 0, "id": 1},
            {"report": "werkzeugkoffer", "page_no": 7, "face_index": 0, "id": 9},
            {"report": "boss", "page_no": 7, "face_index": 0, "id": 10},
        ],
    }
    allocation = allocate_references(candidates_by_key)
    assert set(allocation.keys()) == set(candidates_by_key.keys())
    chosen = [allocation[k] for k in sorted(allocation)]
    # every case study gets a reference
    assert all(c is not None for c in chosen)
    # distinct (report, page_no) — no two case studies share the same page
    anchors = {(c["report"], c["page_no"]) for c in chosen}
    assert len(anchors) == len(chosen), f"duplicate anchors: {anchors}"


def test_allocate_references_degrades_when_pool_too_small() -> None:
    """If candidates are too few to fully diversify, remaining pages take the
    best available (never None when candidates exist)."""
    from stages.director import allocate_references

    candidates_by_key = {
        "slot.07": [{"report": "niklas", "page_no": 8, "face_index": 0, "id": 1}],
        "slot.09": [{"report": "niklas", "page_no": 8, "face_index": 0, "id": 1}],
        "slot.12": [{"report": "niklas", "page_no": 8, "face_index": 0, "id": 1}],
    }
    allocation = allocate_references(candidates_by_key)
    assert all(allocation[k] is not None for k in candidates_by_key)
    # worst case: all three share the one available page (no None, honest)
    assert {allocation[k]["id"] for k in candidates_by_key} == {1}
