"""Tests for references/classify.py (deterministic text-layer classifier).

The classifier is now PURE + DETERMINISTIC + FREE: it reads each reference
PDF's text layer (via PyMuPDF) and tags pages by their German content kickers
(e.g. "FALLSTUDIE" => case study). No vision model, no network.

The real index.json is NEVER clobbered here -- the build runs against a
tmp_path COPY.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from references.classify import (
    build_st_type_index,
    classify_page_text,
    CANDIDATE_ST_TYPES,
)
from references import retrieve_references


HERE = Path(__file__).resolve().parent
REAL_INDEX = HERE.parent / "references" / "index.json"


def test_classify_page_text_rules() -> None:
    """The pure rule function returns the right st_type per priority order."""
    # Rule 1: page 1 is always the cover, regardless of content.
    assert classify_page_text("FALLSTUDIE anything here", page_no=1) == "ST-01"
    assert classify_page_text("Lorem ipsum cover blurb", page_no=1) == "ST-01"

    # Rule 2: a real case-study page (FALLSTUDIE + section kickers, page != 1).
    case_text = "FALLSTUDIE\nAUSGANGSSITUATION ... ZIEL ... UMSETZUNG ... ERGEBNIS ..."
    assert classify_page_text(case_text, page_no=8) == "ST-07A"

    # Rule 3: about page.
    assert classify_page_text("ÜBER UNS\nWir sind ...", page_no=4) == "ST-05"
    assert classify_page_text("DIE AUTOREN\n...", page_no=4) == "ST-05"

    # Rule 4: fazit / conclusion.
    assert classify_page_text("FAZIT\nZusammenfassend ...", page_no=9) == "ST-FAZIT"

    # Rule 6: generic content falls through to OTHER.
    assert classify_page_text("Lorem ipsum dolor sit amet", page_no=3) == "OTHER"

    # Whatever the function emits must be a documented candidate.
    for txt, pno in [
        ("FALLSTUDIE\nAUSGANGSSITUATION ZIEL", 8),
        ("ÜBER UNS", 4),
        ("FAZIT", 9),
        ("BEKANNT AUS", 2),
        ("nothing", 3),
        ("cover", 1),
    ]:
        assert classify_page_text(txt, page_no=pno) in CANDIDATE_ST_TYPES


def test_build_index_finds_case_studies_in_every_deck(tmp_path: Path) -> None:
    """Building against a COPY tags real case studies across multiple decks."""
    copy = tmp_path / "index.json"
    shutil.copy(REAL_INDEX, copy)

    summary = build_st_type_index(index_path=str(copy))
    assert isinstance(summary, dict)
    assert summary.get("ST-07A", 0) >= 1

    hits = retrieve_references("ST-07A", axes={}, k=20, index_path=str(copy))
    decks = {h["deck"] for h in hits}
    # Case studies must now span AT LEAST these four decks.
    for required in ("niklas", "boss", "buchagentur", "werkzeugkoffer"):
        assert required in decks, f"{required} missing from ST-07A decks: {decks}"
    assert len(decks) >= 4

    def pages(deck: str) -> set[int]:
        return {h["page_no"] for h in hits if h["deck"] == deck}

    assert pages("niklas") == {8, 10, 12}
    assert {5, 6, 7}.issubset(pages("boss"))


def test_no_page_one_is_case_study(tmp_path: Path) -> None:
    """Page 1 (cover/agenda) must never be tagged as a case study."""
    copy = tmp_path / "index.json"
    shutil.copy(REAL_INDEX, copy)

    build_st_type_index(index_path=str(copy))

    rows = json.loads(copy.read_text())
    offenders = [
        (r["deck"], r["page_no"])
        for r in rows
        if r["page_no"] == 1 and r["st_type"] == "ST-07A"
    ]
    assert not offenders, f"page 1 tagged as case study: {offenders}"
