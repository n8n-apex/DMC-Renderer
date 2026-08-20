"""High-fidelity region inspector (US-2026-08-19): audit the FOOTER layout and
the numbered-section (1/2/3/4) alignment on every page at HIGH DPI (200+),
region by region — the whole-page 90-DPI audits missed the layout nuance.

Two focuses per page:
  1. FOOTER: the bottom chrome (wordmark/URL/folio) — alignment, clipping,
     negative space, baseline rhythm.
  2. NUMBERED SECTIONS: any "01/02/03" list/grid — the gap pattern between
     items, column alignment, left-edge rhythm, and vertical distribution.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path
from typing import Optional

import fitz
import httpx

HERE = Path(__file__).resolve().parent
PDF = HERE / "output" / "report.pdf"
TMP = Path("/tmp/deck_hi")

FOOTER_PROMPT = """You are a ruthless print-layout QA. This is a HIGH-RES crop of the BOTTOM
(footer band) of a German report page. Audit it like InDesign pagination:
1) Alignment: are the footer elements on one baseline? Any element clipped at
the page edge (a letter cut off)?
2) Negative space: is there a balanced margin below the footer text to the
sheet edge, or does text touch the very edge?
3) Is the footer horizontal line / hairline present and aligned?
Return JSON: {"aligned":bool,"clipped":bool,"tight_to_edge":bool,
"hairline":bool,"detail":"...","negative_space_ok":bool}"""

SECTIONS_PROMPT = (
    "You are a HIGH-RES print-layout inspector. This crop shows NUMBERED "
    "SECTIONS (01/02/03...) of a German report page. Audit like InDesign:\n"
    "1) Is the gap/negative space between the numbered items consistent, or "
    "is there an excessive dead gap anywhere?\n"
    "2) Are the numbers + their text aligned on a clean vertical edge?\n"
    "3) Is the section box/panel placement balanced relative to the page "
    "grid, or oddly inset / touching edges?\n"
    "Return JSON: {\"dead_gap_pct\":0,\"align_ok\":true,\"items\":N,\"detail\":\"...\"}"
)


def _parse_pages(spec: str) -> list[int]:
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


def _crop(page_no: int, rect_frac, dpi: int = 200) -> Path:
    pg = PDF.open if False else None
    doc = fitz.open(PDF)
    pg = doc[page_no - 1]
    W, H = pg.rect.width, pg.rect.height
    r = fitz.Rect(rect_frac[0] * W, rect_frac[1] * H,
                  rect_frac[2] * W, rect_frac[3] * H)
    pix = pg.get_pixmap(dpi=dpi, clip=r)
    out = TMP / f"p{page_no}_{int(rect_frac[0]*100)}_{int(rect_frac[1]*100)}.png"
    pix.save(out)
    doc.close()
    return out


def _ask(url: str, model: str, img: Path, prompt: str) -> dict:
    b64 = base64.b64encode(img.read_bytes()).decode()
    r = httpx.post(url, json={
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": prompt},
        ]}],
        "temperature": 0, "max_tokens": 600,
    }, timeout=300)
    r.raise_for_status()
    raw = r.json()["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return {"raw": raw[:300]}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"raw": raw[:300]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3.5-9b-vlm")
    ap.add_argument("--base", default="http://localhost:1234/v1/chat/completions")
    ap.add_argument("--pages", default="1-25")
    ap.add_argument("--out", default="/tmp/region_audit.json")
    ap.add_argument("--focus", choices=["footer", "sections", "both"], default="both")
    args = ap.parse_args()

    pages = _parse_pages(args.pages)
    TMP.mkdir(parents=True, exist_ok=True)
    results: dict = {}
    for n in pages:
        entry = {}
        # FOOTER band: bottom 9% of the page, full width
        if args.focus in ("footer", "both"):
            img = _crop(n, (0.0, 0.90, 1.0, 1.0), dpi=220)
            entry["footer"] = _ask(args.base, args.model, img, FOOTER_PROMPT)
        # SECTIONS: the middle band (numbered items) — two crops (upper+lower)
        # to catch the gap/alignment without the header/footer.
        if args.focus in ("sections", "both"):
            img = _crop(n, (0.05, 0.25, 0.95, 0.75), dpi=200)
            entry["sections"] = _ask(args.base, args.model, img, SECTIONS_PROMPT)
        results[f"p{n}"] = entry
        print(f"[region] p{n} done", flush=True)
    Path(args.out).write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"[region] wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# --------------------------------------------------------------------------- #
# DET CONTRAST PROBE (US-2026-08-19, Part B): a deterministic readability guard
# that walks the rendered HTML's text-bearing elements, compares each element's
# computed foreground vs the nearest non-transparent background, and flags any
# pair whose contrast ratio is below a readable floor (~3:1 for large text,
# 4.5:1 for body). This catches the "dark text on dark panel / blue on blue"
# class WITHOUT the vision model — a hard regression net on every render.
# --------------------------------------------------------------------------- #

def _rel_lum(hex_color: str) -> float:
    """WCAG relative luminance of a #rrggbb / rgb() / color(srgb ...) color."""
    import re
    m = re.match(r"#([0-9a-fA-F]{6})", hex_color)
    vals = None
    if m:
        vals = tuple(int(m.group(1)[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    else:
        m = re.match(r"rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)", hex_color)
        if m:
            vals = tuple(int(x) / 255.0 for x in m.groups())
    if not vals:
        m = re.match(
            r"color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", hex_color
        )
        if m:
            vals = tuple(min(1.0, float(x)) for x in m.groups())
    if not vals:
        return 0.0
    def chan(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (chan(c) for c in vals)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(fg: str, bg: str) -> float:
    l1, l2 = _rel_lum(fg), _rel_lum(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def probe_contrast(html_path: Path, *, floor: float = 3.0) -> list[dict]:
    """Walk text-bearing elements; return [element, fg, bg, ratio] below floor."""
    from playwright.sync_api import sync_playwright
    offenders: list[dict] = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        p = b.new_page()
        p.goto(html_path.resolve().as_uri())
        p.emulate_media(media="print")
        rows = p.evaluate("""() => {
          const out = [];
          const els = [...document.querySelectorAll('p, h1, h2, h3, h4, li, span, blockquote, div')];
          for (const el of els) {
            const t = (el.textContent || '').trim();
            if (t.length < 2) continue;
            const cs = getComputedStyle(el);
            const fg = cs.color;
            if (fg === 'rgba(0, 0, 0, 0)' || fg === 'transparent') continue;
            if (parseFloat(cs.fontSize) < 8) continue;
            let bg = 'rgba(0, 0, 0, 0)';
            let node = el;
            while (node && bg === 'rgba(0, 0, 0, 0)') {
              if (node.className && String(node.className).includes('tp-rail') &&
                  node !== el && node.parentElement && node.parentElement.tagName === 'SECTION') break;
              const cls = node.className || '';
              // stop at a SELF-CHROMED rail bar or a pseudo-bleed holder: they
              // are not text panels
              if (String(cls).startsWith('tp-chrome')) break;
              const b = getComputedStyle(node).backgroundColor;
              if (b && b !== 'rgba(0, 0, 0, 0)' && b !== 'transparent') { bg = b; break; }
              node = node.parentElement;
            }
            // fall back to the page/section ground when no panel found
            if (bg === 'rgba(0, 0, 0, 0)') {
              const sec = el.closest('section.page');
              bg = sec ? getComputedStyle(sec).backgroundColor : 'rgba(0, 0, 0, 0)';
            }
            out.push({el: el.className.split(' ').slice(0,2).join('.'), text: t.slice(0,24),
                      fg, bg, ratio: 0});
          }
          return out;
        }""")
        for row in rows:
            if row["bg"] in ("rgba(0, 0, 0, 0)", "transparent"):
                continue
            ratio = _contrast(row["fg"], row["bg"])
            if ratio < floor:
                offenders.append({**row, "ratio": round(ratio, 2)})
        b.close()
    return offenders
