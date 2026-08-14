"""Deterministic text-layer page-type classification for reference decks.

This module replaces the old vision-based classifier. The reference PDFs all
carry a real text layer, and this report genre uses stable German *content*
kickers (e.g. "FALLSTUDIE" for a case study, "FAZIT" for a conclusion). Those
are document-structure labels, not client identity, so we encode them directly.

The result is pure, deterministic and free: no vision model, no network.

`classify_page_text` is a pure function (text + 1-based page_no -> st_type).
`build_st_type_index` opens each deck's source PDF, classifies every page from
its extracted text, and writes the labels back into `references/index.json`.

The previous vision entry point (`classify_st_type`) still lives in
`vis_client`; this module no longer depends on any vision client.
"""
from __future__ import annotations

import collections
import json
import os
import re

import fitz  # PyMuPDF

from .decks import DECKS, REPO_ROOT

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(HERE, "index.json")


# The documented, closed set of possible classifier outputs.
# 2026-07-13 (H4): broadened from 6 to 11 labels. The old set left 54 of 84
# reference pages as OTHER, and retrieve_references matches on EXACT st_type,
# so generated ST-02/ST-06/ST-14/ST-22/ST-03 pages had ZERO same-type Richard
# references: the reference-grounded QC comparison was unwired for most page
# types. Every new rule below is grounded in a kicker VERIFIED present in the
# reference corpus (refs/*.pdf text layers), never guessed. ST-09/ST-07B still
# have no stable kicker in the corpus and remain unclassified (OTHER).
CANDIDATE_ST_TYPES: list[str] = [
    "ST-01",      # cover (page 1)
    "ST-02",      # outlook ("Ausblick")
    "ST-05",      # about / "Über uns" / "Die Autoren"
    "ST-06",      # mechanism ("Mechanismus")
    "ST-07A",     # case study ("Fallstudie")
    "ST-14",      # false beliefs ("Irrglauben" / "Denkfehler" / "falsche Annahmen")
    "ST-22",      # collaboration ("Zusammenarbeit")
    "ST-03",      # CTA ("Erstgespräch sichern" / "Termin vereinbaren")
    "ST-FAZIT",   # conclusion ("Fazit")
    "LOGO-WALL",  # social proof ("Bekannt aus" / "setzen bereits auf")
    "OTHER",      # everything else
]

# Section kickers that distinguish a *real* case-study page from a one-line
# agenda/contents mention of the word "Fallstudie". A real case page carries
# one of these as a whole WORD somewhere in its text layer; an agenda/TOC page
# mentions "Fallstudie" in a list but has no section kicker. (The old fallback
# arm, "any mention + >200 chars of text", fired on exactly those agenda/TOC
# pages and is gone. The kickers are NOT restricted to the heading zone here:
# the reference PDFs are A3 spreads whose text layers put the section kickers
# 500-4000 chars in, so a heading-zone restriction loses 9 of the 16 real case
# pages, measured on the corpus.)
_CASE_STUDY_KICKERS: tuple[str, ...] = (
    "AUSGANGSSITUATION",
    "AUSGANGSLAGE",
    "ZIEL",
    "LÖSUNG",
    "LOESUNG",
    "UMSETZUNG",
    "ERGEBNIS",
)

# "About us" kickers.
_ABOUT_KICKERS: tuple[str, ...] = (
    "ÜBER UNS",
    "UEBER UNS",
    "DIE AUTOREN",
    "WER WIR SIND",
    "ÜBER MICH",
)

# H4 kickers (each VERIFIED in the reference corpus; see the deck + page in
# the trailing comment). Checked AFTER the original rules so existing labels
# are unchanged; a page matching none of these stays OTHER (honest fallback).
_FALSE_BELIEF_KICKERS: tuple[str, ...] = (
    "IRRGLAUBEN",        # buchagentur p4 "Die 7 fatalen Buch-Irrglauben"
    "IRRGLAUBE",
    "DENKFEHLER",
    "IRRTÜMER",
    "IRRTUEMER",
    "FALSCHER ANNAHMEN",  # alexander_boss p3 "wegen falscher Annahmen"
    "FALSCHE ANNAHMEN",
)
_MECHANISM_KICKERS: tuple[str, ...] = (
    "MECHANISMUS",       # buchagentur p9 "Einzigartiger Mechanismus"
)
_COLLAB_KICKERS: tuple[str, ...] = (
    "ZUSAMMENARBEIT",    # buchagentur p10 / niklas p18 "So läuft die Zusammenarbeit"
)
_OUTLOOK_KICKERS: tuple[str, ...] = (
    "AUSBLICK",          # niklas p2 "Ein kurzer AUSBLICK"
)
# CTA: the strong IMPERATIVE forms only. The bare word "Erstgespräch" appears
# in a running FOOTER on every aerztepartner page ("Buchen Sie jetzt Ihr
# kostenloses Erstgespräch auf: ...") and would mislabel whole decks as CTA.
_CTA_KICKERS: tuple[str, ...] = (
    "ERSTGESPRÄCH SICHERN",   # alexander_boss p10
    "ERSTGESPRAECH SICHERN",
    "TERMIN VEREINBAREN",
    "GESPRÄCH VEREINBAREN",
    "GESPRAECH VEREINBAREN",
)
_LOGO_WALL_EXTRA_KICKERS: tuple[str, ...] = (
    "SETZEN BEREITS AUF",     # niklas p19 "Diese ... Betriebe setzen bereits auf"
)


