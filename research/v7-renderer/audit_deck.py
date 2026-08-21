"""Local-vision deck auditor: rasterize each PDF page and ask a LOCAL
LM Studio / Ollama vision model for a structured defect readout.

No OpenRouter, no credits, no cloud. The vision model runs on the user's
machine (LM Studio OpenAI-compatible endpoint at :1234, or Ollama :11434).

Usage:
  python audit_deck.py [--base http://localhost:1234/v1] [--model qwen2.5-vl]
                       [--pages 1-25] [--out /tmp/deck_audit.json]
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

import httpx
import fitz  # PyMuPDF


HERE = Path(__file__).resolve().parent
PDF = HERE / "output" / "report.pdf"
TMP = Path("/tmp/deck_audit")

PROMPT = """You are a ruthless print-design QA reviewer. Look at this page of a German
B2B marketing report. List concrete VISUAL defects only (what is actually
wrong on the page), in this JSON shape:

{
  "defects": [
    {"zone": "top/middle/bottom/left/right/rail/stat/photo",
     "severity": "critical|major|minor",
     "description": "specific, in plain English, what is wrong (overlap,
        clipping, dead whitespace, broken stat, missing image, ghost numeral
        on text, text too close to edge, layout imbalance)"}
  ],
  "dead_space_percent": 0-100,
  "has_photo_or_scene": true/false,
  "one_line_verdict": "honest summary"
}

Rules:
- ONLY report defects you can actually SEE. If the page looks clean, say so.
- Quote any text you can read verbatim (especially numbers/percentages).
- If the bottom quarter is empty white/near-empty, that IS a defect.
- If a huge ghost numeral overlaps body copy, that IS a defect.
- If an image band is missing/blank where one should be, that IS a defect.
Return ONLY the JSON, no markdown fences."""


def rasterize(page_no: int, dpi: int = 160) -> Path:
    TMP.mkdir(parents=True, exist_ok=True)
    out = TMP / f"p{page_no}.png"
    # STALE-CACHE GUARD (2026-08-19): the cache used to return an OLD raster
    # after a re-render, so every "re-audit" read the previous deck and the
    # fixes looked like they did nothing. Re-rasterize whenever the source PDF
    # is newer than the cached PNG.
    if out.exists() and out.stat().st_mtime >= PDF.stat().st_mtime:
        return out
    doc = fitz.open(PDF)
    pix = doc[page_no - 1].get_pixmap(dpi=dpi)
    pix.save(out)
    doc.close()
    return out


def _b64(png: Path) -> str:
    return base64.b64encode(png.read_bytes()).decode()


def audit_page(client: httpx.Client, base: str, model: str, page_no: int,
               ref_png: Path | None = None) -> dict:
    png = rasterize(page_no)
    content: list = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{_b64(png)}"},
        },
        {"type": "text", "text": PROMPT},
    ]
    if ref_png and ref_png.exists():
        content.insert(0, {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{_b64(ref_png)}"},
        })
        content.insert(1, {
            "type": "text",
            "text": "This is the GOLD-STANDARD reference page (Richard's design). Compare.",
        })
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0,
        "max_tokens": 800,
    }
    # LM Studio / Metal can transiently OOM on long runs ("Compute error",
    # kIOGPUCommandBufferCallbackErrorOutOfMemory). One retry after a pause
    # recovers most transient failures; a persistent failure surfaces loudly.
    for attempt in (1, 2):
        try:
            r = client.post(f"{base}/chat/completions", json=payload, timeout=300)
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"]
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"defects": [], "one_line_verdict": f"PARSE_FAIL: {raw[:200]}"}
        except Exception as exc:  # noqa: BLE001 -- retry once, then surface
            if attempt == 1 and "compute error" in str(exc).lower():
                import time
                time.sleep(20)
                continue
            return {"defects": [], "one_line_verdict": f"ERROR: {exc}"}
    return {"defects": [], "one_line_verdict": "ERROR: retries exhausted"}


def _parse_pages(spec: str) -> list[int]:
    """'1-25' or '10,12,15,17-18' -> sorted unique page numbers."""
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = (int(x) for x in part.split("-", 1))
            out.update(range(a, b + 1))
        else:
            out.add(int(part))
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:1234/v1")
    ap.add_argument("--model", default="qwen2.5-vl-7b-instruct")
    ap.add_argument("--pages", default="1-25")
    ap.add_argument("--out", default="/tmp/deck_audit.json")
    ap.add_argument("--ref", default="")
    args = ap.parse_args()

    pages = _parse_pages(args.pages)
    refs = {int(p.split(":")[0]): Path(p.split(":", 1)[1]) for p in args.ref.split(",") if ":" in p} if args.ref else {}

    results: dict[str, dict] = {}
    with httpx.Client() as client:
        for n in pages:
            print(f"[audit] page {n} ...", flush=True)
            try:
                results[f"p{n}"] = audit_page(
                    client, args.base, args.model, n, refs.get(n))
            except Exception as exc:
                results[f"p{n}"] = {"defects": [], "one_line_verdict": f"ERROR: {exc}"}
    Path(args.out).write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"[audit] wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
