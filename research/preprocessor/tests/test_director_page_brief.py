"""US-606 — the REAL Director page brief.

The Director currently emits only a generation-side prompt fragment. The
binding contract (2026-08-15-director-fault-audit.md §3) requires ONE page
brief per page with: client_slug, report_id, page_key, section_id, st_type,
selected_reference (face_id/report/page_no/raster/sha256/anatomy), rationale,
visual_job, must_show, must_not_imply, page_arc, region_plan,
renderer_devices. The brief must be PERSISTED IN THE PACKAGE (not only
best-effort Supabase) so the renderer and QA can consume it.

No fabrication: must_show comes verbatim from the page's data; region_plan and
renderer_devices are deterministic from the section's st_type + role.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research" / "preprocessor"))

from stages.director import (  # noqa: E402
    compose_page_brief,
    compose_visual_job,
    must_show_figures,
)


def _case_data() -> dict:
    return {
        "fallstudie_number": 1,
        "kunde": {"name": "Martina Ammon", "funktion": "Gründerin"},
        "ergebnis_headline": "Von operativem Chaos zu skalierbarer KI-Infrastruktur",
        "ergebnis_metrics": [
            {"value": "24 Std. → Minuten", "label": "Support-Reaktionszeit"},
            {"value": "> 200.000 €", "label": "Support-Einsparung / Jahr"},
            {"value": "4", "label": "Automatisierte Kernprozesse"},
        ],
        "pullquote": {"text": "APEX hat unsere Antwortzeiten reduziert.",
                      "attribution": "Martina Ammon"},
    }


def _reference() -> dict:
    return {
        "face_id": 11,
        "report": "buchagentur",
        "page_no": 5,
        "raster_uri": "file:///refs/pages/buchagentur/p5.png",
        "sha256": "abc123",
        "mechanism": "case-study proof spread",
        "devices": "stat_stack, dark_full_height_panel, quote",
        "density": "dense",
        "format": "a3",
    }


# --------------------------------------------------------------------------- #
# 1. the brief carries ALL required fields
# --------------------------------------------------------------------------- #
def test_page_brief_has_all_required_fields() -> None:
    brief = compose_page_brief(
        st_type="ST-07A", data=_case_data(),
        client_slug="apex", report_id="APEX-R1",
        page_key="slot.14", section_id="section.14",
        reference=_reference(),
    )
    for field in ("client_slug", "report_id", "page_key", "section_id",
                  "st_type", "selected_reference", "rationale", "visual_job",
                  "must_show", "must_not_imply", "page_arc", "region_plan",
                  "renderer_devices"):
        assert field in brief, f"missing brief field: {field}"
    assert brief["client_slug"] == "apex"
    assert brief["st_type"] == "ST-07A"
    assert brief["selected_reference"]["face_id"] == 11
    assert brief["selected_reference"]["report"] == "buchagentur"
    assert brief["rationale"], "rationale must be non-empty"


# --------------------------------------------------------------------------- #
# 2. must_show is VERBATIM page data (no fabrication)
# --------------------------------------------------------------------------- #
def test_must_show_figures_are_verbatim() -> None:
    data = _case_data()
    figs = must_show_figures("ST-07A", data)
    assert "24 Std. → Minuten" in figs
    assert "> 200.000 €" in figs
    # every figure appears in the source data
    raw = json.dumps(data, ensure_ascii=False)
    for f in figs:
        assert f in raw, f"must_show figure {f!r} not in the page data"


# --------------------------------------------------------------------------- #
# 3. page_arc + region_plan are deterministic per st_type/role
# --------------------------------------------------------------------------- #
def test_page_arc_and_regions_deterministic() -> None:
    brief = compose_page_brief(
        st_type="ST-07A", data=_case_data(),
        client_slug="apex", report_id="R", page_key="slot.14",
        section_id="section.14", reference=None,
    )
    assert isinstance(brief["page_arc"], list) and brief["page_arc"], "page_arc"
    assert isinstance(brief["region_plan"], list) and brief["region_plan"]
    for region in brief["region_plan"]:
        for k in ("region", "role", "bounds"):
            assert k in region, f"region missing {k}: {region}"
        assert len(region["bounds"]) == 4


# --------------------------------------------------------------------------- #
# 4. ST-06 continuation roles get role-specific regions
# --------------------------------------------------------------------------- #
def test_st06_result_continuation_region() -> None:
    brief = compose_page_brief(
        st_type="ST-06", data={"steps": [], "ergebnis": "30-50%"},
        client_slug="apex", report_id="R", page_key="section.16.page.2",
        section_id="section.16", continuation_role="result",
        reference=None,
    )
    roles = [r["role"] for r in brief["region_plan"]]
    assert "result" in roles or "proof" in roles, roles
    assert brief["page_arc"][-1]["role"] == "result"


# --------------------------------------------------------------------------- #
# 5. the brief serialises INTO the package page (persistence)
# --------------------------------------------------------------------------- #
def test_page_brief_writes_into_package_page() -> None:
    from stages.assemble_package import _write_director_brief

    page_dict: dict = {"slot": 14, "st_type": "ST-07A"}
    brief = compose_page_brief(
        st_type="ST-07A", data=_case_data(),
        client_slug="apex", report_id="R", page_key="slot.14",
        section_id="section.14", reference=_reference(),
    )
    _write_director_brief(page_dict, brief)
    assert page_dict["director_brief"] == brief
