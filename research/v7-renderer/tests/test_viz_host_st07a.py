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


def test_casestudy_hero_scene_band_renders_when_resolved(tmp_path) -> None:
    """A resolved case_scene slot renders a .csh-scene supporting band INSIDE
    the left narrative column (between sections) on the A3 spread — the visual
    that fills the void bands."""
    page = _st07a_page()
    page["layout_variant"] = "casestudy_hero"
    page["slots"] = [{"slot_id": "case_scene", "path": _scene_png(tmp_path)}]
    ctx = _SceneCtx(_apex_ctx(), _scene_png(tmp_path))
    html = st_07a.render(page, ctx).html
    assert "csh-scene" in html
    assert "cs_scene.png" in html


def test_casestudy_hero_scene_absent_renders_no_empty_box() -> None:
    """No case_scene slot -> no .csh-scene markup at all (graceful, never an
    empty frame — a client without a generated scene gets the clean spread)."""
    page = _st07a_page()
    page["layout_variant"] = "casestudy_hero"
    page["slots"] = []
    html = st_07a.render(page, _apex_ctx()).html
    assert "csh-scene" not in html
