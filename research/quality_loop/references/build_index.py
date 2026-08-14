"""Build the reference library from ALL of Richard's reference decks.

Rasterizes every page of each deck PDF to PNG at 150 dpi and writes a combined
index.json describing each page (deck, page_no, st_type, axes, png_path). Each
row is tagged with its deck's per-client axes (categorical labels from the
design DNA), so retrieval can pull same-page-type references from MULTIPLE
decks and stay brand-agnostic.

Niklas pages have known st_type identifications (ST_TYPE_MAP); the other five
decks get st_type=None for now (a later task auto-classifies them).

Run once to (re)generate the PNGs + index (idempotent — overwrites cleanly):
    PYTHONPATH=. python references/build_index.py
"""
import json
import os

import fitz

from decks import DECKS, REPO_ROOT

HERE = os.path.dirname(os.path.abspath(__file__))

PAGES_ROOT = os.path.join(HERE, "pages")
INDEX_PATH = os.path.join(HERE, "index.json")

# GIVEN page -> st_type map for the Niklas deck. Pages not listed -> None.
ST_TYPE_MAP = {
    1: "ST-01",
    2: "ST-05",
    8: "ST-07A",
    10: "ST-07A",
    12: "ST-07A",
    16: "ST-FAZIT",
    19: "LOGO-WALL",
    20: "ST-03",
}

DPI = 150


def _build_deck(deck, matrix):
    deck_id = deck["deck_id"]
    pdf_path = os.path.join(REPO_ROOT, deck["pdf_filename"])
    pages_dir = os.path.join(PAGES_ROOT, deck_id)
    os.makedirs(pages_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    rows = []
    for i, page in enumerate(doc):
        page_no = i + 1  # 1-based
        pix = page.get_pixmap(matrix=matrix)
        png_abs = os.path.join(pages_dir, f"p{page_no}.png")
        pix.save(png_abs)

        st_type = ST_TYPE_MAP.get(page_no) if deck_id == "niklas" else None
        rel_png = os.path.relpath(png_abs, HERE)  # relative to references/
        rows.append({
            "deck": deck_id,
            "page_no": page_no,
            "st_type": st_type,
            "axes": dict(deck["axes"]),
            "png_path": os.path.join("references", rel_png),
        })
    doc.close()
    return rows


def build_index(decks=DECKS, index_path=INDEX_PATH):
    matrix = fitz.Matrix(DPI / 72, DPI / 72)

    rows = []
    for deck in decks:
        rows.extend(_build_deck(deck, matrix))

    with open(index_path, "w") as f:
        json.dump(rows, f, indent=2)

    return rows


if __name__ == "__main__":
    rows = build_index()
    print(f"Wrote {len(rows)} rows to {INDEX_PATH}")
    by_deck = {}
    for r in rows:
        by_deck[r["deck"]] = by_deck.get(r["deck"], 0) + 1
    for deck_id, n in by_deck.items():
        print(f"  {deck_id}: {n} pages")
