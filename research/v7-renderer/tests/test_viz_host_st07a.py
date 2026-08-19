"""ST-07A host wiring for the data-viz PRESET layer.

The first ST-07A page is a `casestudy_hero` spread, whose RIGHT half is a floating
dark-island dashboard: a rate/ratio viz renders as a BESPOKE ring DEVICE drawn for
the navy panel (cream figure + label), NOT the cream `c-viz` macro — the macro is
styled flat-on-cream and would clash on the dark panel. The cream macro path is
still exercised by the `standard` / `magazine` variants (see test_render_r2). When
viz is absent the dashboard promotes the lead metric instead; either way no
`c-viz` macro leaks. Reuses the real apex package + ctx helper from
test_st07a_fill_variant.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from package_loader import load_package  # noqa: E402
from patterns import st_07a  # noqa: E402
from tests.test_st07a_fill_variant import _apex_ctx, APEX  # noqa: E402


def _st07a_page() -> dict:
    pkg = load_package(APEX)
    page = copy.deepcopy(next(p for p in pkg.pages if str(p.get("st_type")) == "ST-07A"))
    return page


def test_viz_renders_when_present():
    ctx = _apex_ctx()
    page = _st07a_page()
    page["data"]["viz"] = [
        {"preset": "completion_ring", "percent": 100, "center": "6/6", "label": "Prozesse"}
    ]
    # the LEGACY ST-07A's magazine variant hosts viz (cs-mag-viz); the fill
    # variant (the A4 default) does not consume a viz module. The deck renders
    # case studies through the a4_case_study TREATMENT; this test pins the
    # legacy magazine host so the viz path stays covered.
    page["layout_variant"] = "magazine"
    frag = st_07a.render(page, ctx)
    assert "cs-mag-viz" in frag.html
    assert "6/6" in frag.html and "Prozesse" in frag.html
    assert "csh-dev-donut" not in frag.html


def test_no_viz_unchanged():
    ctx = _apex_ctx()
    page = _st07a_page()
    page["data"].pop("viz", None)
    frag = st_07a.render(page, ctx)
    assert "c-viz" not in frag.html


class _SceneCtx:
    """A ctx that resolves a case_scene slot (path to a real PNG) — proves the
    A3 spread's supporting-scene band renders between narrative sections."""

    def __init__(self, real_ctx, scene_path: str | None):
        self._inner = real_ctx
        self._scene_path = scene_path

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def slot_uri(self, page, slot_id, **kwargs):
        if slot_id == "case_scene" and self._scene_path:
            return self._scene_path
        return self._inner.slot_uri(page, slot_id, **kwargs)


def _scene_png(tmp_path) -> str:
    from PIL import Image

    p = tmp_path / "cs_scene.png"
    Image.new("RGB", (320, 180), (25, 42, 58)).save(p)
    return str(p)


def test_casestudy_hero_scene_removed_even_when_resolved(tmp_path) -> None:
    """US-505 (Richard grammar): abstract fal scene bands are REMOVED from the
    A3 spreads — Richard never uses abstract generative art; his case-study
    spreads use data devices + real photography. Even a resolved case_scene
    slot renders NO .csh-scene markup."""
    page = _st07a_page()
    page["layout_variant"] = "casestudy_hero"
    page["slots"] = [{"slot_id": "case_scene", "path": _scene_png(tmp_path)}]
    ctx = _SceneCtx(_apex_ctx(), _scene_png(tmp_path))
    html = st_07a.render(page, ctx).html
    assert "csh-scene" not in html, "abstract art bands are forbidden on spreads"


def test_casestudy_hero_scene_absent_renders_no_empty_box() -> None:
    """No case_scene slot -> no .csh-scene markup (graceful — and with US-505
    the markup NEVER renders: the proof panel + measure carry the spread)."""
    page = _st07a_page()
    page["layout_variant"] = "casestudy_hero"
    page["slots"] = []
    html = st_07a.render(page, _apex_ctx()).html
    assert "csh-scene" not in html


