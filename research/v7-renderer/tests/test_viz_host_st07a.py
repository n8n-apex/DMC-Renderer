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
    frag = st_07a.render(page, ctx)
    # casestudy_hero renders the rate/ratio viz as the dark-panel ring DEVICE,
    # carrying the verbatim figure + label (no cream c-viz macro on the navy panel).
    assert "csh-dev-donut" in frag.html
    assert "6/6" in frag.html and "Prozesse" in frag.html
    assert "c-viz-ring" not in frag.html


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


def test_casestudy_hero_right_proof_is_full_height_with_quote_inside() -> None:
    """US-403: the A3 spread's right "Das Ergebnis" panel must be a FULL-HEIGHT
    authority panel (Richard's proof-rail pattern), not an auto-height card
    parked at the top leaving a void. The quote seats INSIDE the dark panel as
    its closing statement; the panel owns the right column top-to-bottom."""
    page = _st07a_page()
    page["layout_variant"] = "casestudy_hero"
    html = st_07a.render(page, _apex_ctx()).html
    assert "csh-dash" in html
    assert "csh-quote--on-dark" in html
    # the quote must appear AFTER the KPI rail and BEFORE the dash's closing
    # wrapper — i.e. inside the dark panel, not as a cream sibling below it.
    kpi_pos = html.index("csh-dash-kpis")
    quote_pos = html.index("csh-quote--on-dark")
    # the dash is closed by the same </div> that ends .csh-right's child chain;
    # find the LAST closing div after the quote (the dash's end)
    tail = html[quote_pos:]
    dash_end = html.rindex("</div>", quote_pos)
    assert kpi_pos < quote_pos < dash_end, (
        "order must be: KPIs -> quote -> dash close (quote inside the panel)"
    )


def test_casestudy_hero_dash_is_full_height_via_css() -> None:
    """The dash rule must be flex:1 (fill the right column height), not
    auto-height (flex:0 1 auto) which left the lower-right void."""
    page = _st07a_page()
    page["layout_variant"] = "casestudy_hero"
    css = st_07a.render(page, _apex_ctx()).css
    import re

    block = re.search(r"\.st-07a \.csh-dash\s*\{([^}]*)\}", css, re.S)
    assert block, "missing .csh-dash rule"
    assert "flex: 1 1 auto" in block.group(1), (
        f".csh-dash must be flex:1 1 auto (full-height proof rail); got: {block.group(1)}"
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
