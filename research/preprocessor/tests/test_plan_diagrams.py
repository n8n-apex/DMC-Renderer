"""Tests for the diagram proof-layer planner (stages/plan_diagrams.py)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stages.plan_diagrams import plan_diagrams, apply_diagram_plan  # noqa: E402


def _pkg(pages):
    return {"pages": pages}


def _budget(_st):
    return 1000


def _chars(d):
    return sum(len(str(v)) for v in d.values() if isinstance(v, str))


def test_non_host_types_never_get_a_diagram():
    pages = [
        {"slot": 1, "st_type": "ST-01", "data": {"body": "30 % schneller"}},
        {"slot": 20, "st_type": "ST-03", "data": {"body": "60 % mehr"}},
        {"slot": 6, "st_type": "ST-31", "data": {"body": "15x"}},
    ]
    plan = plan_diagrams(_pkg(pages), char_count=_chars, copy_budget=_budget)
    assert plan.bindings == []


def test_existing_convergence_is_confirmed_not_overwritten():
    venn = {"kind": "convergence", "nodes": ["a", "b", "c"],
            "center_lead": "Systeme", "center": "statt Ressourcen"}
    pages = [{"slot": 5, "st_type": "ST-14", "data": {"diagram": dict(venn)}}]
    plan = plan_diagrams(_pkg(pages), char_count=_chars, copy_budget=_budget)
    assert len(plan.bindings) == 1
    b = plan.bindings[0]
    assert b.kind == "convergence" and b.mode == "replace"
    assert b.payload["center_lead"] == "Systeme"
    apply_diagram_plan(_pkg(pages), plan)
    assert pages[0]["data"]["diagram"]["nodes"] == ["a", "b", "c"]


def test_stat_callout_fires_on_text_light_page_with_headroom():
    pages = [{"slot": 4, "st_type": "ST-09",
              "data": {"body": "Manuelle Prozesse fressen 25-30 % der Kosten."}}]
    plan = plan_diagrams(_pkg(pages), char_count=_chars, copy_budget=_budget)
    assert len(plan.bindings) == 1
    b = plan.bindings[0]
    assert b.kind == "stat_callout" and b.mode == "augment"
    assert b.payload["figure"] == "25-30 %"          # verbatim, not computed
    apply_diagram_plan(_pkg(pages), plan)
    assert pages[0]["data"]["diagram"]["kind"] == "stat_callout"


def test_stat_callout_suppressed_when_page_near_budget():
    big = "x" * 800  # 800/1000 = 0.8 > 0.62 gate
    pages = [{"slot": 4, "st_type": "ST-09",
              "data": {"body": "30 % mehr", "loesung": big}}]
    plan = plan_diagrams(_pkg(pages), char_count=_chars, copy_budget=_budget)
    assert plan.bindings == []
    assert any("no headroom" in d for d in plan.dropped)


def test_real_chart_defers_the_diagram():
    pages = [{"slot": 4, "st_type": "ST-09", "charts": [{"kind": "bars"}],
              "data": {"body": "30 % mehr"}}]
    plan = plan_diagrams(_pkg(pages), char_count=_chars, copy_budget=_budget)
    assert plan.bindings == []
    assert any("real chart present" in d for d in plan.dropped)


def test_occupied_zone_skipped():
    pages = [{"slot": 12, "st_type": "ST-07A", "data": {"ergebnis_text": "15x mehr"}}]
    plan = plan_diagrams(_pkg(pages), occupied_zones=frozenset({12}),
                         char_count=_chars, copy_budget=_budget)
    assert plan.bindings == []


def test_no_figure_no_callout():
    pages = [{"slot": 4, "st_type": "ST-09", "data": {"body": "Kein einziger Wert hier."}}]
    plan = plan_diagrams(_pkg(pages), char_count=_chars, copy_budget=_budget)
    assert plan.bindings == []


def test_deterministic_and_budget_capped():
    pages = [{"slot": s, "st_type": "ST-09", "data": {"body": f"{s} %"}} for s in (2, 4, 8, 10, 13)]
    plan = plan_diagrams(_pkg(pages), char_count=_chars, copy_budget=_budget, max_diagrams=3)
    assert len(plan.bindings) == 3
    assert [b.page_slot for b in plan.bindings] == sorted(b.page_slot for b in plan.bindings)
    # determinism: same inputs → same output
    plan2 = plan_diagrams(_pkg(pages), char_count=_chars, copy_budget=_budget, max_diagrams=3)
    assert [b.page_slot for b in plan2.bindings] == [b.page_slot for b in plan.bindings]
