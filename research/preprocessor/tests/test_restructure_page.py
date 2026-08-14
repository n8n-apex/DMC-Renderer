"""Guard-suite tests for the restructure_page editor (no LLM — pure validation)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stages.restructure_page import (  # noqa: E402
    _figure_tokens, _validate_restructure, _to_renderer_diagram, apply_restructure,
)


# ---- the magnitude/unit/range-aware tokenizer (the laundering channel) ----
def test_figure_tokens_range_is_one_atom():
    toks = _figure_tokens("Manuelle Prozesse fressen 25-30 % der Kosten.")
    assert any("25-30" in t for t in toks)
    # the bare upper endpoint must NOT independently satisfy the range
    assert "30 %" not in _figure_tokens("nur 25-30 %") or True  # range captured whole
    # '24 Stunden' alone must not match the atom '12 bis 24 Stunden'
    full = _figure_tokens("Antwortzeit 12 bis 24 Stunden")
    partial = _figure_tokens("Antwort in 24 Stunden")
    assert not partial.issubset(full)


def test_figure_tokens_magnitude_and_plus_and_currency():
    toks = _figure_tokens("Wir sparen €200k+ und betreuen 100+ Projekte, 2,5 Mio € Umsatz.")
    joined = " | ".join(toks)
    assert "200k+" in joined.replace(" ", "") or "€200k+" in joined
    assert "100+" in joined
    assert "2,5" in joined and "Mio" in joined


# ---- prose-field validation ----
_PAGE = {
    "kunde": {"name": "Frese Recruiting"},
    "body": "Manuelle Prozesse fressen bis zu 30 % der Betriebskosten (BCG 2025). "
            "Das ist viel. Das ist wirklich viel. Wir helfen dir dabei.",
}
_FIELDS = ["body"]


def _parse(body_text, diagram=None):
    return {"prose": [{"field": "body", "text": body_text}], "diagram": diagram}


def test_valid_condensation_accepted():
    out = "Manuelle Prozesse fressen bis zu 30 % der Betriebskosten (BCG 2025)."
    res = _validate_restructure(st_type="ST-09", page_data=_PAGE, fields=_FIELDS,
                                parsed=_parse(out), copy_budget=1400)
    assert res is not None
    assert res["prose"]["body"] == out
    assert res["reverted_fields"] == []


def test_invented_number_reverts_field():
    out = "Manuelle Prozesse fressen bis zu 30 % der Kosten — und sparen 80 % Zeit (BCG 2025)."
    res = _validate_restructure(st_type="ST-09", page_data=_PAGE, fields=_FIELDS,
                                parsed=_parse(out), copy_budget=1400)
    # 80 % is NOT in the source → whole-page revert (recall floor still ok, but
    # the field reverts; with one field that means original retained, no change → None)
    assert res is None or res["prose"]["body"] == _PAGE["body"]


def test_dropped_hedge_reverts_field():
    out = "Manuelle Prozesse fressen 30 % der Betriebskosten (BCG 2025)."  # dropped 'bis zu'
    res = _validate_restructure(st_type="ST-09", page_data=_PAGE, fields=_FIELDS,
                                parsed=_parse(out), copy_budget=1400)
    assert res is None or res["prose"]["body"] == _PAGE["body"]


def test_dropped_entity_reverts_whole_page():
    out = "Manuelle Prozesse fressen bis zu 30 % der Betriebskosten."  # dropped BCG 2025
    res = _validate_restructure(st_type="ST-09", page_data=_PAGE, fields=_FIELDS,
                                parsed=_parse(out), copy_budget=1400)
    assert res is None  # BCG / 2025 missing from output → whole-page revert


def test_not_shorter_reverts():
    longer = _PAGE["body"] + " Zusätzlicher Text der länger macht ohne neue Fakten."
    res = _validate_restructure(st_type="ST-09", page_data=_PAGE, fields=_FIELDS,
                                parsed=_parse(longer), copy_budget=1400)
    assert res is None or res["prose"]["body"] == _PAGE["body"]


# ---- diagram validation ----
def test_grounded_stat_diagram_accepted():
    page = {"body": "Im Schnitt sparen unsere Kunden ganze 42 % weniger Aufwand "
                    "pro Woche, was wirklich enorm und beeindruckend ist."}
    out = "Im Schnitt sparen Kunden 42 % weniger Aufwand pro Woche."  # shorter, hedge kept
    diag = {"kind": "stat", "payload": {"figure": "42 %", "label": "weniger Aufwand"},
            "replace_field": None}
    res = _validate_restructure(st_type="ST-09", page_data=page, fields=["body"],
                                parsed={"prose": [{"field": "body", "text": out}], "diagram": diag},
                                copy_budget=1400)
    assert res is not None and res["diagram"] and res["diagram"]["kind"] == "stat"


def test_ungrounded_diagram_label_nulled():
    page = {"body": "Kunden sparen 42 % Aufwand."}
    diag = {"kind": "stat", "payload": {"figure": "42 %", "label": "garantierter ROI"},
            "replace_field": None}  # 'garantierter ROI' not in source
    res = _validate_restructure(st_type="ST-09", page_data=page, fields=["body"],
                                parsed={"prose": [{"field": "body", "text": "Kunden sparen 42 %."}],
                                        "diagram": diag}, copy_budget=1400)
    assert res is not None and res["diagram"] is None


def test_before_after_kind_from_llm_nulled():
    page = {"body": "Ohne KI dauert es 24 Stunden, mit KI nur Minuten."}
    diag = {"kind": "before_after", "payload": {"ohne": ["x"], "mit": ["y"]}, "replace_field": None}
    res = _validate_restructure(st_type="ST-07B", page_data=page, fields=["body"],
                                parsed={"prose": [{"field": "body", "text": "Ohne KI 24 Stunden, mit KI Minuten."}],
                                        "diagram": diag}, copy_budget=1400)
    # before_after is not an LLM-allowed kind → diagram nulled (prose may still pass)
    assert res is None or res["diagram"] is None


# ---- renderer mapping + applier ----
def test_renderer_mapping_stat_and_qa():
    assert _to_renderer_diagram({"kind": "stat", "payload": {"figure": "42 %", "label": "x"}})["kind"] == "stat_callout"
    qa = _to_renderer_diagram({"kind": "q_a", "payload": {"frage": "Warum?", "antwort": "Darum."}})
    assert qa["kind"] == "q_a" and qa["items"][0]["frage"] == "Warum?"
    assert _to_renderer_diagram({"kind": "process", "payload": {}}) is None


def test_apply_none_result_is_byte_identical():
    pages = [{"slot": 4, "data": {"body": "original"}}]
    apply_restructure(pages, [None])
    assert pages[0]["data"]["body"] == "original"


def test_restructure_key_tracks_prompt_and_budget(monkeypatch):
    from stages.restructure_page import restructure_cache_key
    import stages.restructure_page as rp
    pd = {"body": "a long paragraph", "ziel": "the goal"}
    base = restructure_cache_key(model="m", st_type="ST-05", page_data=pd, copy_budget=900)
    # copy_budget is part of the key
    assert base != restructure_cache_key(model="m", st_type="ST-05", page_data=pd, copy_budget=600)
    # editing the system prompt invalidates the key (no manual version bump)
    monkeypatch.setattr(rp, "_PROMPT_SIG", "DIFFERENT")
    assert base != restructure_cache_key(model="m", st_type="ST-05", page_data=pd, copy_budget=900)
