"""TDD for the template-driven PLACEMENT engine (Phase 4, Task 3).

Offline: the per-region content is supplied by a fake render_region, so we test
PLACEMENT (geometry, z, class, graceful-omit) precisely; plus render_macro proves
the existing macro library is reachable for the role binder (Task 5).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from layout_template import LayoutTemplate  # noqa: E402
from patterns._template_driven import render_from_template, render_macro  # noqa: E402


def _template() -> LayoutTemplate:
    return LayoutTemplate.from_dict({
        "st_type": "ST-07A",
        "variant": "authority-rail",
        "grid": {"columns": 12, "margin": {"top": 0.05, "right": 0.05,
                 "bottom": 0.05, "left": 0.05}, "gutter": 0.02},
        "regions": [
            {"role": "headline", "x": 0.05, "y": 0.13, "w": 0.55, "h": 0.18, "z": 2},
            {"role": "stat_rail", "x": 0.62, "y": 0.06, "w": 0.33, "h": 0.88, "z": 1},
            {"role": "footer", "x": 0.01, "y": 0.10, "w": 0.03, "h": 0.50},
        ],
        "type_roles": {"headline": "display", "body": "body"},
        "color_roles": {"ground": "ground", "ink": "ink", "accent": "accent"},
        "whitespace_target": 0.2,
        "source_refs": [{"deck": "niklas", "page_no": 8}],
    })


def test_places_regions_with_geometry_and_omits_empty():
    tpl = _template()

    def render_region(r, i):
        # the footer region returns no content -> must be OMITTED (graceful)
        if r.role == "footer":
            return None
        return f"<b>{r.role}</b>"

    frag = render_from_template(tpl, render_region=render_region)
    html = frag.html
    # headline placed at its geometry (x .05 -> left 5%, y .13 -> top 13%, etc.)
    assert 'class="tpl-region tpl-region--headline"' in html
    assert "left:5.000%;top:13.000%;width:55.000%;height:18.000%;z-index:2" in html
    # stat_rail placed
    assert "left:62.000%;top:6.000%;width:33.000%;height:88.000%;z-index:1" in html
    # footer omitted (render_region returned None)
    assert "tpl-region--footer" not in html
    # content dispatched
    assert "<b>headline</b>" in html and "<b>stat_rail</b>" in html
    # scoped CSS, no forbidden head rules
    assert ".tpl-page" in frag.css and ".tpl-region" in frag.css
    for forbidden in ("@page", ":root", "@font-face", "<style"):
        assert forbidden not in frag.css


def test_render_macro_reaches_component_library():
    out = render_macro("section_label.jinja", "section_label", text="AUSGANGSSITUATION")
    assert "AUSGANGSSITUATION" in out
    head = render_macro("two_tone_headline.jinja", "two_tone_headline",
                        lead="Dein Wachstum", accent="FRISST")
    assert "Dein Wachstum" in head and "FRISST" in head


def test_no_regions_rendered_when_all_empty():
    tpl = _template()
    frag = render_from_template(tpl, render_region=lambda r, i: None)
    # the page box still exists but carries no region frames
    assert '<div class="tpl-page">' in frag.html
    assert "tpl-region" not in frag.html