def _has_kicker(zone: str, kickers: tuple[str, ...]) -> bool:
    """True iff one of `kickers` occurs in `zone` as a whole WORD.

    Word-boundary matching so a short kicker never fires on a derived word:
    "ZIEL" must not match "ZIELGRUPPE" or "ERZIELEN", "FAZIT" must not match
    inside a compound. Multi-word kickers ("FALSCHE ANNAHMEN") match verbatim
    between boundaries. Pure and deterministic (re caches the patterns).
    """
    return any(re.search(r"\b" + re.escape(k) + r"\b", zone) for k in kickers)


def classify_page_text(text: str, page_no: int) -> str:
    """Return an st_type for a page given its extracted text + 1-based page_no.

    Rules, checked in priority order (case-insensitive; hyphen-linebreaks are
    joined first so "Zusam-\\nmenarbeit" matches "ZUSAMMENARBEIT"; every kicker
    matches as a whole WORD, see _has_kicker; "heading zone" = the first ~300
    chars of the text layer, where true kickers sit at char 13-17 and prose
    mentions at 1020+, measured):
      1. page_no == 1                          -> "ST-01"   (cover)
      2. "FALLSTUDIE" anywhere + a case-study  -> "ST-07A"  (case study)
         section kicker as a whole word (an agenda/TOC page mentions the word
         but carries no section kicker; the old ">200 chars" arm fired there)
      3. an about-us kicker                    -> "ST-05"   (about)
      4. "FAZIT" in the heading zone           -> "ST-FAZIT"
      5. "BEKANNT AUS" / "SETZEN BEREITS AUF"  -> "LOGO-WALL"
      6. a false-belief kicker                 -> "ST-14"
      7. a mechanism kicker (heading zone)     -> "ST-06"
      8. a collaboration kicker (heading zone) -> "ST-22"
      9. an outlook kicker (heading zone)      -> "ST-02"
     10. a strong CTA imperative               -> "ST-03"
     11. otherwise                             -> "OTHER"
    """
    if page_no == 1:
        return "ST-01"

    # join hyphenated linebreaks so a kicker split across lines still matches
    # (niklas p18 carries "Zusam-\nmenarbeit" in its text layer).
    joined = (text or "").replace("-\n", "")
    up = joined.upper()
    head = up[:300]

    if "FALLSTUDIE" in up and _has_kicker(up, _CASE_STUDY_KICKERS):
        return "ST-07A"

    if _has_kicker(up, _ABOUT_KICKERS):
        return "ST-05"

    # like MECHANISMUS below: "Fazit" also occurs mid-PROSE on other page
    # types, so the conclusion label keys on the HEADING ZONE only.
    if _has_kicker(head, ("FAZIT",)):
        return "ST-FAZIT"

    if _has_kicker(up, ("BEKANNT AUS",) + _LOGO_WALL_EXTRA_KICKERS):
        return "LOGO-WALL"

    if _has_kicker(up, _FALSE_BELIEF_KICKERS):
        return "ST-14"

    # MECHANISMUS / ZUSAMMENARBEIT / AUSBLICK also occur mid-PROSE on other
    # page types (measured: true headings sit at char 13-17 of the text layer,
    # prose mentions at 1020+), so these three match only in the HEADING ZONE.
    if _has_kicker(head, _MECHANISM_KICKERS):
        return "ST-06"

    if _has_kicker(head, _COLLAB_KICKERS):
        return "ST-22"

    if _has_kicker(head, _OUTLOOK_KICKERS):
        return "ST-02"

    if _has_kicker(up, _CTA_KICKERS):
        return "ST-03"

    return "OTHER"


