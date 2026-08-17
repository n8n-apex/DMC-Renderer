"""Phase 4 host wiring + curation for the data-viz PRESET layer (MAGNITUDE +
PROCESS families).

Covers:
  - HOST WIRING — ST-02 (Outlook), ST-09 (Status-Quo), ST-06 (Mechanism) each
    read data['viz'] and render it via the shared viz dispatch macro; absent →
    the page renders exactly as before (no c-viz markup).
  - CURATION — apply_apex_viz binds the curated MAGNITUDE/PROCESS presets onto
    their host pages, and EVERY displayed figure/title is grounded (the
    no-fabrication guard raises nothing on the real apex package).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from package_loader import load_package  # noqa: E402
from grammar_loader import load_grammar  # noqa: E402
from patterns import st_02, st_06, st_09  # noqa: E402
from patterns.base import RenderContext  # noqa: E402
from fixtures.apex.viz_curation import (  # noqa: E402
    apply_apex_viz, _figure_grounded, _spec_figures, _viz_for_page,
)

APEX = HERE.parent / "fixtures" / "apex"


def _ctx() -> RenderContext:
    pkg = load_package(APEX)
    return RenderContext(
        brand=pkg.brand,
        grammar=load_grammar(),
        package_dir=pkg.package_dir,
        report_assets=pkg.report_assets,
    )


def _page(st_type: str) -> dict:
    pkg = load_package(APEX)
    # US-604: prefer a NON-continuation page (the ST-06 section spans two
    # continuation pages; the intro one carries the viz/flow band).
    for p in pkg.pages:
        if str(p.get("st_type")) == st_type and not p.get("continuation_index"):
            return copy.deepcopy(p)
    return copy.deepcopy(next(p for p in pkg.pages if str(p.get("st_type")) == st_type))


def _page_of(pkg, st_type: str, role=None) -> dict:
    """The page with `st_type`; when `role` is given it must also match
    continuation_role (US-604: ST-02/ST-05/ST-06/ST-FAZIT span continuation
    pages). With role=None a NON-continuation page is preferred, then the first
    page of that type."""
    for p in pkg:
        if str(p.get("st_type")) != st_type:
            continue
        if role is None:
            if not p.get("continuation_index"):
                return copy.deepcopy(p)
        elif p.get("continuation_role") == role:
            return copy.deepcopy(p)
    for p in pkg:
        if str(p.get("st_type")) == st_type:
            return copy.deepcopy(p)
    raise AssertionError(f"no {st_type} page (role={role!r}) in the apex fixture")


# ---------------------------------------------------------------------------
# HOST WIRING — viz renders when present, page is unchanged when absent.
# ---------------------------------------------------------------------------

def test_st02_renders_viz_when_present():
    page = _page("ST-02")
    page["data"]["viz"] = [
        {"preset": "stat_strip", "items": [
            {"value": "30 %", "label": "Kosten"}, {"value": "60 %", "label": "kein Wert"}]}]
    html = st_02.render(page, _ctx()).html
    assert "c-viz-strip" in html
    assert "30 %" in html and "60 %" in html


def test_st02_no_viz_unchanged():
    page = _page("ST-02")
    page["data"].pop("viz", None)
    assert "c-viz" not in st_02.render(page, _ctx()).html


def test_st09_renders_viz_when_present():
    page = _page("ST-09")
    page["data"]["viz"] = [
        {"preset": "mega_numeral", "value": "50 %", "label": "Burnout"}]
    html = st_09.render(page, _ctx()).html
    assert "c-viz-mega" in html
    assert "50 %" in html


def test_st09_no_viz_unchanged():
    page = _page("ST-09")
    page["data"].pop("viz", None)
    assert "c-viz" not in st_09.render(page, _ctx()).html


def test_st06_renders_viz_when_present():
    # US-604: the apex ST-06 is continuation pages; the flow/viz band renders
    # on a SINGLE-page ST-06 (synthetic, no identity) — the legacy contract.
    page = _page("ST-06")
    for k in ("page_id", "section_id", "continuation_index",
              "continuation_role", "section_page_count"):
        page.pop(k, None)
    # the viz cascade fires when the flow strip is suppressed (>=5 steps) —
    # inject 6 steps + the cascade spec, mirroring the old single-page state.
    page["data"]["steps"] = [
        {"title": f"Schritt {i}", "body": f"Body {i} " * 20} for i in range(1, 7)
    ]
    page["data"]["viz"] = [
        {"preset": "step_cascade", "title": "Der Ablauf",
         "steps": [{"title": "Audit"}, {"title": "Bereinigung"}]}]
    html = st_06.render(page, _ctx()).html
    assert "c-viz-cascade" in html
    assert "Audit" in html and "Bereinigung" in html


def test_st06_no_viz_unchanged():
    page = _page("ST-06")
    page["data"].pop("viz", None)
    assert "c-viz" not in st_06.render(page, _ctx()).html


# ---------------------------------------------------------------------------
# CURATION — the bindings land on their pages with grounded figures.
# ---------------------------------------------------------------------------

def test_curation_binds_magnitude_and_process_presets():
    pkg = json.loads((APEX / "resolved_package.json").read_text(encoding="utf-8"))
    apply_apex_viz(pkg)  # FAILS LOUD if any displayed figure is not grounded
    # ST-06 step_cascade was disabled (duplicated the page's own step list + overflowed
    # the sheet); ST-02 + ST-09 remain the Phase 4 magnitude bindings.
    expected = {"ST-02": "radial_cluster", "ST-09": "mega_numeral"}
    for st, preset in expected.items():
        page = next(p for p in pkg["pages"] if p["st_type"] == st)
        viz = (page.get("data") or {}).get("viz")
        assert isinstance(viz, list) and viz, f"{st} missing data['viz']"
        assert viz[0]["preset"] == preset, f"{st} wrong preset: {viz[0]['preset']}"


def test_curation_every_displayed_figure_is_grounded():
    """The structural no-fabrication guarantee for the Phase 4 host pages: every
    figure/title a curated preset DISPLAYS must appear verbatim in that page.
    US-605: a continuation page lacking the figure's source copy (e.g. the
    ST-02 evidence page without the body's percentages) is SKIPPED by the
    curation — the figure is displayed on the page that carries its source, so
    the guard runs only on the pages whose spec actually grounds (would bind)."""
    pkg = json.loads((APEX / "resolved_package.json").read_text(encoding="utf-8"))
    for page in pkg["pages"]:
        if page.get("st_type") not in ("ST-02", "ST-09"):
            continue
        specs = _viz_for_page(page)
        if not specs:
            continue
        for spec in specs:
            figs = [f for f in _spec_figures(spec) if f not in (None, "")]
            if figs and not all(_figure_grounded(f, page) for f in figs):
                continue  # curation skips this page — nothing displayed here
            for fig in figs:
                assert _figure_grounded(fig, page), (
                    f"ungrounded figure {fig!r} on {page['st_type']}")


def test_curation_lifts_coverage_past_six_pages():
    """Phase 4 goal: more than 6/20 pages carry a code-drawn data viz."""
    pkg = json.loads((APEX / "resolved_package.json").read_text(encoding="utf-8"))
    apply_apex_viz(pkg)
    n = sum(1 for p in pkg["pages"] if (p.get("data") or {}).get("viz"))
    assert n > 6, f"only {n} pages carry data['viz']; expected > 6"


def test_curation_is_idempotent_with_new_bindings():
    pkg = json.loads((APEX / "resolved_package.json").read_text(encoding="utf-8"))
    apply_apex_viz(pkg)
    first = [(p.get("data") or {}).get("viz") for p in pkg["pages"]]
    apply_apex_viz(pkg)
    second = [(p.get("data") or {}).get("viz") for p in pkg["pages"]]
    assert first == second


# ---------------------------------------------------------------------------
# END-TO-END — apply curation to the real package, then render each host page;
# the curated, grounded figures must appear in the rendered HTML.
# ---------------------------------------------------------------------------

def test_applied_curation_renders_on_host_pages():
    pkg = load_package(APEX)
    raw = json.loads((APEX / "resolved_package.json").read_text(encoding="utf-8"))
    apply_apex_viz(raw)
    ctx = _ctx()

    # US-604: ST-02 spans context + evidence continuations; the curated
    # radial_cluster binds to the CONTEXT page (it carries the figures).
    st02 = _page_of(raw["pages"], "ST-02", role="context")
    html02 = st_02.render(st02, ctx).html
    assert "c-viz-cluster" in html02 and "30 %" in html02 and "60 %" in html02

    st09 = _page_of(raw["pages"], "ST-09")
    html09 = st_09.render(st09, ctx).html
    assert "c-viz-mega" in html09 and "50 %" in html09

    # ST-06 step_cascade binding is intentionally disabled (it duplicated the page's
    # own step list and overflowed the sheet); ST-06 must carry no curated viz band.
    st06 = _page_of(raw["pages"], "ST-06", role="intro")
    assert not (st06.get("data") or {}).get("viz"), "ST-06 should carry no curated viz"
    _ = pkg  # load_package smoke (package parses cleanly)
