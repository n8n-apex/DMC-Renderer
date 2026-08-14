"""Tests for the structure_content stage."""
from __future__ import annotations

from types import SimpleNamespace

from models_charts import BeforeAfterBars
from models_pagedata import CaseStudyData, GenericPageData
from models_social import SocialProofBlock
from stages.structure_content import structure_content


def _page(slot, type_, data):
    return SimpleNamespace(slot=slot, type=type_, data=data)


def test_typed_data_per_page() -> None:
    sc = structure_content([_page(7, "ST-07A", {"kunde": {"name": "N"}, "ziel": "z"})])
    p = sc.pages[0]
    assert isinstance(p.data, CaseStudyData)
    assert p.data.kunde.name == "N"
    assert p.warnings == []


def test_before_after_auto_from_two_numeric_metrics() -> None:
    sc = structure_content([_page(7, "ST-07A", {
        "ergebnis_metrics": [
            {"label": "vorher", "value": "172.549 €"},
            {"label": "nachher", "value": "290.100 €"},
        ],
    })])
    charts = sc.pages[0].charts
    assert len(charts) == 1
    assert isinstance(charts[0], BeforeAfterBars)
    assert charts[0].before_value == 172549.0
    assert charts[0].after_value == 290100.0
    assert charts[0].before_label == "vorher"


def test_no_auto_chart_when_not_two_numeric() -> None:
    sc = structure_content([_page(6, "ST-06", {"metrics": [{"value": "x"}, {"value": "y"}, {"value": "z"}]})])
    assert sc.pages[0].charts == []


def test_no_auto_chart_when_labels_lack_before_after_signal() -> None:
    """Two unrelated numeric stats (e.g. an About page "50 Kunden / 10 Jahre")
    must NOT be turned into a fabricated before/after comparison
    (PRD §8.3 lane ①, DNA §C5). Both values parse to numbers, so the old code
    would wrongly emit a misleading '50 -> 10' BeforeAfterBars."""
    sc = structure_content([_page(5, "ST-05", {
        "stats": [
            {"label": "Kunden", "value": "50"},
            {"label": "Jahre", "value": "10"},
        ],
    })])
    assert sc.pages[0].charts == []


def test_before_after_auto_only_with_before_after_signal() -> None:
    """Two numeric stats whose labels genuinely encode before/after DO yield
    exactly one BeforeAfterBars."""
    sc = structure_content([_page(6, "ST-06", {
        "metrics": [
            {"label": "Ohne KI", "value": "14"},
            {"label": "Mit KI", "value": "50"},
        ],
    })])
    charts = sc.pages[0].charts
    assert len(charts) == 1
    assert isinstance(charts[0], BeforeAfterBars)
    assert charts[0].before_value == 14
    assert charts[0].after_value == 50


def test_explicit_chart_is_parsed() -> None:
    sc = structure_content([_page(6, "ST-06", {"chart": {"kind": "comparison_columns", "ohne": ["a"], "mit": ["b"]}})])
    charts = sc.pages[0].charts
    assert len(charts) == 1
    assert charts[0].kind == "comparison_columns"


def test_social_proof_validated() -> None:
    sc = structure_content([_page(10, "ST-10", {"social_proof": {"ratings": [{"platform": "Google", "score": 4.9}]}})])
    sp = sc.pages[0].social_proof
    assert isinstance(sp, SocialProofBlock)
    assert sp.ratings[0].platform == "Google"


def test_bad_data_degrades_and_collects_warning() -> None:
    sc = structure_content([_page(2, "ST-02", {"zielgruppe": 123})])
    p = sc.pages[0]
    assert isinstance(p.data, GenericPageData)
    assert p.warnings and "ST-02" in p.warnings[0]
    assert sc.warnings


def test_accepts_dict_pages() -> None:
    sc = structure_content([{"slot": 2, "type": "ST-02", "data": {"title": "t"}}])
    assert sc.pages[0].st_type == "ST-02"
    assert sc.pages[0].data.title == "t"


def test_no_social_proof_is_none() -> None:
    sc = structure_content([_page(2, "ST-02", {"title": "t"})])
    assert sc.pages[0].social_proof is None
