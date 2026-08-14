import json
import os


def test_retrieve_returns_matching_st_type_sorted_by_axis_distance(tmp_path=None):
    from references import retrieve_references
    q_axes = {"headline_type":"serif","palette":"blue_cyan","accent_mechanic":"tonal",
              "texture":"smooth","density":"airy","qr_enabled":False}
    rows = retrieve_references("ST-07A", q_axes, k=3)
    assert 1 <= len(rows) <= 3
    assert all(r["st_type"] == "ST-07A" for r in rows)
    import os
    assert all(os.path.exists(os.path.join(os.path.dirname(__file__), "..", r["png_path"])) for r in rows)


HERE = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(HERE, "..", "references", "index.json")
REFERENCES_DIR = os.path.join(HERE, "..")


def _load_index():
    with open(INDEX_PATH) as f:
        return json.load(f)


def test_index_covers_all_six_decks():
    rows = _load_index()
    decks = {r["deck"] for r in rows}
    assert decks == {"apex", "niklas", "buchagentur", "boss", "werkzeugkoffer", "aerztepartner"}
    assert len(rows) > 60


def test_each_deck_axes_match_dna():
    rows = _load_index()

    werkzeug = [r for r in rows if r["deck"] == "werkzeugkoffer"]
    assert werkzeug
    assert all(r["axes"]["headline_type"] == "all_sans" for r in werkzeug)

    niklas = [r for r in rows if r["deck"] == "niklas"]
    assert niklas
    assert all(r["axes"]["qr_enabled"] is True for r in niklas)

    apex = [r for r in rows if r["deck"] == "apex"]
    assert apex
    assert all(r["axes"]["qr_enabled"] is False for r in apex)
    assert all(r["axes"]["accent_mechanic"] == "tonal" for r in apex)


def test_every_png_path_exists():
    rows = _load_index()
    for r in rows:
        full = os.path.join(REFERENCES_DIR, r["png_path"])
        assert os.path.exists(full), f"missing {r['png_path']}"


def test_retrieve_still_works_and_spans_decks():
    from references import retrieve_references
    q_axes = {"headline_type": "serif", "palette": "royal_blue_charcoal",
              "accent_mechanic": "contrasting", "texture": "darkened_photo",
              "density": "punchy_5050", "qr_enabled": True, "tone": "masculine_bold"}
    rows = retrieve_references("ST-07A", q_axes, k=3)
    assert 1 <= len(rows) <= 3
    assert all(r["st_type"] == "ST-07A" for r in rows)
