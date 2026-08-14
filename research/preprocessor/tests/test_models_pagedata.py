"""Tests for the typed per-ST page-data schemas + parse_page_data dispatch."""
from __future__ import annotations

from models_pagedata import (
    CaseStudyData,
    GenericPageData,
    IntroData,
    StatItem,
    parse_page_data,
)


def test_case_study_full_structured() -> None:
    data = {
        "kurzportraet": "kp", "ausgangsproblem": "ap", "ziel": "z", "loesung": "l",
        "ergebnis_text": "et", "ergebnis_headline": "eh", "fallstudie_number": 3,
        "ergebnis_metrics": [{"label": "Umsatz", "value": "+172%"}, "6 Wochen: Zeit"],
        "kunde": {"name": "N", "funktion": "F", "company_url": "https://k.test"},
        "pullquote": {"text": "great", "attribution": "N, F"},
    }
    parsed, warn = parse_page_data("ST-07A", data)
    assert warn is None
    assert isinstance(parsed, CaseStudyData)
    assert parsed.kunde.name == "N"
    assert parsed.pullquote.text == "great"
    assert isinstance(parsed.ergebnis_metrics[0], StatItem)
    assert parsed.ergebnis_metrics[0].label == "Umsatz"
    assert parsed.ergebnis_metrics[1] == "6 Wochen: Zeit"


def test_missing_fields_validate_as_none() -> None:
    parsed, warn = parse_page_data("ST-07A", {})
    assert warn is None
    assert isinstance(parsed, CaseStudyData)
    assert parsed.kunde is None
    assert parsed.pullquote is None
    assert parsed.ergebnis_metrics == []


def test_extra_keys_preserved() -> None:
    parsed, warn = parse_page_data("ST-02", {"title": "t", "mystery": "keep me"})
    assert warn is None
    assert isinstance(parsed, IntroData)
    assert parsed.model_dump().get("mystery") == "keep me"


def test_unknown_type_is_generic_no_warning() -> None:
    parsed, warn = parse_page_data("ST-99", {"anything": 1})
    assert warn is None
    assert isinstance(parsed, GenericPageData)
    assert parsed.model_dump().get("anything") == 1


def test_bad_data_on_known_type_degrades_with_warning() -> None:
    parsed, warn = parse_page_data("ST-02", {"zielgruppe": 123})
    assert warn is not None and "ST-02" in warn
    assert isinstance(parsed, GenericPageData)


def test_non_dict_data_degrades() -> None:
    parsed, warn = parse_page_data("ST-01", ["not", "a", "dict"])  # type: ignore[arg-type]
    assert warn is not None
    assert isinstance(parsed, GenericPageData)


def test_cover_proof_stats_mixed_forms() -> None:
    parsed, warn = parse_page_data("ST-01", {
        "title": "T", "kicker_pills": ["a", "b"],
        "proof_stats": ["172%: Wachstum", {"value": "50k", "label": "Leads"}],
        "author": {"name": "A", "role": "Founder"},
    })
    assert warn is None
    assert parsed.kicker_pills == ["a", "b"]
    assert parsed.proof_stats[0] == "172%: Wachstum"
    assert isinstance(parsed.proof_stats[1], StatItem)
    assert parsed.author.role == "Founder"


def test_collaboration_steps_have_n_and_dauer() -> None:
    parsed, warn = parse_page_data("ST-22", {
        "title": "Ablauf",
        "steps": [{"n": 1, "title": "Kickoff", "body": "b", "dauer": "1 Woche"}, "freitext"],
    })
    assert warn is None
    assert parsed.steps[0].n == 1
    assert parsed.steps[0].dauer == "1 Woche"
    assert parsed.steps[1] == "freitext"
