"""WIRING CONFORMANCE GATE — the durable source of truth for "is the generative
pipeline actually wired into the shipped deck?"

WHY THIS EXISTS: the built-vs-used gap (fal/Nano Banana, social/diagram routing,
infographics) has been re-litigated ~3 times across context compactions because
the knowledge lived only in conversation and nothing in the repo ENFORCED the
wiring. This gate fixes that: run it FIRST, and GREEN rows are wired, RED rows are
exactly the work remaining. See memory `generative-pipeline-wiring-state` and the
plan docs/superpowers/plans/2026-06-17-bake-in-generative-pipeline.md.

Rows are intentionally RED until each plan phase wires them (idiomatic here — the
design-conformance gate keeps tests red on purpose as the definition of done).
The anti-REGRESSION rows (currently GREEN) must STAY green: they lock in what the
shipped deck already does so it cannot silently fall back to the frozen/cached path.

Run: pytest tests/test_wiring_conformance.py -v
"""
import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
V7 = HERE.parent                       # research/v7-renderer
RESEARCH = V7.parent                   # research
PRE = RESEARCH / "preprocessor"

ROUTE_PACKAGE = PRE / "stages" / "route_package.py"
MAIN = PRE / "main.py"
BUILD_PACKAGE = V7 / "fixtures" / "apex" / "build_package.py"
RENDER_PY = V7 / "render.py"
FIXTURE = V7 / "fixtures" / "apex" / "resolved_package.json"


def _text(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ---------------------------------------------------------------------------
# ANTI-REGRESSION rows (must STAY green) — what the shipped deck already does.
# ---------------------------------------------------------------------------

def test_shipped_deck_carries_social_routing_output():
    """The frozen fixture must still show routing output, so a fall-back to an
    un-routed package is caught. Exactly one ST-07A page carries a social_post."""
    pkg = json.loads(_text(FIXTURE))
    case_posts = [
        p for p in pkg["pages"]
        if p["st_type"] == "ST-07A" and (p.get("data") or {}).get("social_post")
    ]
    assert len(case_posts) == 1, f"social routing missing from deck: {len(case_posts)} posts"


def test_shipped_deck_carries_diagram_routing_output():
    pkg = json.loads(_text(FIXTURE))
    diagram_pages = [p for p in pkg["pages"] if (p.get("data") or {}).get("diagram")]
    assert diagram_pages, "diagram proof layer missing from the shipped deck"


# ---------------------------------------------------------------------------
# WIRING rows — RED until the plan phase that wires each lands. RED = to-do.
# ---------------------------------------------------------------------------

def test_phase1_shared_route_package_exists():
    assert ROUTE_PACKAGE.exists(), "Phase 1: create stages/route_package.py"
    assert "def route_package" in _text(ROUTE_PACKAGE)


def test_phase1_render_endpoint_calls_route_package():
    assert "route_package(" in _text(MAIN), \
        "Phase 1: /render must call the shared route_package() so production gets routing"


def test_phase1_build_package_calls_route_package():
    assert "route_package(" in _text(BUILD_PACKAGE), \
        "Phase 1: build_package must call shared route_package() (stop the divergence)"


def test_phase2_renderer_accepts_package_dir():
    assert "--package-dir" in _text(RENDER_PY), \
        "Phase 2: render.py must accept --package-dir so it isn't bound to the frozen fixture"


def test_phase3_build_package_has_real_fal_path():
    txt = _text(BUILD_PACKAGE)
    assert ("generate_assets(" in txt) or ("--fal" in txt), \
        "Phase 3: build_package must be able to call real fal generate_assets (not only _build_asset_plan)"


def test_phase3_no_stale_fixture_provenance_when_fal_on():
    """Anti-CACHE: once fal generation is active for the deck, NO asset may still
    carry the pre-baked-reuse provenance. Skipped until fal is turned on (a marker
    file written by the fal build); this is the row that stops 'it was using cached
    things' from recurring silently."""
    marker = V7 / "fixtures" / "apex" / ".fal_active"
    if not marker.exists():
        pytest.skip("fal not yet activated for the deck (Phase 3); provenance check dormant")
    pkg = json.loads(_text(FIXTURE))
    stale = [
        a for p in pkg["pages"] for a in (p.get("assets") or [])
        if "reused apex fixture image" in (a.get("message") or "")
    ] + [
        a for a in pkg.get("report_assets", [])
        if "reused apex fixture image" in (a.get("message") or "")
    ]
    assert not stale, f"fal is active but {len(stale)} assets still carry pre-baked provenance"