# HUMAN-VERIFIED page labels for types with NO stable text kicker (ST-09 status
# quo, ST-07B theory) plus genre-blend closers. Each entry was labeled by
# READING the page (2026-07-13); the quoted opening line is the evidence. These
# override the keyword rules (ground truth beats heuristics).
_MANUAL_LABELS: dict[tuple[str, int], str] = {
    # "Statusluecke ... Nach aussen laeuft es ... Genau deshalb ist deine
    # Situation so gefaehrlich" - the quiet-failure-under-visible-success page.
    ("buchagentur", 3): "ST-09",
    # "Du hast in diesem Report gelernt ..." - the recap/summary closer.
    ("buchagentur", 11): "ST-FAZIT",
    # Principle pages, each stating and arguing ONE thesis:
    # "Sichtbarkeit ist kein Trend. Sichtbarkeit ist Kontrolle."
    ("niklas", 7): "ST-07B",
    # "Gute Mitarbeiter entscheiden sich nicht wegen ... sondern wegen Vertrauen"
    ("niklas", 9): "ST-07B",
    # "Ein klarer, moderner Auftritt sendet ein eindeutiges Signal"
    ("niklas", 11): "ST-07B",
    # "Nicht die Anzahl der Anfragen entscheidet ... sondern ihre Qualitaet"
    ("niklas", 13): "ST-07B",
    # "Ist dein Betrieb DER Betrieb ...? ... Genau das setzt die NMR ..." - back-cover ask.
    ("niklas", 20): "ST-03",
    # "Wenn Sie diesen Report in den Haenden halten, haben Sie bereits
    # Grossartiges geleistet ... Aber trotzdem spueren Sie" - the credit-then-turn opener.
    ("boss", 2): "ST-02",
    # "DIE UNSICHTBARE GEWINNLAWINE: Warum Personal der Tueroeffner ... ist" - the principle spread.
    ("boss", 4): "ST-07B",
    # "Haben Sie noch Fragen? ... 'Warum sollte das ausgerechnet bei uns
    # funktionieren?'" - objections quoted + answered (the false-beliefs genre).
    ("boss", 8): "ST-14",
    # "Finden Sie jetzt heraus, wo Ihr System bereits heute still Geld ...
    # verliert" - the closing ask.
    ("aerztepartner", 11): "ST-03",
}


def build_st_type_index(index_path: str = INDEX_PATH) -> dict[str, int]:
    """Re-tag every index row from its deck's PDF text layer; return a summary.

    For each deck in ``DECKS``, open ``REPO_ROOT/pdf_filename``, extract each
    page's text, classify it, and overwrite ``st_type`` on the matching index
    row (matched on ``deck`` + 1-based ``page_no``). Logs every
    ``deck pN -> st_type`` and returns a ``{st_type: count}`` summary over the
    rows that were updated. Idempotent: re-running produces the same labels.

    Label precedence per page: (1) a deck marked ``machine_generated`` in DECKS
    is ALWAYS "OTHER" (the apex deck is pipeline OUTPUT, not Richard's hand -
    retrieval must never anchor a comparison on machine output, not even its
    cover); (2) a human-verified ``_MANUAL_LABELS`` entry; (3) the keyword rules.
    """
    with open(index_path) as f:
        rows = json.load(f)

    # Index rows for O(1) lookup by (deck, page_no).
    by_key: dict[tuple[str, int], dict] = {
        (row["deck"], row["page_no"]): row for row in rows
    }

    summary: collections.Counter[str] = collections.Counter()

    for deck in DECKS:
        deck_id = deck["deck_id"]
        pdf_path = os.path.join(REPO_ROOT, deck["pdf_filename"])
        machine = bool(deck.get("machine_generated"))
        doc = fitz.open(pdf_path)
        try:
            for i in range(doc.page_count):
                page_no = i + 1  # 1-based
                text = doc[i].get_text()
                if machine:
                    st_type = "OTHER"
                elif (deck_id, page_no) in _MANUAL_LABELS:
                    st_type = _MANUAL_LABELS[(deck_id, page_no)]
                else:
                    st_type = classify_page_text(text, page_no)
                print(f"{deck_id} p{page_no} -> {st_type}")
                row = by_key.get((deck_id, page_no))
                if row is not None:
                    row["st_type"] = st_type
                    summary[st_type] += 1
        finally:
            doc.close()

    with open(index_path, "w") as f:
        json.dump(rows, f, indent=2)

    return dict(summary)
