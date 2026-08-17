"""Tests for treatment_engine.adapt (Task TS-1.1, the data layer).

These tests pin the NORMALIZED TreatmentData model and the adapt(page, ctx)
mapper to the REAL apex fixture (fixtures/apex/resolved_package.json, 20 pages):
  - grounding: every value in TreatmentData traces to a value present in the
    page dict (no fabricated client literals, no invented defaults),
  - graceful degradation: adapt never crashes on missing slots / bypass types,
  - the per-st_type overrides (ST-07A, ST-05, ST-06/ST-22, ST-FAZIT) produce
    the structured fields their treatments will read.

Written FIRST (TDD): they import from treatment_engine and fail until the
module exists, then drive the implementation to green. Run ONLY this file:
  python -m pytest tests/test_treatment_engine.py -v
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from package_loader import load_package  # noqa: E402
from grammar_loader import load_grammar  # noqa: E402
from patterns.base import RenderContext  # noqa: E402
from treatment_engine import TreatmentData, adapt  # noqa: E402

FIXTURE = ROOT / "fixtures" / "apex"


def _page_of(pkg, st_type: str, role=None) -> dict:
    """The page with `st_type`; when `role` is given it must also match
    continuation_role (US-604: ST-02/ST-05/ST-06/ST-FAZIT span continuation
    pages). With role=None a NON-continuation page is preferred, then the first
    page of that type."""
    for pg in pkg.pages:
        if str(pg.get("st_type")) != st_type:
            continue
        if role is None:
            if not pg.get("continuation_index"):
                return pg
        elif pg.get("continuation_role") == role:
            return pg
    for pg in pkg.pages:
        if str(pg.get("st_type")) == st_type:
            return pg
    raise AssertionError(f"no {st_type} page (role={role!r}) in the apex fixture")


def _st07a_with_resolved_portrait(pkg) -> dict:
    """The ST-07A case study whose case_study_portrait slot RESOLVES (the
    editorial hero — now at a different index after US-604's continuation pages)."""
    for pg in pkg.pages:
        if str(pg.get("st_type")) != "ST-07A":
            continue
        for s in pg.get("slots") or []:
            if s.get("slot_id") == "case_study_portrait" and s.get("status") == "resolved":
                return pg
    raise AssertionError("no ST-07A with a resolved case_study_portrait")


# Treatment-eligible content types: their adapt result must carry real content
# (at least one of the narrative-bearing fields). The bypass types (ST-01 cover,
# ST-31 atemseite, ST-07B theory, ST-03 cta_hard) are handled gracefully but are
# NOT asserted non-empty here (they are intentionally bypassed by the system).
ELIGIBLE_TYPES = {
    "ST-02", "ST-05", "ST-09", "ST-14", "ST-07A", "ST-06", "ST-22", "ST-FAZIT",
}


@pytest.fixture(scope="module")
def pkg():
    return load_package(FIXTURE)


@pytest.fixture(scope="module")
def ctx(pkg):
    return RenderContext(
        brand=pkg.brand,
        grammar=load_grammar(),
        package_dir=pkg.package_dir,
        report_assets=pkg.report_assets,
    )


def _has_content(td: TreatmentData) -> bool:
    return bool(
        td.headline
        or td.body
        or td.stats
        or td.steps
        or td.sections
        or td.list_items
    )


def test_adapt_st07a_hero_grounded(pkg, ctx):
    """The ST-07A hero (the case study with a resolved portrait) maps to
    grounded fields."""
    page = _st07a_with_resolved_portrait(pkg)
    assert page["st_type"] == "ST-07A"
    data = page["data"]

    td = adapt(page, ctx)

    # headline override = ergebnis_headline (grounded, verbatim)
    assert td.headline == data["ergebnis_headline"]

    # stats values come EXACTLY from ergebnis_metrics (grounded, not invented)
    metric_values = [m["value"] for m in data["ergebnis_metrics"]]
    td_values = [s["value"] for s in td.stats]
    assert td_values == metric_values

    # primary portrait resolved to a non-empty file:// URI
    assert isinstance(td.image, str)
    assert td.image.startswith("file://")

    # quote from the page's pullquote, attribution from the kunde name
    assert td.quote is not None
    assert td.quote["text"] == data["pullquote"]["text"]
    assert data["kunde"]["name"] in (td.quote["attribution"] or "")

    # sections built from the (label, field) spec, grounded verbatim from the data
    labels = [s["label"] for s in td.sections]
    assert "Ausgangssituation" in labels
    assert "Lösung" in labels
    assert "Ergebnis" in labels
    for s in td.sections:
        assert s["text"], f"section {s['label']} has empty text"

    # client identity caption grounded from kunde (name/role for the case rail)
    assert td.caption is not None
    assert td.caption["name"] == data["kunde"]["name"]


def test_adapt_no_crash_on_missing_portrait(ctx):
    """ST-07A with NO portrait slot: no crash, image None, text-derived fields still
    populated (the a4_case_study rail falls back to an initials avatar from kunde).

    A synthetic page (the fixture's real case studies now carry portraits), so this
    exercises the imageless path deterministically."""
    page = {
        "st_type": "ST-07A",
        "data": {
            "fallstudie_number": 9,
            "ergebnis_headline": "Ein Ergebnis",
            "kurzportraet": "Kurzportrait des Kunden.",
            "ausgangsproblem": "Ausgangstext.",
            "loesung": "Loesungstext.",
            "ergebnis_text": "Ergebnistext.",
            "ergebnis_metrics": [{"value": "42%", "label": "Kennzahl"}],
            "pullquote": {"text": "Ein Zitat."},
            "kunde": {"name": "Max Muster", "funktion": "CEO"},
        },
    }
    td = adapt(page, ctx)  # must not raise

    assert td.image is None
    assert td.sections, "narrative sections should still be built from text"
    assert td.stats, "ergebnis_metrics should still map to stats"
    assert td.caption and td.caption["name"] == "Max Muster"


def test_adapt_all_pages_no_crash(pkg, ctx):
    """adapt EVERY page: no exception, always a TreatmentData; eligible content
    types carry real content."""
    for i, page in enumerate(pkg.pages):
        td = adapt(page, ctx)  # must not raise on any page (incl. bypass types)
        assert isinstance(td, TreatmentData), f"page {i} did not return TreatmentData"
        if page.get("st_type") in ELIGIBLE_TYPES:
            assert _has_content(td), f"eligible page {i} ({page['st_type']}) is empty"


def test_adapt_grounding_st05(pkg, ctx):
    """ST-05 (identity continuation): credentials = partners, stats = stats
    (grounded), images = the 3 resolved proof photos."""
    page = _page_of(pkg, "ST-05", role="identity")
    assert page["st_type"] == "ST-05"
    data = page["data"]

    td = adapt(page, ctx)

    assert td.credentials == data["partners"]
    # stats grounded: same values + labels
    assert [s["value"] for s in td.stats] == [s["value"] for s in data["stats"]]
    assert [s["label"] for s in td.stats] == [s["label"] for s in data["stats"]]
    assert len(td.images) == 3


def test_no_fabricated_client_literals_in_engine():
    """The engine source bakes NO client-specific literal as a default/fallback
    and NO raw hex color. (German structural section labels are allowed.)"""
    src = (ROOT / "treatment_engine.py").read_text(encoding="utf-8")
    lowered = src.lower()
    for needle in (
        "apex", "frese", "jousef", "conesso", "pure media", "apex-consulting",
    ):
        assert needle not in lowered, f"client literal {needle!r} leaked into engine"
    assert not re.search(r"#[0-9a-fA-F]{6}", src), "raw hex color literal in engine"
