"""Live grader smoke check (Phase 1, Task 1.3).

NOT a pytest test: this makes a small number of LIVE, paid OpenRouter vision
calls (cached on disk after the first run). It proves the reference-grounded
grader actually works before we trust it in the loop:

  1. WELL-FORMED: ``score_page`` returns ``{row_id: {"score": int, "rationale": str}}``.
  2. DISCRIMINATION: a real Richard reference page (which DOES exhibit the
     positive trait) scores strictly higher on a positive row than a blank page
     (which does not). If the grader cannot tell those apart, the model/prompt is
     wrong and we stop before relying on it.

The key + model + endpoint are read from research/preprocessor/.env by the
client (never printed here). Run with the renderer venv:

    PYTHONPATH=<quality_loop> <venv>/bin/python tools/grader_smoke.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

QL_ROOT = Path(__file__).resolve().parent.parent  # .../quality_loop
if str(QL_ROOT) not in sys.path:
    sys.path.insert(0, str(QL_ROOT))

from vis_client import VisionClient  # noqa: E402

# Positive rows that a real page exhibits and a blank page does not. P01
# (founder-as-hero) is reliably present on a cover; P07 (social-proof) is
# printed for context but not asserted on (covers may lack it).
POSITIVE_ROW = "P01"
ROWS = ["P01", "P07"]
TARGET_TYPE = "ST-01"  # cover: every deck has one at page 1, strong founder hero


def _resolve(png_path: str) -> str:
    """index.json stores paths relative to the quality_loop root."""
    return str((QL_ROOT / png_path).resolve())


def _pick_pages() -> tuple[str, list[str]]:
    """Return (good_page_png, reference_pngs) for the target page type.

    Good page: an apex example of TARGET_TYPE. References: up to two examples
    of the same type from OTHER decks (composition grounded across clients).
    """
    index = json.loads((QL_ROOT / "references" / "index.json").read_text("utf-8"))
    examples = [e for e in index if e.get("st_type") == TARGET_TYPE]
    if not examples:
        raise SystemExit(f"no reference pages of type {TARGET_TYPE} in index.json")
    good = next((e for e in examples if e["deck"] == "apex"), examples[0])
    refs = [e for e in examples if e["deck"] != good["deck"]][:2]
    if not refs:
        refs = [e for e in examples if e is not good][:2]
    return _resolve(good["png_path"]), [_resolve(e["png_path"]) for e in refs]


def _blank_page() -> str:
    from PIL import Image

    p = Path(tempfile.gettempdir()) / "grader_smoke_blank.png"
    Image.new("RGB", (1240, 1754), "white").save(p)  # A4 @ ~150dpi, empty
    return str(p)


def _score_of(result: dict, row: str) -> int:
    entry = result.get(row)
    return int(entry["score"]) if isinstance(entry, dict) and "score" in entry else 0


def _well_formed(result: dict, rows: list[str]) -> bool:
    for rid, entry in result.items():
        if rid not in rows:
            return False
        if not isinstance(entry, dict) or not isinstance(entry.get("score"), int):
            return False
        if not isinstance(entry.get("rationale"), str):
            return False
    return True


def main() -> int:
    client = VisionClient()
    print(f"model={client.model}  endpoint={client._api_base}")

    good_png, ref_pngs = _pick_pages()
    blank_png = _blank_page()
    print(f"good={Path(good_png).name}  refs={[Path(r).name for r in ref_pngs]}")

    good = client.score_page(good_png, ref_pngs, ROWS)
    blank = client.score_page(blank_png, ref_pngs, ROWS)
    print("GOOD :", json.dumps(good, ensure_ascii=False))
    print("BLANK:", json.dumps(blank, ensure_ascii=False))

    ok_form = _well_formed(good, ROWS) and _well_formed(blank, ROWS)
    g, b = _score_of(good, POSITIVE_ROW), _score_of(blank, POSITIVE_ROW)
    ok_discriminate = g > b
    print(
        f"well_formed={ok_form}  {POSITIVE_ROW}: good={g} > blank={b} "
        f"-> discriminates={ok_discriminate}"
    )

    if ok_form and ok_discriminate:
        print("SMOKE PASS")
        return 0
    print("SMOKE FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
