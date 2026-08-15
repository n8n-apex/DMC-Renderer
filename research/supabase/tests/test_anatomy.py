"""US-404: deterministic anatomy verification for reference faces.

The atlas role/mechanism/devices metadata is stale (built from an older deck
layout). The Director contract forbids stale anatomy from driving generation,
so anatomy is re-derived from the face's ACTUAL page text and persisted.
These tests pin the determinism and the no-fabrication rule.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from catalog import verify_face_anatomy  # noqa: E402


def test_case_study_page_classified_as_proof() -> None:
    text = (
        "Fallstudie 3\nVon 24-Stunden-Reaktionszeit zu Minuten\n\n"
        "Vorher: bis zu 24 Stunden Antwortzeit. Nachher: 2 Minuten. "
        "Die Einsparung beträgt über 200.000 € pro Jahr."
    )
    a = verify_face_anatomy(text)
    assert a["role"] == "case_study"
    assert a["mechanism"] == "case_study_proof"
    assert "money_stat" in a["devices"]
    assert "before_after_transform" in a["devices"]
    assert a["argument"].startswith("Fallstudie 3")


def test_misconception_page_not_misread_as_case_study() -> None:
    text = (
        "Die 7 fatalen Buch-Irrglauben\n"
        "Mythos 1: Mehr Mitarbeiter lösen das Problem. Falsch."
    )
    a = verify_face_anatomy(text)
    assert a["mechanism"] == "misconception_sequence"
    assert a["role"] == "false_beliefs"


def test_empty_text_yields_no_fabricated_anatomy() -> None:
    a = verify_face_anatomy("")
    assert a["mechanism"] == "editorial"
    assert a["devices"] == ""
    assert a["argument"] == ""
