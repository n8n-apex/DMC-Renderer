"""Offline TDD for the ST-07A template binder (Phase 4, Task 5).

No render: drives the role binder over the real niklas template with fake page
data + a fake ctx, asserting per-role occurrence indexing + graceful omit.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from layout_template import LayoutTemplate  # noqa: E402
from patterns.st_07a_tpl import (  # noqa: E402
    _TEMPLATE_PATH, render as st07a_tpl_render, st07a_region_renderer,
)


class _Brand:
    company_url_display = "apex-consulting.ai"
    company_name_short = "APEX Consulting"


class _Ctx:
    brand = _Brand()

    def slot_uri(self, page, slot_id):  # no portrait resolved
        return None


def _page():
    return {"st_type": "ST-07A", "data": {
        "fallstudie_number": "1",
        "ergebnis_headline": "Von operativem Chaos zu skalierbarer KI",
        "ausgangsproblem": "Rapides Wachstum.",
        "ziel": "Den Engpass loesen.",
        "loesung": "Custom KI-Agenten.",
        "ergebnis_text": "Belastung eliminiert.",
        "ergebnis_metrics": [
            {"value": "24 Std. → Minuten", "label": "Antwortzeit"},
            {"value": "> 200.000 €", "label": "Einsparung"},
            {"value": "4", "label": "Kernprozesse"},
        ],
        "kunde": {"name": "Martina Ammon", "funktion": "Gründerin", "company_url": "ammon.de"},
        "pullquote": {"text": "APEX hat uns geholfen.", "attribution": "Martina Ammon"},
    }}


def test_binder_occurrence_indexing_and_omit():
    tpl = LayoutTemplate.from_dict(json.loads(_TEMPLATE_PATH.read_text(encoding="utf-8")))
    rr = st07a_region_renderer(_page(), _Ctx())
    out = [(r.role, rr(r, i)) for i, r in enumerate(tpl.regions)]

    kickers = [h for role, h in out if role == "kicker" and h]
    bodies = [h for role, h in out if role == "body" and h]
    stats = [h for role, h in out if role == "stat" and h]

    # kicker occurrence order = the four fixed section headings
    assert "Ausgangssituation" in kickers[0]
    assert "Ziel" in kickers[1]
    assert "Lösung" in kickers[2]
    assert "Ergebnis" in kickers[3]
    # body occurrence order matches the sections
    assert "Rapides Wachstum" in bodies[0]
    assert "Custom KI-Agenten" in bodies[2]
    # stat occurrence order = the three metrics
    assert "Antwortzeit" in stats[0]
    assert "200.000" in stats[1]
    assert "Kernprozesse" in stats[2]
    # headline + eyebrow present
    assert any(role == "headline" and h and "skalierbarer" in h for role, h in out)
    assert any(role == "eyebrow" and h and "FALLSTUDIE" in h for role, h in out)
    # portrait omitted (no slot resolved)
    assert all(h is None for role, h in out if role == "portrait")


def test_render_returns_placed_fragment():
    frag = st07a_tpl_render(_page(), _Ctx())
    assert '<div class="tpl-page">' in frag.html
    assert "tpl-region--headline" in frag.html
    assert "tpl-region--stat" in frag.html
    assert "tpl-region--portrait" not in frag.html  # omitted (no slot)
    assert ".tpl-stat-v" in frag.css
