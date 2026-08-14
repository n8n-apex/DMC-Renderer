"""Tests for Stage 3 — validate_copy (grammar §3.9)."""

from __future__ import annotations

import pytest

from models import CopyWarning
from stages.validate_copy import validate_copy


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _page(slot: int, ptype: str, data: dict) -> dict:
    return {"slot": slot, "type": ptype, "data": data}


def _rule_counts(warnings: list[CopyWarning]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for w in warnings:
        counts[w.rule] = counts.get(w.rule, 0) + 1
    return counts


# ─────────────────────────────────────────────────────────────────────────────
# Test cases (the 10 cases from the spec, plus a couple of edge cases)
# ─────────────────────────────────────────────────────────────────────────────


def test_1_clean_text_no_violations() -> None:
    """Clean copy → empty warnings list."""
    pages = [_page(1, "ST-01", {
        "title": "Wie 800 Exemplare in 90 Tagen 23 qualifizierte Anfragen brachten",
        "subtitle": "Der mechanische Hebel den 2026 keine Agentur mehr ignorieren kann.",
    })]
    warnings = validate_copy(pages)
    assert warnings == []


def test_2_innovativ_buzzword_flagged() -> None:
    """`innovativ` (or its inflections) is flagged with correct slot + field."""
    pages = [_page(3, "ST-09", {"intro": "Wir bieten innovative Lösungen für den Mittelstand."})]
    warnings = validate_copy(pages)
    assert len(warnings) == 1
    w = warnings[0]
    assert w.rule == "buzzword_denylist"
    assert w.page_slot == 3
    assert w.page_type == "ST-09"
    assert w.field_name == "intro"
    assert "innovative" in w.detail.lower()


def test_3_nachhaltig_in_sustainability_context_no_warning() -> None:
    """`nachhaltig` on a page with sustainability indicators is allowed."""
    pages = [_page(5, "ST-09", {
        "title": "Unser ökologischer Ansatz",
        "body": "Wir arbeiten nachhaltig und reduzieren CO2-Emissionen um 40%.",
    })]
    warnings = validate_copy(pages)
    counts = _rule_counts(warnings)
    # nachhaltig must NOT be flagged here
    assert counts.get("buzzword_denylist", 0) == 0, (
        f"sustainability context exception failed; warnings: {warnings}"
    )


def test_3b_nachhaltig_outside_sustainability_context_flagged() -> None:
    """Same word, no sustainability context → flagged."""
    pages = [_page(5, "ST-05", {"body": "Unser nachhaltig wachsendes Beratungsunternehmen."})]
    warnings = validate_copy(pages)
    assert any(w.rule == "buzzword_denylist" and "nachhaltig" in w.detail.lower()
               for w in warnings)


def test_4_second_nicht_sondern_flagged() -> None:
    """First "Nicht X, sondern Y" passes silently. Second is flagged."""
    pages = [
        _page(2, "ST-02", {"intro": "Es geht nicht um Geschwindigkeit, sondern um Präzision."}),
        _page(8, "ST-06", {"body": "Wir arbeiten nicht mit jedem, sondern nur mit ausgewählten Partnern."}),
    ]
    warnings = validate_copy(pages)
    nicht_warnings = [w for w in warnings if w.rule == "construction_limit_nicht_sondern"]
    assert len(nicht_warnings) == 1, (
        f"expected 1 cross-report 'Nicht … sondern' warning (the 2nd); "
        f"got {len(nicht_warnings)}: {nicht_warnings}"
    )
    # Warning should reference page 8 (the second occurrence)
    assert nicht_warnings[0].page_slot == 8


def test_5_konjunktiv_multiple_flagged() -> None:
    """Each subjunctive (Konjunktiv II) word is flagged."""
    pages = [_page(2, "ST-02", {
        "intro": "Du könntest mehr erreichen wenn du die Methode anwenden würdest.",
    })]
    warnings = validate_copy(pages)
    konjunktiv = [w for w in warnings if w.rule == "konjunktiv"]
    assert len(konjunktiv) >= 2, f"expected ≥2 konjunktiv warnings; got {konjunktiv}"


def test_6_verboten_opening_flagged() -> None:
    """Field opening with a forbidden phrase from §9 is flagged."""
    pages = [_page(2, "ST-02", {
        "intro": "In der heutigen Geschäftswelt ist Geschwindigkeit alles.",
    })]
    warnings = validate_copy(pages)
    assert any(w.rule == "verboten_opening" for w in warnings)


def test_7_vague_promise_without_number_flagged() -> None:
    """Phrase like 'bessere Ergebnisse' without a number nearby is flagged."""
    pages = [_page(1, "ST-01", {"subtitle": "Bessere Ergebnisse für mehr Wachstum."})]
    warnings = validate_copy(pages)
    assert any(w.rule == "vague_promise" for w in warnings)


def test_8_vague_promise_with_number_passes() -> None:
    """Same phrase with a number within ±30 chars passes the vague check."""
    pages = [_page(1, "ST-01", {
        "subtitle": "80% bessere Ergebnisse als der Branchenschnitt.",
    })]
    warnings = validate_copy(pages)
    vague = [w for w in warnings if w.rule == "vague_promise"]
    assert vague == [], f"number-near-phrase should bypass vague_promise: {vague}"


def test_9_buzzword_on_multiple_pages_correct_slots() -> None:
    """When the same buzzword appears on multiple pages, each warning
    references its own page slot.
    """
    pages = [
        _page(3, "ST-09", {"body": "Wir bieten innovative Lösungen."}),
        _page(7, "ST-14", {"body": "Unsere innovative Methode hilft dir."}),
    ]
    warnings = validate_copy(pages)
    buzz = [w for w in warnings if w.rule == "buzzword_denylist"]
    slots = sorted({w.page_slot for w in buzz})
    assert slots == [3, 7], f"expected warnings on slots [3, 7]; got {slots}"


def test_10_empty_data_no_crash() -> None:
    """Empty / minimal page data must not crash and must produce no warnings."""
    pages = [
        _page(1, "ST-01", {}),
        _page(2, "ST-02", {"title": ""}),
        _page(3, "ST-09", {"body": "    "}),  # whitespace only
        {"slot": 4, "type": "ST-14"},  # missing data key entirely
    ]
    warnings = validate_copy(pages)
    assert warnings == []


# ─────────────────────────────────────────────────────────────────────────────
# Edge-case coverage beyond the spec's 10
# ─────────────────────────────────────────────────────────────────────────────


def test_walker_finds_nested_strings() -> None:
    """The string walker descends into nested dicts and lists."""
    pages = [_page(10, "ST-07A", {
        "kunde": {"name": "Acme GmbH", "tagline": "Wir sind innovativ"},
        "teaser_bullets": ["Mehr Erfolg", "innovative Methode"],
    })]
    warnings = validate_copy(pages)
    buzz_fields = {w.field_name for w in warnings if w.rule == "buzzword_denylist"}
    assert "kunde.tagline" in buzz_fields, (
        f"walker should descend into kunde.tagline; got fields={buzz_fields}"
    )
    assert any(f.startswith("teaser_bullets[") for f in buzz_fields), (
        f"walker should descend into teaser_bullets[*]; got {buzz_fields}"
    )


def test_endlich_as_opener_is_verboten() -> None:
    """`Endlich` as the first word of a field opens a forbidden lead."""
    pages = [_page(1, "ST-01", {"title": "Endlich messbare Ergebnisse."})]
    warnings = validate_copy(pages)
    assert any(w.rule == "verboten_opening" for w in warnings)


def test_passive_voice_flagged() -> None:
    """German passive (wird/wurde/werden + past participle) is flagged."""
    pages = [_page(2, "ST-02", {
        "body": "Die Strategie wird von unserem Team entwickelt und getestet.",
    })]
    warnings = validate_copy(pages)
    passive = [w for w in warnings if w.rule == "passive_voice"]
    assert len(passive) >= 1, f"expected passive-voice warning; got {warnings}"


def test_pydantic_pages_accepted() -> None:
    """The validator accepts Pydantic ReportPage objects (not just dicts)."""
    from models import ReportPage
    pages = [
        ReportPage(slot=1, type="ST-01",
                   data={"title": "Wir bieten innovative Lösungen."}),
    ]
    warnings = validate_copy(pages)
    assert any(w.rule == "buzzword_denylist" for w in warnings)