def test_casestudy_hero_right_proof_is_short_box_quote_outside() -> None:
    """REVERTED (user 2026-08-16): the A3 right "Das Ergebnis" panel is a SHORT
    clean box (auto-height), NOT a full-height stretched panel — the stretched
    version was an abomination against the negative space. The quote is a
    sibling BELOW the box (cream), not inside it. The negative space is the
    Director's infographic job."""
    page = _st07a_page()
    page["layout_variant"] = "casestudy_hero"
    html = st_07a.render(page, _apex_ctx()).html
    assert "csh-dash" in html
    assert "csh-quote" in html
    assert "csh-quote--on-dark" not in html, "quote must NOT be inside the dark box"
    # the quote comes AFTER the dash closes (sibling, not child)
    dash_end = html.index("</div>", html.index("csh-dash-kpis") if "csh-dash-kpis" in html else html.index("csh-dash"))
    quote_pos = html.index("csh-quote")
    assert quote_pos > dash_end, "quote must be OUTSIDE (below) the dark box"


def test_casestudy_hero_dash_is_auto_height_via_css() -> None:
    """The dash must be auto-height (flex:0 1 auto) — the short clean box."""
    page = _st07a_page()
    page["layout_variant"] = "casestudy_hero"
    css = st_07a.render(page, _apex_ctx()).css
    import re

    block = re.search(r"\.st-07a \.csh-dash\s*\{([^}]*)\}", css, re.S)
    assert block, "missing .csh-dash rule"
    assert "flex: 0 1 auto" in block.group(1), (
        f".csh-dash must be auto-height (short box); got: {block.group(1)}"
    )


def test_metric_transform_german_sentence_case() -> None:
    """US-504: a lowercase-start phrase in a metric transform ("von bis zu 24
    Stunden auf Minuten") is sentence-cased so it reads as proper German, not a
    sloppy typo (the audit flagged p12/p15)."""
    page = _st07a_page()
    page["data"]["ergebnis_metrics"] = [
        {"label": "Reaktionszeit", "value": "von bis zu 24 Stunden auf Minuten"},
    ]
    html = st_07a.render(page, _apex_ctx()).html
    assert "Von bis zu 24 Stunden" in html, "transform 'from' must be sentence-cased"


def test_casestudy_hero_fills_void_with_data_infographic_band() -> None:
    """The Director's infographic placement: the A3 spread's negative space
    (below the short dash) is filled with a DATA band — the real viz devices
    + remaining metrics rendered as flat stat cells. NEVER decorative art;
    always the page's actual figures."""
    page = _st07a_page()
    page["layout_variant"] = "casestudy_hero"
    page["data"]["ergebnis_metrics"] = [
        {"value": "von 30 auf 2 Minuten", "label": "Onboarding-Zeit"},
        {"value": "von 60 auf 5 Minuten", "label": "Copywriting pro Asset"},
        {"value": "3 kritische Workflows eliminiert", "label": "Operative Engpässe"},
    ]
    page["data"]["viz"] = [
        {"preset": "transform_arrow",
         "from": {"value": "30 Minuten", "label": "Onboarding vorher"},
         "to": {"value": "2 Minuten", "label": "mit APEX"}},
    ]
    html = st_07a.render(page, _apex_ctx()).html
    assert "csh-infographics" in html, "the infographic band must render"
    assert "30 Minuten" in html and "2 Minuten" in html, "real transform data must show"
    assert "3 kritische Workflows eliminiert" in html, "real metric must show"


def test_casestudy_hero_infographics_absent_without_data() -> None:
    """No metrics/viz -> no infographic band (never an empty filler)."""
    page = _st07a_page()
    page["layout_variant"] = "casestudy_hero"
    page["data"]["ergebnis_metrics"] = []
    page["data"]["viz"] = []
    html = st_07a.render(page, _apex_ctx()).html
    assert "csh-infographics" not in html
