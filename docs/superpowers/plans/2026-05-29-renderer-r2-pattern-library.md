# Renderer R2 — Pattern Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full 12-pattern library so the renderer composes an apex report whose layout language matches the finished reference PDF — replacing R1's `_generic` skeleton for every ST type — while staying brand-agnostic and deterministic.

**Architecture:** Shared components (`patterns/_components.py`) + one `render(page, ctx) -> PageFragment` module per ST type, registered in `patterns/__init__.py`. Richness travels in each pattern's optional `data` contract (enriched in the apex fixture as DATA). Built + visually verified in 4 batches.

**Tech Stack:** Python 3.11, WeasyPrint, PyMuPDF (fitz), qrcode (renderer venv). Spec: `docs/superpowers/specs/2026-05-29-renderer-r2-pattern-library-design.md`.

---

## CRITICAL EXECUTION NOTES (read before starting)

1. **No git in this repo.** Never run git/commit. Each task's gate is pytest + (per batch) a visual-fidelity check.
2. **Renderer venv MUST be activated for WeasyPrint** (macOS Pango/GLib via `DYLD_FALLBACK_LIBRARY_PATH`): always run as
   `cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python …`
   Bare `.venv/bin/python` fails to import weasyprint.
3. **Baseline:** renderer `pytest tests/ -q` = 26 passed; pre-processor (separate venv, no activation) = 220 passed. Keep both green.
4. **Guard:** `tests/test_chassis_contract.py::test_no_coral_in_chassis_logic` bans the literal `coral` in any non-test `*.py` under `research/v7-renderer/`. No new "coral".

### Five architecture rules every pattern MUST follow (prevent open loops)

- **R-1 Interface:** `def render(page: dict, ctx: RenderContext) -> PageFragment` (import from `patterns.base`). Read `page["data"]` (default `{}`), `page.get("assets") or []`, `page.get("components") or []`. Use `ctx.brand` + `ctx.resolve_asset`/`ctx.resolve_component`.
- **R-2 No head-level CSS in a fragment:** never emit `@page`/`@font-face`/`:root`/`html`/`body{}` — those live in the assembler's shared head. (A test asserts these strings are absent from `frag.css`.)
- **R-3 Scope ALL pattern CSS under the page's section class.** The assembler wraps each page in `<section class="page st-XX">` (e.g. `st-01`, `st-09`, `st-fazit`). Every selector a pattern emits MUST be prefixed with its `.st-XX` (e.g. `.st-09 .symptom-title { … }`). This prevents cross-page CSS bleed across the 12 patterns in the single shared `<style>`. Shared-component CSS (from `_components.py`) is intentionally global (identical everywhere → dedupes).
- **R-4 Per-page dynamic values inline, not in CSS.** Image URLs etc. go in `style="…"` on the element (the assembler dedupes identical CSS blocks; a per-page value in CSS would leak across pages).
- **R-5 Brand colors only via `var(--brand-*)`; degrade gracefully.** Never hardcode a client hex/name. Every enriched `data` key is optional; render what's present, omit what's absent. List fields accept BOTH a plain string item and an object item.
- **R-6 Python 3.11 — NO backslash inside an f-string `{…}` expression.** This repo runs Python **3.11.15**, where `f"…{f\"…\"…}"` (a double-quoted f-string nested in another f-string) is a hard `SyntaxError: f-string expression part cannot include a backslash`. **Precompute every optional/conditional HTML fragment into a variable** using single-quoted f-strings (double-quoted HTML attributes inside the expression are fine — only *backslashes* are forbidden), then reference the bare variable in the final assembly. Canonical correct form (follow this for ALL patterns/components):
  ```python
  headline_html = f'<h1 class="x-headline">{C._esc(title)}</h1>' if title else ""
  intro_html = f'<div class="x-intro">{intro}</div>' if intro else ""
  html = (f'<div class="st-XX-wrap">{headline_html}{intro_html}'
          f'<div class="x-list">{"".join(blocks)}</div></div>')
  ```
  Any code block below that shows an inline `{f"…" if X else ""}` conveys INTENT only — implement it with precomputed variables as above. The per-task pytest run imports the module, so a violation fails instantly.

### Per-batch rhythm (every batch ends here)

After a batch's components + patterns + unit tests are green:
1. **Enrich** `fixtures/apex/report_content.json` with that batch's structured fields (DATA; transcribed from `content for apex.md` — repo root — per the schema given in the task).
2. **Regenerate** the package (pre-processor venv): `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python ../v7-renderer/fixtures/apex/build_package.py` → expect `pages=20 st07a=5 …`, no AssertionError.
3. **Render** (renderer venv): `cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python render.py` → no traceback; note overflow/warnings.
4. **Visual-verify:** dispatch a reviewer that reads the batch's rendered PNGs (`output/report-pN.png`) AND the matching reference pages of `APEX - KI DMC Report v1 (1).pdf`, and reports whether the layout language matches (expected structural elements present + arranged like the reference). Tune CSS until it matches and no page overflows. **This is the fidelity gate — final CSS values are settled here, not guessed up-front.**

---

## File Structure

```
research/v7-renderer/patterns/
  _components.py   # NEW — qr_svg, numbered_step_card, numbered_block, stat_strip,
                   #       dark_cta_panel, horizontal_flow, bar_mini  (+ *_CSS consts)
  __init__.py      # MODIFY — register all 12 patterns in REGISTRY
  st_09.py st_14.py st_06.py            # Batch 1 (implement stubs)
  st_02.py st_07b.py st_08.py           # Batch 2 (st_08 is NEW)
  st_03.py st_fazit.py st_31.py st_32.py# Batch 3 (st_31/st_32 NEW)
  st_01.py st_05.py st_22.py            # Batch 4 (implement stubs)
  st_07a.py        # MODIFY (tiny) — import qr_svg from _components (DRY); keep tests green
research/v7-renderer/tests/test_render_r2.py   # NEW — per-pattern unit tests
research/v7-renderer/fixtures/apex/report_content.json  # enrich per batch
```

`st_31.py`, `st_32.py`, `st_08.py` are new files; the rest are one-line stubs being implemented.

---

## Data contract (recap — all keys OPTIONAL, graceful)

ST-01 `{title, subtitle, eyebrow, kicker_pills[str], intro, inclusions[str], proof_stats[{value,label}], teaser_items[str], author{name,role}}` + assets cover_hero/cover_author •
ST-02 `{title, body, zielgruppe[str], author{name,role}, cta_text, cta_url}` •
ST-03 `{title, body, cta_text, cta_url}` •
ST-05 `{title, body, stats[{value,label}], partners[str], credibility_points[str]}` •
ST-06 `{title, body, steps[{n,title,body} | str], ergebnis}` •
ST-07B `{title, body, key_insight, compare{ohne[str],mit[str]}}` •
ST-08 `{title, faqs[{frage,antwort}]}` •
ST-09 `{title, body, symptoms[{title,body} | str]}` •
ST-14 `{title, body, beliefs[{irrglaube,realitaet,quelle} | str]}` •
ST-22 `{title, body, steps[{n,title,body,dauer} | str]}` •
ST-31/32 `{phrase?}` + report texture/gradient asset •
ST-FAZIT `{title, body, these, kosten_des_nichtstuns, cta_text, cta_url}`

---

## Task 1: Shared components — `_components.py` (Batch 1 subset) + test scaffold

**Files:** Create `research/v7-renderer/patterns/_components.py`; create `research/v7-renderer/tests/test_render_r2.py`.

This task adds the components Batch 1 needs (`numbered_step_card`, `numbered_block`) PLUS the shared `qr_svg` and `_esc` (later batches extend this file with `stat_strip`, `dark_cta_panel`, `horizontal_flow`, `bar_mini`). Components return HTML strings; each has a global CSS constant patterns include.

- [ ] **Step 1: Write the failing test** — create `tests/test_render_r2.py`:

```python
"""R2 per-pattern + component unit tests."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHASSIS_ROOT = HERE.parent
sys.path.insert(0, str(CHASSIS_ROOT))

import pytest  # noqa: E402
from brand_tokens import parse_brand_tokens  # noqa: E402
from grammar_loader import load_grammar  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402

SAMPLE_BRAND = {
    "brand_primary": "#5a9ab3", "brand_accent": "#85d2ee",
    "brand_neutral_dark": "#0F0F1F", "brand_neutral_mid": "#7A7A8C",
    "brand_neutral_light": "#fdffff", "font_heading": "Montserrat",
    "font_body": "Source Sans 3", "qr_target_url": "https://example.de",
    "company_name_short": "Example", "company_url_display": "example.de",
}

def _ctx(package_dir: Path = CHASSIS_ROOT / "fixtures" / "apex") -> RenderContext:
    return RenderContext(brand=parse_brand_tokens(SAMPLE_BRAND),
                         grammar=load_grammar(), package_dir=package_dir)

def _no_head_css(frag: PageFragment) -> None:
    for tok in ("@page", "@font-face", ":root"):
        assert tok not in frag.css, f"{tok} must not appear in fragment css"


def test_components_numbered_block_and_step_card() -> None:
    from patterns import _components as C
    block = C.numbered_block(1, "Titel", "<p>Body</p>", reality_html="<p>Real</p>", quelle="BCG 2025")
    assert "Titel" in block and "Real" in block and "BCG 2025" in block
    card = C.numbered_step_card(2, "Schritt", "<p>tu dies</p>")
    assert "Schritt" in card and "tu dies" in card
    assert isinstance(C.NUMBERED_BLOCK_CSS, str) and C.NUMBERED_BLOCK_CSS.strip()
    assert isinstance(C.NUMBERED_STEP_CARD_CSS, str) and C.NUMBERED_STEP_CARD_CSS.strip()
    # QR helper present + parity with st_07a
    svg = C.qr_svg("https://x.de", "#FFFFFF", "#000000")
    assert svg.startswith("<svg") and "rect" in svg
```

- [ ] **Step 2: Run it — expect FAIL** (`ModuleNotFoundError: No module named 'patterns._components'`)

Run: `cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python -m pytest tests/test_render_r2.py -k components -q`

- [ ] **Step 3: Implement `patterns/_components.py`** (Batch-1 subset):

```python
"""Shared pattern components — reusable HTML builders + global CSS constants.

Each build_* returns an HTML string; the paired *_CSS constant is included by
patterns in their PageFragment.css. Component CSS is GLOBAL + static (class-based)
so it dedupes across patterns; per-instance values are inlined on elements.
All honor anti-patterns (no rounded corners except gated classes; no shadows);
accent fires only at §3.7 locations (numbers, kickers, URLs, stat values, glyphs).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import qrcode  # noqa: E402


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def qr_svg(url: str, fg: str, bg: str, cell: int = 4) -> str:
    """Inline SVG QR (fg modules on bg). Extracted from st_07a so both share one impl."""
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=cell, border=0)
    qr.add_data(url)
    qr.make(fit=True)
    n = qr.modules_count
    size = n * cell
    rects = []
    for r, row in enumerate(qr.get_matrix()):
        for c, on in enumerate(row):
            if on:
                rects.append(f'<rect x="{c*cell}" y="{r*cell}" width="{cell}" height="{cell}" fill="{fg}"/>')
    return (f'<svg viewBox="0 0 {size} {size}" width="100%" height="100%" '
            f'xmlns="http://www.w3.org/2000/svg"><rect width="{size}" height="{size}" fill="{bg}"/>'
            + "".join(rects) + "</svg>")


# ---- numbered_step_card (ST-06) ----
NUMBERED_STEP_CARD_CSS = """
.nb-step-card { display:flex; gap:5mm; margin:0 0 5mm 0; padding:5mm; border:0.4mm solid var(--brand-neutral-mid); border-radius:2mm; }
.nb-step-card .nb-step-num { flex:0 0 auto; font-family:'Montserrat',sans-serif; font-weight:800; font-size:18pt; color:var(--brand-accent); line-height:1; min-width:11mm; }
.nb-step-card .nb-step-title { font-family:'Montserrat',sans-serif; font-weight:700; font-size:11pt; color:var(--brand-primary); margin:0 0 1.5mm 0; }
.nb-step-card .nb-step-body p { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:9.5pt; line-height:1.45; color:#333; margin:0 0 2mm 0; }
"""

def numbered_step_card(n, title: str, body_html: str) -> str:
    return (f'<div class="nb-step-card"><div class="nb-step-num">{_esc(n)}</div>'
            f'<div class="nb-step-text"><div class="nb-step-title">{_esc(title)}</div>'
            f'<div class="nb-step-body">{body_html}</div></div></div>')


# ---- numbered_block (ST-09, ST-14) ----
NUMBERED_BLOCK_CSS = """
.nb-block { display:flex; gap:5mm; margin:0 0 6mm 0; }
.nb-block .nb-index { flex:0 0 auto; font-family:'Montserrat',sans-serif; font-weight:800; font-size:22pt; color:var(--brand-accent); line-height:0.9; min-width:13mm; }
.nb-block .nb-title { font-family:'Montserrat',sans-serif; font-weight:700; font-size:11pt; color:var(--brand-primary); margin:0 0 2mm 0; }
.nb-block .nb-body p { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:9.5pt; line-height:1.45; color:#333; margin:0 0 2mm 0; text-align:justify; hyphens:auto; }
.nb-block .nb-reality { margin-top:2mm; padding-left:4mm; border-left:1mm solid var(--brand-accent); }
.nb-block .nb-quelle { font-family:'Montserrat',sans-serif; font-weight:600; font-size:7pt; letter-spacing:0.06em; text-transform:uppercase; color:var(--brand-neutral-mid); margin-top:1.5mm; }
"""

def numbered_block(n, title: str, body_html: str, *, reality_html: str | None = None, quelle: str = "") -> str:
    reality = f'<div class="nb-reality">{reality_html}</div>' if reality_html else ""
    q = f'<div class="nb-quelle">{_esc(quelle)}</div>' if quelle else ""
    title_html = f'<div class="nb-title">{_esc(title)}</div>' if title else ""
    return (f'<div class="nb-block"><div class="nb-index">{_esc(n)}</div>'
            f'<div class="nb-text">{title_html}<div class="nb-body">{body_html}</div>{reality}{q}</div></div>')
```

- [ ] **Step 4: Run it — expect PASS**

Run: `… && python -m pytest tests/test_render_r2.py -k components -q`

- [ ] **Step 5: DRY — point `st_07a` at the shared `qr_svg`** (optional-but-do-it; keep tests green): in `patterns/st_07a.py`, replace the local `_qr_svg` definition with `from patterns._components import qr_svg as _qr_svg` (keep the call sites `_qr_svg(...)` unchanged). Run `… && python -m pytest tests/ -q` → still 26+ green.

- [ ] **Step 6: Verification checkpoint**

Run: `cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python -m pytest tests/ -q`
Expected: all green (26 + new component tests).

---

## Task 2: ST-09 (Status quo), ST-14 (False beliefs), ST-06 (Mechanism)

**Files:** implement `patterns/st_09.py`, `patterns/st_14.py`, `patterns/st_06.py`; register in `patterns/__init__.py`; append tests to `tests/test_render_r2.py`.

- [ ] **Step 1: Append failing tests:**

```python
def _page(st_type, data, slot=4):
    return {"slot": slot, "st_type": st_type, "page_numbers": str(slot), "data": data, "assets": [], "components": []}

def test_st09_status_quo() -> None:
    from patterns import st_09
    data = {"title": "Deine Prozesse skalieren nicht", "body": "Intro.",
            "symptoms": [{"title": "Montag kostet 3 Stunden", "body": "Du öffnest fünf Tools."},
                         "Ein reiner String-Eintrag"]}
    frag = st_09.render(_page("ST-09", data), _ctx())
    assert isinstance(frag, PageFragment); _no_head_css(frag)
    assert ".st-09" in frag.css                       # R-3 scoping
    assert "Montag kostet 3 Stunden" in frag.html and "reiner String" in frag.html
    assert st_09.render(_page("ST-09", {}), _ctx()).html.strip()  # graceful empty

def test_st14_false_beliefs() -> None:
    from patterns import st_14
    data = {"title": "Drei Lügen", "beliefs": [
        {"irrglaube": "Mehr Leute = mehr Kunden", "realitaet": "Systeme skalieren, nicht Köpfe.", "quelle": "PwC 2026"}]}
    frag = st_14.render(_page("ST-14", data), _ctx())
    _no_head_css(frag); assert ".st-14" in frag.css
    assert "Mehr Leute" in frag.html and "Systeme skalieren" in frag.html and "PwC 2026" in frag.html

def test_st06_mechanism() -> None:
    from patterns import st_06
    data = {"title": "Das Framework", "body": "Intro.",
            "steps": [{"title": "Audit", "body": "Wir messen."}, {"title": "Bereinigung", "body": "Wir putzen."}],
            "ergebnis": "30-50% Effizienz."}
    frag = st_06.render(_page("ST-06", data), _ctx())
    _no_head_css(frag); assert ".st-06" in frag.css
    assert "Audit" in frag.html and "Bereinigung" in frag.html
```

- [ ] **Step 2: Run — expect FAIL** (`AttributeError: module 'patterns.st_09' has no attribute 'render'`)

Run: `… && python -m pytest tests/test_render_r2.py -k "st09 or st14 or st06" -q`

- [ ] **Step 3: Implement the three patterns.** Each scopes CSS under its `.st-XX` (R-3), reads optional keys (R-5), uses `numbered_block`/`numbered_step_card`.

`patterns/st_09.py`:
```python
"""ST-09 Status quo — intro + numbered symptom blocks (grammar P-4)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from preprocess import preprocess_body  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402
from patterns import _components as C  # noqa: E402

def _item(it):
    return (it.get("title", ""), it.get("body", "")) if isinstance(it, dict) else ("", str(it))

def render(page: dict, ctx: RenderContext) -> PageFragment:
    d = page.get("data") or {}
    title = d.get("title", "")
    intro = preprocess_body(d.get("body", ""))
    blocks = []
    for i, it in enumerate(d.get("symptoms") or [], start=1):
        t, body = _item(it)
        blocks.append(C.numbered_block(i, t, preprocess_body(body)))
    headline_html = f'<h1 class="sq-headline">{C._esc(title)}</h1>' if title else ""
    intro_html = f'<div class="sq-intro">{intro}</div>' if intro else ""
    html = (f'<div class="st-09-wrap">{headline_html}{intro_html}'
            f'<div class="sq-list">{"".join(blocks)}</div></div>')
    css = C.NUMBERED_BLOCK_CSS + """
.st-09 .sq-headline { font-family:'Montserrat',sans-serif; font-weight:800; font-size:24pt; color:var(--brand-primary); line-height:1.12; margin:0 0 4mm 0; }
.st-09 .sq-intro p { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:11pt; line-height:1.45; color:#333; margin:0 0 6mm 0; }
"""
    return PageFragment(html=html, css=css)
```

`patterns/st_14.py`:
```python
"""ST-14 False beliefs — numbered Irrglaube→Realität blocks (grammar P-5)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from preprocess import preprocess_body  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402
from patterns import _components as C  # noqa: E402

def render(page: dict, ctx: RenderContext) -> PageFragment:
    d = page.get("data") or {}
    title = d.get("title", "")
    intro = preprocess_body(d.get("body", ""))
    blocks = []
    for i, it in enumerate(d.get("beliefs") or [], start=1):
        if isinstance(it, dict):
            irr = it.get("irrglaube", ""); real = it.get("realitaet", ""); q = it.get("quelle", "")
            blocks.append(C.numbered_block(i, irr, "", reality_html=preprocess_body(real), quelle=q))
        else:
            blocks.append(C.numbered_block(i, "", preprocess_body(str(it))))
    headline_html = f'<h1 class="fb-headline">{C._esc(title)}</h1>' if title else ""
    intro_html = f'<div class="fb-intro">{intro}</div>' if intro else ""
    html = (f'<div class="st-14-wrap">{headline_html}{intro_html}'
            f'<div class="fb-list">{"".join(blocks)}</div></div>')
    css = C.NUMBERED_BLOCK_CSS + """
.st-14 .fb-headline { font-family:'Montserrat',sans-serif; font-weight:800; font-size:24pt; color:var(--brand-primary); line-height:1.12; margin:0 0 4mm 0; }
.st-14 .fb-intro p { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:11pt; line-height:1.45; color:#333; margin:0 0 6mm 0; }
.st-14 .nb-title { font-style:italic; }
"""
    return PageFragment(html=html, css=css)
```

`patterns/st_06.py`:
```python
"""ST-06 Mechanism — numbered step cards + result recap (grammar P-8)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from preprocess import preprocess_body  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402
from patterns import _components as C  # noqa: E402

def _step(it):
    return (it.get("title", ""), it.get("body", "")) if isinstance(it, dict) else ("", str(it))

def render(page: dict, ctx: RenderContext) -> PageFragment:
    d = page.get("data") or {}
    title = d.get("title", "")
    intro = preprocess_body(d.get("body", ""))
    cards = []
    for i, it in enumerate(d.get("steps") or [], start=1):
        t, body = _step(it)
        cards.append(C.numbered_step_card(i, t, preprocess_body(body)))
    ergebnis = d.get("ergebnis", "")
    recap = f'<div class="mx-recap"><div class="mx-recap-label">DAS ERGEBNIS</div>{preprocess_body(ergebnis)}</div>' if ergebnis else ""
    headline_html = f'<h1 class="mx-headline">{C._esc(title)}</h1>' if title else ""
    intro_html = f'<div class="mx-intro">{intro}</div>' if intro else ""
    html = (f'<div class="st-06-wrap">{headline_html}{intro_html}'
            f'<div class="mx-steps">{"".join(cards)}</div>{recap}</div>')
    css = C.NUMBERED_STEP_CARD_CSS + """
.st-06 .mx-headline { font-family:'Montserrat',sans-serif; font-weight:800; font-size:23pt; color:var(--brand-primary); line-height:1.12; margin:0 0 4mm 0; }
.st-06 .mx-intro p { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:10pt; line-height:1.45; color:#333; margin:0 0 5mm 0; }
.st-06 .mx-recap { margin-top:4mm; padding:5mm; background:var(--brand-primary); color:#fff; }
.st-06 .mx-recap-label { font-family:'Montserrat',sans-serif; font-weight:700; font-size:8pt; letter-spacing:0.15em; color:var(--brand-accent); margin-bottom:2mm; }
.st-06 .mx-recap p { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:10pt; line-height:1.4; color:#fff; margin:0; }
"""
    return PageFragment(html=html, css=css)
```

- [ ] **Step 4: Register in `patterns/__init__.py`** — extend `REGISTRY`:
```python
from patterns import st_07a, _generic, st_09, st_14, st_06
REGISTRY: dict[str, Callable[[dict, RenderContext], PageFragment]] = {
    "ST-07A": st_07a.render,
    "ST-09": st_09.render,
    "ST-14": st_14.render,
    "ST-06": st_06.render,
}
```
(Keep `get_renderer` unchanged. Later tasks add more imports + entries.)

- [ ] **Step 5: Run — expect PASS**

Run: `… && python -m pytest tests/test_render_r2.py -k "st09 or st14 or st06" -q`

- [ ] **Step 6: Verification checkpoint** (full suite green)

Run: `cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python -m pytest tests/ -q`

---

## Task 3: Batch 1 fixture enrichment + visual-verify

**Files:** Modify `research/v7-renderer/fixtures/apex/report_content.json` (slots 4=ST-09, 5=ST-14, 16=ST-06).

- [ ] **Step 1: Enrich the three pages' `data`** by transcribing from `content for apex.md` (repo root):
  - **Slot 4 (ST-09 STATUS QUO):** add `"symptoms"` = array of the 6 SYMPTOMS, each `{"title": <bold lead line>, "body": <the paragraph under it>}`. (e.g. `{"title":"Montagmorgen kostet drei Stunden Überblick","body":"Du öffnest fünf verschiedene Tools, kopierst Daten …"}`). Keep existing `title`/`body`.
  - **Slot 5 (ST-14 FALSE BELIEFS):** add `"beliefs"` = the 3 items, each `{"irrglaube": <the „…" quote after IRRGLAUBE N>, "realitaet": <the REALITÄT line + its paragraph>, "quelle": <the parenthetical source(s), e.g. "PwC 2026 · KPMG 2025">}`.
  - **Slot 16 (ST-06 MECHANISM):** add `"steps"` = the 6 SCHRITTE, each `{"title": <step heading w/o the [full]/[gesture] tag>, "body": <its paragraph>}`, and `"ergebnis"`: a one-line result (use the PwC 30-50% sentence from the MECHANISMUS intro).
  Keep valid JSON; strings verbatim (keep `„` glyphs).

- [ ] **Step 2: Regenerate** (pre-processor venv):
`cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python ../v7-renderer/fixtures/apex/build_package.py`
Expected: `pages=20 st07a=5 …`, no AssertionError.

- [ ] **Step 3: Render + visual-verify** (renderer venv):
`cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python render.py`
Then dispatch a visual reviewer (general-purpose): give it `output/report-p4.png`, `-p5.png`, `-p16.png` and reference pages of `APEX - KI DMC Report v1 (1).pdf` showing the status-quo / false-beliefs / mechanism sections; ask whether the numbered-list / step-card layout language matches (numbered items, accent indices, reality sub-blocks, step cards, result panel) and whether anything overflows. Tune the `.st-09/.st-14/.st-06` CSS until it matches and no page overflows.

- [ ] **Step 4: Checkpoint** — `… && python -m pytest tests/ -q` green; `python render.py` shows no overflow for slots 4/5/16.

---

## Task 4: ST-02 (Outlook), ST-07B (Theory), ST-08 (FAQ)

**Files:** implement `patterns/st_02.py`, `patterns/st_07b.py`; create `patterns/st_08.py`; register in `__init__.py`; append tests. No new shared components.

- [ ] **Step 1: Append failing tests:**

```python
def test_st02_outlook() -> None:
    from patterns import st_02
    data = {"title": "Dein Wachstum scheitert nicht am Markt", "body": "Abs eins.\n\nAbs zwei.",
            "zielgruppe": ["B2B 10-50 MA", "500k-3M Umsatz"]}
    frag = st_02.render(_page("ST-02", data, slot=2), _ctx())
    _no_head_css(frag); assert ".st-02" in frag.css
    assert "Dein Wachstum" in frag.html and "B2B 10-50 MA" in frag.html
    assert st_02.render(_page("ST-02", {}, slot=2), _ctx()).html.strip()

def test_st07b_theory() -> None:
    from patterns import st_07b
    data = {"title": "Wachstum entsteht nicht durch mehr Köpfe", "body": "Prosa.",
            "key_insight": "Engpässe sind strukturell, nicht motivational."}
    frag = st_07b.render(_page("ST-07B", data, slot=8), _ctx())
    _no_head_css(frag); assert ".st-07b" in frag.css
    assert "mehr Köpfe" in frag.html and "strukturell" in frag.html

def test_st08_faq() -> None:
    from patterns import st_08
    data = {"title": "Häufige Fragen", "faqs": [
        {"frage": "Wie lange dauert es?", "antwort": "Wenige Wochen."},
        {"frage": "Muss ich Tools wechseln?", "antwort": "Nein."}]}
    frag = st_08.render(_page("ST-08", data, slot=99), _ctx())
    _no_head_css(frag); assert ".st-08" in frag.css
    assert "Wie lange" in frag.html and "Wenige Wochen" in frag.html
    assert st_08.render(_page("ST-08", {}, slot=99), _ctx()).html.strip()
```

- [ ] **Step 2: Run — expect FAIL**

Run: `… && python -m pytest tests/test_render_r2.py -k "st02 or st07b or st08" -q`

- [ ] **Step 3: Implement the three patterns.**

`patterns/st_02.py`:
```python
"""ST-02 Outlook — display headline + two-column body + optional Zielgruppe checklist (P-2)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from preprocess import preprocess_body  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402
from patterns import _components as C  # noqa: E402

def render(page: dict, ctx: RenderContext) -> PageFragment:
    d = page.get("data") or {}
    title = d.get("title", "")
    body = preprocess_body(d.get("body", ""))
    zg = d.get("zielgruppe") or []
    zg_html = ""
    if zg:
        lis = "".join(f"<li>{C._esc(z)}</li>" for z in zg)
        zg_html = f'<div class="ol-zg"><div class="ol-zg-label">ZIELGRUPPE DES REPORTS</div><ul>{lis}</ul></div>'
    headline_html = f'<h1 class="ol-headline">{C._esc(title)}</h1>' if title else ""
    body_block = f'<div class="ol-body">{body}</div>' if body else ""
    html = f'<div class="st-02-wrap">{headline_html}{body_block}{zg_html}</div>'
    css = """
.st-02 .ol-headline { font-family:'Montserrat',sans-serif; font-weight:800; font-size:26pt; color:var(--brand-primary); line-height:1.1; margin:0 0 6mm 0; }
.st-02 .ol-body { column-count:2; column-gap:8mm; }
.st-02 .ol-body p { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:10pt; line-height:1.5; color:#333; margin:0 0 3mm 0; text-align:justify; hyphens:auto; }
.st-02 .ol-zg { margin-top:5mm; padding-top:4mm; border-top:0.3mm solid var(--brand-neutral-mid); }
.st-02 .ol-zg-label { font-family:'Montserrat',sans-serif; font-weight:700; font-size:8pt; letter-spacing:0.15em; color:var(--brand-accent); margin-bottom:2mm; }
.st-02 .ol-zg ul { list-style:none; padding:0; margin:0; }
.st-02 .ol-zg li { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:9.5pt; color:#333; margin:0 0 1.5mm 0; padding-left:5mm; position:relative; }
.st-02 .ol-zg li::before { content:"\\2713"; position:absolute; left:0; color:var(--brand-accent); font-weight:700; }
"""
    return PageFragment(html=html, css=css)
```

`patterns/st_07b.py`:
```python
"""ST-07B Theory/Gegenseite — prose + key-insight callout + optional before/after (P-7)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from preprocess import preprocess_body  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402
from patterns import _components as C  # noqa: E402

def render(page: dict, ctx: RenderContext) -> PageFragment:
    d = page.get("data") or {}
    title = d.get("title", "")
    body = preprocess_body(d.get("body", ""))
    insight = d.get("key_insight", "")
    insight_html = f'<div class="th-insight">{preprocess_body(insight)}</div>' if insight else ""
    compare = d.get("compare") or {}
    cmp_html = ""
    if compare.get("ohne") or compare.get("mit"):
        def col(label, items):
            lis = "".join(f"<li>{C._esc(x)}</li>" for x in (items or []))
            return f'<div class="th-col"><div class="th-col-label">{label}</div><ul>{lis}</ul></div>'
        cmp_html = (f'<div class="th-compare">{col("OHNE", compare.get("ohne"))}'
                    f'{col("MIT", compare.get("mit"))}</div>')
    headline_html = f'<h1 class="th-headline">{C._esc(title)}</h1>' if title else ""
    body_block = f'<div class="th-body">{body}</div>' if body else ""
    html = f'<div class="st-07b-wrap">{headline_html}{body_block}{cmp_html}{insight_html}</div>'
    css = """
.st-07b .th-headline { font-family:'Montserrat',sans-serif; font-weight:800; font-size:25pt; color:var(--brand-primary); line-height:1.12; margin:0 0 5mm 0; }
.st-07b .th-body p { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:10.5pt; line-height:1.5; color:#333; margin:0 0 3mm 0; text-align:justify; hyphens:auto; }
.st-07b .th-insight { margin-top:5mm; padding:5mm 6mm; border-left:1.5mm solid var(--brand-accent); background:var(--brand-neutral-light); }
.st-07b .th-insight p { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-style:italic; font-weight:600; font-size:12pt; line-height:1.4; color:var(--brand-primary); margin:0; }
.st-07b .th-compare { display:flex; gap:6mm; margin:5mm 0; }
.st-07b .th-col { flex:1; padding:5mm; border:0.4mm solid var(--brand-neutral-mid); }
.st-07b .th-col-label { font-family:'Montserrat',sans-serif; font-weight:700; font-size:9pt; letter-spacing:0.12em; color:var(--brand-accent); margin-bottom:2mm; }
.st-07b .th-col ul { margin:0; padding-left:5mm; }
.st-07b .th-col li { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:9.5pt; line-height:1.4; color:#333; margin:0 0 1.5mm 0; }
"""
    return PageFragment(html=html, css=css)
```

`patterns/st_08.py` (NEW):
```python
"""ST-08 FAQ — question/answer stack (Master S19; not used by apex — synthetic-verified)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from preprocess import preprocess_body  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402
from patterns import _components as C  # noqa: E402

def render(page: dict, ctx: RenderContext) -> PageFragment:
    d = page.get("data") or {}
    title = d.get("title", "")
    items = []
    for f in (d.get("faqs") or []):
        q = f.get("frage", "") if isinstance(f, dict) else ""
        a = f.get("antwort", "") if isinstance(f, dict) else str(f)
        items.append(f'<div class="faq-item"><div class="faq-q">{C._esc(q)}</div>'
                     f'<div class="faq-a">{preprocess_body(a)}</div></div>')
    headline_html = f'<h1 class="faq-headline">{C._esc(title)}</h1>' if title else ""
    html = (f'<div class="st-08-wrap">{headline_html}'
            f'<div class="faq-list">{"".join(items)}</div></div>')
    css = """
.st-08 .faq-headline { font-family:'Montserrat',sans-serif; font-weight:800; font-size:24pt; color:var(--brand-primary); line-height:1.12; margin:0 0 6mm 0; }
.st-08 .faq-list { column-count:2; column-gap:8mm; }
.st-08 .faq-item { break-inside:avoid; margin:0 0 5mm 0; }
.st-08 .faq-q { font-family:'Montserrat',sans-serif; font-weight:700; font-size:10.5pt; color:var(--brand-accent); margin:0 0 1.5mm 0; }
.st-08 .faq-a p { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:9.5pt; line-height:1.45; color:#333; margin:0 0 2mm 0; }
"""
    return PageFragment(html=html, css=css)
```

- [ ] **Step 4: Register** in `patterns/__init__.py` — add imports `st_02, st_07b, st_08` and entries `"ST-02": st_02.render, "ST-07B": st_07b.render, "ST-08": st_08.render`.

- [ ] **Step 5: Run — expect PASS**

Run: `… && python -m pytest tests/test_render_r2.py -k "st02 or st07b or st08" -q`

- [ ] **Step 6: Verification checkpoint** — `… && python -m pytest tests/ -q` green.

---

## Task 5: Batch 2 fixture enrichment + visual-verify

**Files:** Modify `fixtures/apex/report_content.json` (slot 2 = ST-02; slots 8/10/13 = ST-07B already carry `key_insight` from R1 — verify present). ST-08 is NOT in the apex report (synthetic-verified in Task 4 only).

- [ ] **Step 1: Enrich slot 2 (ST-02)** — optionally add `"zielgruppe"` (derive 3-5 bullets from the OUTLOOK section's audience description in `content for apex.md`, e.g. "B2B-Unternehmen mit 10–50 Mitarbeitern", "€500k–€3M Jahresumsatz"). If the content has no clear audience list, leave it out (the pattern omits it gracefully). Confirm slots 8/10/13 each have a non-empty `key_insight`; if any is missing, add it from the THEORY section's KEY INSIGHT line.

- [ ] **Step 2: Regenerate** (pre-processor venv): `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python ../v7-renderer/fixtures/apex/build_package.py` → `pages=20 st07a=5 …`, no AssertionError.

- [ ] **Step 3: Render + visual-verify** — `cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python render.py`; dispatch a visual reviewer with `output/report-p2.png`, `-p8.png`, `-p10.png`, `-p13.png` vs. the reference PDF's outlook + theory pages. Confirm: ST-02 two-column body + (if present) Zielgruppe checklist; ST-07B prose + accent key-insight callout. Tune `.st-02`/`.st-07b` CSS until matched and no overflow.

- [ ] **Step 4: Checkpoint** — `… && python -m pytest tests/ -q` green; render shows no overflow for slots 2/8/10/13.

---

## Task 6: `dark_cta_panel` component + ST-03 (Hard CTA), ST-FAZIT (Summary), ST-31/ST-32 (breathing)

**Files:** extend `patterns/_components.py` (add `dark_cta_panel` + CSS); implement `patterns/st_03.py`, `patterns/st_fazit.py`; create `patterns/st_31.py` + `patterns/st_32.py`; register; append tests.

> **R-3 note for breathing:** ST-31 and ST-32 share ONE render. To apply to both `.st-31` and `.st-32` sections, the breathing pattern scopes its CSS under its own globally-unique wrapper class `.br-page` (a unique prefix satisfies R-3's anti-collision intent just like component classes do).

- [ ] **Step 1: Append failing tests:**

```python
def test_components_dark_cta_panel() -> None:
    from patterns import _components as C
    p = C.dark_cta_panel("Buche jetzt", "https://apex.de", qr="<svg/>", body_html="<p>Los.</p>")
    assert "Buche jetzt" in p and "apex.de" in p and "Los." in p
    assert isinstance(C.DARK_CTA_PANEL_CSS, str) and C.DARK_CTA_PANEL_CSS.strip()

def test_st03_hard_cta() -> None:
    from patterns import st_03
    data = {"title": "Buche jetzt dein Erstgespräch", "body": "Kein Risiko.",
            "cta_text": "Jetzt buchen", "cta_url": "https://apex-consulting.ai/"}
    frag = st_03.render(_page("ST-03", data, slot=20), _ctx())
    _no_head_css(frag); assert ".st-03" in frag.css
    assert "Buche jetzt" in frag.html and "apex-consulting.ai" in frag.html

def test_stfazit_summary() -> None:
    from patterns import st_fazit
    data = {"title": "Zusammenfassung", "body": "Argument.",
            "these": "Es ist ein Systemfehler.", "kosten_des_nichtstuns": "Jeder Monat kostet.",
            "cta_url": "https://apex-consulting.ai/"}
    frag = st_fazit.render(_page("ST-FAZIT", data, slot=18), _ctx())
    _no_head_css(frag); assert ".st-fazit" in frag.css
    assert "Systemfehler" in frag.html and "Jeder Monat" in frag.html

def test_st31_breathing_css_ground_and_asset(tmp_path) -> None:
    from patterns import st_31, st_32
    # no asset -> CSS ground, still valid
    frag = st_31.render(_page("ST-31", {"phrase": "Durchatmen."}), _ctx())
    _no_head_css(frag); assert "br-page" in frag.html and "Durchatmen." in frag.html
    assert st_32.render is st_31.render  # ST-32 reuses the breathing render
    # with a background asset on the page
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "g.png").write_bytes(b"\x89PNG\r\n")
    page = {"slot": 6, "st_type": "ST-31", "data": {},
            "assets": [{"slot_id": "atmospheric_gradient", "image_type": "gradient", "path": "assets/g.png"}],
            "components": []}
    frag2 = st_31.render(page, _ctx(tmp_path))
    assert "g.png" in frag2.html
```

- [ ] **Step 2: Run — expect FAIL**

Run: `… && python -m pytest tests/test_render_r2.py -k "dark_cta or st03 or stfazit or st31" -q`

- [ ] **Step 3a: Add `dark_cta_panel` to `_components.py`:**
```python
# ---- dark_cta_panel (ST-03, ST-FAZIT) ----
DARK_CTA_PANEL_CSS = """
.dcp { background:var(--brand-primary); color:#fff; padding:14mm 12mm; }
.dcp .dcp-headline { font-family:'Montserrat',sans-serif; font-weight:800; font-size:24pt; line-height:1.1; color:#fff; margin:0 0 5mm 0; }
.dcp .dcp-body p { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:11pt; line-height:1.5; color:rgba(255,255,255,0.9); margin:0 0 4mm 0; }
.dcp .dcp-cta { font-family:'Montserrat',sans-serif; font-weight:700; font-size:10pt; letter-spacing:0.08em; text-transform:uppercase; color:#fff; margin:0 0 2mm 0; }
.dcp .dcp-url { font-family:'Montserrat',sans-serif; font-weight:800; font-size:19pt; color:var(--brand-accent); text-decoration:none; display:block; margin:3mm 0; word-break:break-all; }
.dcp .dcp-qr { width:26mm; height:26mm; background:#fff; padding:2mm; margin-top:4mm; }
"""

def dark_cta_panel(headline, url, *, qr=None, body_html=None, cta_text=None):
    body = f'<div class="dcp-body">{body_html}</div>' if body_html else ""
    cta = f'<div class="dcp-cta">{_esc(cta_text)}</div>' if cta_text else ""
    qr_html = f'<div class="dcp-qr">{qr}</div>' if qr else ""
    head = f'<div class="dcp-headline">{_esc(headline)}</div>' if headline else ""
    url_html = f'<a class="dcp-url" href="{_esc(url)}">{_esc(url)}</a>' if url else ""
    return f'<div class="dcp">{head}{body}{cta}{url_html}{qr_html}</div>'
```

- [ ] **Step 3b: Implement the patterns.**

`patterns/st_03.py`:
```python
"""ST-03 Hard-CTA back cover — dark panel + oversized accent URL + QR (P-12)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from preprocess import preprocess_body  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402
from patterns import _components as C  # noqa: E402

def render(page: dict, ctx: RenderContext) -> PageFragment:
    d = page.get("data") or {}
    url = d.get("cta_url") or ctx.brand.qr_target_url
    qr = C.qr_svg(url, fg=ctx.brand.brand_primary, bg="#FFFFFF")
    panel = C.dark_cta_panel(d.get("title", ""), url, qr=qr,
                             body_html=preprocess_body(d.get("body", "")),
                             cta_text=d.get("cta_text"))
    html = f'<div class="st-03-wrap">{panel}</div>'
    css = C.DARK_CTA_PANEL_CSS + """
.st-03 .dcp { min-height: 232mm; }
"""
    return PageFragment(html=html, css=css)
```

`patterns/st_fazit.py`:
```python
"""ST-FAZIT Summary — dark header band + body + These pull-statement + cost + CTA (P-9)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from preprocess import preprocess_body  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402
from patterns import _components as C  # noqa: E402

def render(page: dict, ctx: RenderContext) -> PageFragment:
    d = page.get("data") or {}
    title = d.get("title", "")
    body = preprocess_body(d.get("body", ""))
    these = d.get("these", "")
    kosten = d.get("kosten_des_nichtstuns", "")
    url = d.get("cta_url", "")
    header = f'<div class="fz-header">{C._esc(title)}</div>' if title else ""
    these_html = f'<div class="fz-these">{C._esc(these)}</div>' if these else ""
    kosten_html = (f'<div class="fz-kosten"><div class="fz-kosten-label">KOSTEN DES NICHTSTUNS</div>'
                   f'{preprocess_body(kosten)}</div>') if kosten else ""
    cta = f'<a class="fz-cta" href="{C._esc(url)}">{C._esc(url)}</a>' if url else ""
    body_block = f'<div class="fz-body">{body}</div>' if body else ""
    html = (f'<div class="st-fazit-wrap">{header}{body_block}'
            f'{these_html}{kosten_html}{cta}</div>')
    css = """
.st-fazit .fz-header { background:var(--brand-primary); color:#fff; font-family:'Montserrat',sans-serif; font-weight:800; font-size:22pt; line-height:1.1; padding:8mm; margin:0 0 6mm 0; }
.st-fazit .fz-body p { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:10.5pt; line-height:1.5; color:#333; margin:0 0 3mm 0; text-align:justify; hyphens:auto; }
.st-fazit .fz-these { font-family:'Montserrat',sans-serif; font-weight:700; font-size:15pt; line-height:1.25; color:var(--brand-primary); border-left:1.5mm solid var(--brand-accent); padding-left:5mm; margin:5mm 0; }
.st-fazit .fz-kosten { background:var(--brand-neutral-light); padding:5mm; margin:4mm 0; }
.st-fazit .fz-kosten-label { font-family:'Montserrat',sans-serif; font-weight:700; font-size:8pt; letter-spacing:0.15em; color:var(--brand-accent); margin-bottom:2mm; }
.st-fazit .fz-kosten p { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:10pt; line-height:1.45; color:#333; margin:0; }
.st-fazit .fz-cta { display:block; font-family:'Montserrat',sans-serif; font-weight:800; font-size:14pt; color:var(--brand-accent); text-decoration:none; margin-top:5mm; }
"""
    return PageFragment(html=html, css=css)
```

`patterns/st_31.py`:
```python
"""ST-31/ST-32 Atemseite — calm breathing page: report background asset if present, else CSS ground."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from patterns.base import PageFragment, RenderContext  # noqa: E402
from patterns import _components as C  # noqa: E402

_BG_TYPES = ("gradient", "texture", "background", "scene")

def render(page: dict, ctx: RenderContext) -> PageFragment:
    d = page.get("data") or {}
    bg_uri = None
    for a in (page.get("assets") or []):
        if a.get("image_type") in _BG_TYPES and a.get("path"):
            p = ctx.resolve_asset(a["path"])
            if p is not None:
                bg_uri = p.as_uri()
                break
    bg_html = (f'<div class="br-bg" style="background-image:url(\'{bg_uri}\')"></div>'
               if bg_uri else "")
    phrase = d.get("phrase", "")
    phrase_html = f'<div class="br-phrase">{C._esc(phrase)}</div>' if phrase else ""
    html = f'<div class="br-page">{bg_html}<div class="br-center">{phrase_html}</div></div>'
    css = """
.br-page { position:relative; min-height:232mm; }
.br-page .br-bg { position:absolute; inset:0; background-size:cover; background-position:center; z-index:0; }
.br-page .br-center { position:relative; z-index:1; display:flex; align-items:center; justify-content:center; min-height:232mm; }
.br-page .br-phrase { font-family:'Montserrat',sans-serif; font-weight:300; font-size:18pt; color:var(--brand-primary); text-align:center; max-width:120mm; }
"""
    return PageFragment(html=html, css=css)
```

`patterns/st_32.py` (NEW — reuses breathing render):
```python
"""ST-32 breathing — identical to ST-31 (Atemseite). Re-exports the shared render."""
from patterns.st_31 import render  # noqa: F401
```

- [ ] **Step 4: Register** in `patterns/__init__.py` — add imports `st_03, st_fazit, st_31, st_32` and entries `"ST-03": st_03.render, "ST-FAZIT": st_fazit.render, "ST-31": st_31.render, "ST-32": st_32.render`.

- [ ] **Step 5: Run — expect PASS**

Run: `… && python -m pytest tests/test_render_r2.py -k "dark_cta or st03 or stfazit or st31" -q`

- [ ] **Step 6: Verification checkpoint** — `… && python -m pytest tests/ -q` green.

---

## Task 7: Batch 3 fixture/image-map enrichment + visual-verify

**Files:** Modify `fixtures/apex/image_map.json` (put a background image on each breathing slot) and confirm slot 20 (ST-03) + slot 18 (ST-FAZIT) data.

- [ ] **Step 1: Map breathing backgrounds** — in `fixtures/apex/image_map.json`, add `page_assets` entries so slots 6, 11, 17 each carry a background-ish asset (reuse existing files), e.g.:
```json
{"slot": 6,  "slot_id": "breathing_bg_1", "image_type": "gradient", "file": "report_atmospheric_gradient.png"},
{"slot": 11, "slot_id": "breathing_bg_2", "image_type": "texture",  "file": "report_background_texture.png"},
{"slot": 17, "slot_id": "breathing_bg_3", "image_type": "background","file": "report_extra_wide.png"}
```
(Confirm those filenames via `ls fixtures/apex/assets/`.) Confirm slot 20's data has `title/body/cta_text/cta_url` (from R1) and slot 18 (ST-FAZIT) has `title/body/these/kosten_des_nichtstuns` (from R1) — add `cta_url: "https://apex-consulting.ai/"` to slot 18 if missing.

- [ ] **Step 2: Regenerate** (pre-processor venv): `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python ../v7-renderer/fixtures/apex/build_package.py` → `pages=20 st07a=5 …`, no AssertionError. (Breathing slots now carry their background asset.)

- [ ] **Step 3: Render + visual-verify** — `python render.py`; dispatch a visual reviewer with `output/report-p6.png`, `-p11.png`, `-p17.png` (breathing), `-p18.png` (Fazit), `-p20.png` (CTA) vs. the reference PDF's breathing / summary / back-cover pages. Confirm: breathing pages show the atmospheric background (or calm CSS ground) with generous whitespace; ST-FAZIT shows the dark header band + These pull-statement + cost block + accent CTA; ST-03 is the dark back cover with the oversized accent URL + QR. Tune CSS until matched, no overflow.

- [ ] **Step 4: Checkpoint** — `… && python -m pytest tests/ -q` green; render shows no overflow for slots 6/11/17/18/20.

---

## Task 8: `stat_strip` + `bar_mini` + `horizontal_flow` components + ST-01 (Cover), ST-05 (About), ST-22 (Collaboration)

**Files:** extend `patterns/_components.py`; implement `patterns/st_01.py`, `patterns/st_05.py`, `patterns/st_22.py`; register; append tests. These are the bespoke pages — first-pass CSS here; final fidelity is settled in Task 9's visual loop.

- [ ] **Step 1: Append failing tests:**

```python
def test_components_stat_bar_flow() -> None:
    from patterns import _components as C
    assert "100+" in C.stat_strip([{"value": "100+", "label": "Projekte"}])
    assert C.stat_strip([]) == ""
    assert "Projekte" in C.bar_mini([{"value": "100", "label": "Projekte"}, {"value": "30", "label": "Quote"}])
    flow = C.horizontal_flow([{"n": 1, "title": "Call", "body": "45 Min", "dauer": "1 Tag"},
                              {"n": 2, "title": "Audit", "body": "3-5 Tage"}])
    assert "Call" in flow and "Audit" in flow and "hf-arrow" in flow

def test_st01_cover() -> None:
    from patterns import st_01
    data = {"title": "Dein Wachstum frisst dich auf", "subtitle": "Wie manuelle Prozesse …",
            "kicker_pills": ["PROZESSAUTOMATISIERUNG"], "inclusions": ["3 Fallstudien"],
            "proof_stats": [{"value": "100", "label": "Projekte"}],
            "teaser_items": ["Warum 60% scheitern"], "author": {"name": "Jousef", "role": "Founder"}}
    frag = st_01.render(_page("ST-01", data, slot=1), _ctx())
    _no_head_css(frag); assert ".st-01" in frag.css
    assert "Dein Wachstum" in frag.html and "PROZESSAUTOMATISIERUNG" in frag.html and "Jousef" in frag.html
    assert st_01.render(_page("ST-01", {}, slot=1), _ctx()).html.strip()

def test_st05_about() -> None:
    from patterns import st_05
    data = {"title": "Über 100 AI-Projekte", "body": "APEX …",
            "stats": [{"value": "100+", "label": "Projekte"}, {"value": "30%", "label": "Einsparung"}],
            "partners": ["Frese", "Conesso"], "credibility_points": ["100+ Projekte"]}
    frag = st_05.render(_page("ST-05", data, slot=3), _ctx())
    _no_head_css(frag); assert ".st-05" in frag.css
    assert "100+" in frag.html and "Frese" in frag.html

def test_st22_collaboration() -> None:
    from patterns import st_22
    data = {"title": "Von Erstgespräch zu System", "body": "Strukturiert.",
            "steps": [{"n": 1, "title": "Strategiegespräch", "body": "45 Min.", "dauer": "1 Tag"},
                      {"n": 2, "title": "Audit", "body": "Bottlenecks.", "dauer": "3-5 Tage"}]}
    frag = st_22.render(_page("ST-22", data, slot=19), _ctx())
    _no_head_css(frag); assert ".st-22" in frag.css
    assert "Strategiegespräch" in frag.html and "hflow" in frag.html
```

- [ ] **Step 2: Run — expect FAIL**

Run: `… && python -m pytest tests/test_render_r2.py -k "stat_bar_flow or st01 or st05 or st22" -q`

- [ ] **Step 3a: Extend `_components.py`** — add at the top import `from preprocess import preprocess_body` (after the qrcode import), then append:
```python
# ---- stat_strip (ST-05, ST-01) ----
STAT_STRIP_CSS = """
.stat-strip-c { display:flex; gap:6mm; }
.stat-strip-c .ssc { flex:1; }
.stat-strip-c .ssc-value { font-family:'Montserrat',sans-serif; font-weight:800; font-size:20pt; color:var(--brand-accent); line-height:1; }
.stat-strip-c .ssc-label { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-weight:600; font-size:8pt; letter-spacing:0.04em; text-transform:uppercase; color:#333; margin-top:1.5mm; }
"""
def stat_strip(stats) -> str:
    cells = "".join(
        f'<div class="ssc"><div class="ssc-value">{_esc(s.get("value",""))}</div>'
        f'<div class="ssc-label">{_esc(s.get("label",""))}</div></div>'
        for s in (stats or []) if isinstance(s, dict))
    return f'<div class="stat-strip-c">{cells}</div>' if cells else ""

# ---- bar_mini (ST-01) ----
import re as _re
BAR_MINI_CSS = """
.bar-mini { display:flex; flex-direction:column; gap:2mm; }
.bar-mini .bm-row { display:flex; align-items:center; gap:3mm; }
.bar-mini .bm-bar { height:3mm; background:var(--brand-accent); min-width:6mm; }
.bar-mini .bm-label { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:7.5pt; color:#333; }
"""
def bar_mini(stats) -> str:
    parsed = []
    for s in (stats or []):
        if not isinstance(s, dict):
            continue
        m = _re.search(r"\d+(?:[.,]\d+)?", str(s.get("value", "")))
        num = float(m.group().replace(",", ".")) if m else 0.0
        parsed.append((num, s.get("value", ""), s.get("label", "")))
    if not parsed:
        return ""
    mx = max((n for n, _, _ in parsed), default=0) or 1
    rows = "".join(
        f'<div class="bm-row"><div class="bm-bar" style="width:{max(6.0, 40*n/mx):.0f}mm"></div>'
        f'<div class="bm-label">{_esc(lab)} · {_esc(val)}</div></div>'
        for n, val, lab in parsed)
    return f'<div class="bar-mini">{rows}</div>'

# ---- horizontal_flow (ST-22) ----
HORIZONTAL_FLOW_CSS = """
.hflow { display:flex; align-items:stretch; }
.hflow .hf-step { flex:1; padding:4mm 3mm; }
.hflow .hf-arrow { flex:0 0 auto; align-self:center; color:var(--brand-accent); font-size:16pt; font-weight:800; }
.hflow .hf-num { font-family:'Montserrat',sans-serif; font-weight:800; font-size:16pt; color:var(--brand-accent); line-height:1; }
.hflow .hf-title { font-family:'Montserrat',sans-serif; font-weight:700; font-size:9.5pt; color:var(--brand-primary); margin:2mm 0 1mm 0; }
.hflow .hf-body p { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:8pt; line-height:1.35; color:#333; margin:0; }
.hflow .hf-dauer { font-family:'Montserrat',sans-serif; font-weight:600; font-size:7pt; letter-spacing:0.06em; text-transform:uppercase; color:var(--brand-neutral-mid); margin-top:1.5mm; }
"""
def horizontal_flow(steps) -> str:
    nodes = []
    for i, st in enumerate(steps or [], start=1):
        if isinstance(st, dict):
            n, title, body, dauer = st.get("n", i), st.get("title", ""), st.get("body", ""), st.get("dauer", "")
        else:
            n, title, body, dauer = i, "", str(st), ""
        title_html = f'<div class="hf-title">{_esc(title)}</div>' if title else ""
        dauer_html = f'<div class="hf-dauer">{_esc(dauer)}</div>' if dauer else ""
        body_html = preprocess_body(body)
        nodes.append(
            f'<div class="hf-step"><div class="hf-num">{_esc(n)}</div>'
            f'{title_html}<div class="hf-body">{body_html}</div>{dauer_html}</div>')
    return f'<div class="hflow">{"<div class=\"hf-arrow\">&rarr;</div>".join(nodes)}</div>' if nodes else ""
```

- [ ] **Step 3b: Implement the three patterns** (first-pass; Task 9 tunes).

`patterns/st_05.py`:
```python
"""ST-05 About — body + stat panel + partner row + credibility (P-3)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from preprocess import preprocess_body  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402
from patterns import _components as C  # noqa: E402

def render(page: dict, ctx: RenderContext) -> PageFragment:
    d = page.get("data") or {}
    title = d.get("title", "")
    body = preprocess_body(d.get("body", ""))
    stats = C.stat_strip(d.get("stats"))
    partners = d.get("partners") or []
    cred = d.get("credibility_points") or []
    partners_html = ""
    if partners:
        chips = "".join(f'<span class="ab-partner">{C._esc(p)}</span>' for p in partners)
        partners_html = f'<div class="ab-partners"><div class="ab-label">BEKANNT AUS</div>{chips}</div>'
    cred_html = ""
    if cred:
        lis = "".join(f"<li>{C._esc(c)}</li>" for c in cred)
        cred_html = f'<ul class="ab-cred">{lis}</ul>'
    stats_panel = f'<div class="ab-stats"><div class="ab-label-light">APEX IN ZAHLEN</div>{stats}</div>' if stats else ""
    headline_html = f'<h1 class="ab-headline">{C._esc(title)}</h1>' if title else ""
    html = (f'<div class="st-05-wrap">{headline_html}'
            f'<div class="ab-cols"><div class="ab-main">{body}{cred_html}{partners_html}</div>'
            f'<div class="ab-side">{stats_panel}</div></div></div>')
    css = C.STAT_STRIP_CSS + """
.st-05 .ab-headline { font-family:'Montserrat',sans-serif; font-weight:800; font-size:23pt; color:var(--brand-primary); line-height:1.12; margin:0 0 5mm 0; }
.st-05 .ab-cols { display:flex; gap:7mm; }
.st-05 .ab-main { flex:1.7; }
.st-05 .ab-side { flex:1; }
.st-05 .ab-main p { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:9.5pt; line-height:1.5; color:#333; margin:0 0 3mm 0; text-align:justify; hyphens:auto; }
.st-05 .ab-cred { margin:4mm 0; padding-left:5mm; }
.st-05 .ab-cred li { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:9.5pt; color:#333; margin:0 0 1.5mm 0; }
.st-05 .ab-partners { margin-top:5mm; }
.st-05 .ab-label { font-family:'Montserrat',sans-serif; font-weight:700; font-size:8pt; letter-spacing:0.15em; color:var(--brand-accent); margin-bottom:2mm; }
.st-05 .ab-partner { display:inline-block; font-family:'Montserrat',sans-serif; font-weight:600; font-size:9pt; color:var(--brand-primary); margin:0 4mm 2mm 0; }
.st-05 .ab-stats { background:var(--brand-primary); padding:6mm; }
.st-05 .ab-label-light { font-family:'Montserrat',sans-serif; font-weight:700; font-size:8pt; letter-spacing:0.15em; color:#fff; margin-bottom:3mm; }
.st-05 .ab-stats .stat-strip-c { flex-direction:column; gap:4mm; }
.st-05 .ab-stats .ssc-label { color:rgba(255,255,255,0.85); }
"""
    return PageFragment(html=html, css=css)
```

`patterns/st_22.py`:
```python
"""ST-22 Collaboration — intro + horizontal connector flow (P-10/P-13)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from preprocess import preprocess_body  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402
from patterns import _components as C  # noqa: E402

def render(page: dict, ctx: RenderContext) -> PageFragment:
    d = page.get("data") or {}
    title = d.get("title", "")
    body = preprocess_body(d.get("body", ""))
    flow = C.horizontal_flow(d.get("steps"))
    headline_html = f'<h1 class="co-headline">{C._esc(title)}</h1>' if title else ""
    intro_html = f'<div class="co-intro">{body}</div>' if body else ""
    html = (f'<div class="st-22-wrap">{headline_html}{intro_html}'
            f'<div class="co-flow">{flow}</div></div>')
    css = C.HORIZONTAL_FLOW_CSS + """
.st-22 .co-headline { font-family:'Montserrat',sans-serif; font-weight:800; font-size:23pt; color:var(--brand-primary); line-height:1.12; margin:0 0 4mm 0; }
.st-22 .co-intro p { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:10pt; line-height:1.45; color:#333; margin:0 0 6mm 0; }
.st-22 .co-flow { margin-top:4mm; }
.st-22 .hflow .hf-step { border-top:1mm solid var(--brand-accent); }
"""
    return PageFragment(html=html, css=css)
```

`patterns/st_01.py`:
```python
"""ST-01 Cover — full-bleed hero + kicker pills + inclusions/proof column + title/author (P-1)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from preprocess import preprocess_body  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402
from patterns import _components as C  # noqa: E402

def render(page: dict, ctx: RenderContext) -> PageFragment:
    d = page.get("data") or {}
    # hero background asset (image_type background) if present
    hero_uri = None
    for a in (page.get("assets") or []):
        if a.get("image_type") == "background" and a.get("path"):
            p = ctx.resolve_asset(a["path"])
            if p is not None:
                hero_uri = p.as_uri()
                break
    # Background goes ON THE BLOCK (WeasyPrint won't paint an abspos inset:0 child).
    # Multi-background: dark overlay gradient ON TOP of the hero image for text legibility.
    bg_style = (f' style="background-image:linear-gradient(180deg,rgba(15,15,31,0.20),rgba(15,15,31,0.70)),url(\'{hero_uri}\')"'
                if hero_uri else "")
    pills = "".join(f'<span class="cv-pill">{C._esc(k)}</span>' for k in (d.get("kicker_pills") or []))
    pills_html = f'<div class="cv-pills">{pills}</div>' if pills else ""
    incl = d.get("inclusions") or []
    incl_html = ""
    if incl:
        lis = "".join(f"<li>{C._esc(x)}</li>" for x in incl)
        incl_html = f'<div class="cv-incl"><div class="cv-incl-label">INKLUSIVE IM REPORT</div><ul>{lis}</ul>{C.bar_mini(d.get("proof_stats"))}</div>'
    teasers = d.get("teaser_items") or []
    teasers_html = ""
    if teasers:
        lis = "".join(f"<li>{C._esc(t)}</li>" for t in teasers)
        teasers_html = f'<div class="cv-teasers"><div class="cv-incl-label">DU LERNST</div><ol>{lis}</ol></div>'
    author = d.get("author") or {}
    author_html = ""
    if author.get("name"):
        role = f' · {C._esc(author.get("role",""))}' if author.get("role") else ""
        author_html = f'<div class="cv-author">{C._esc(author["name"])}{role}</div>'
    title = d.get("title", "")
    subtitle = d.get("subtitle", "")
    title_html = f'<h1 class="cv-title">{C._esc(title)}</h1>' if title else ""
    subtitle_html = f'<div class="cv-subtitle">{C._esc(subtitle)}</div>' if subtitle else ""
    wordmark = C._esc(ctx.brand.company_name_short)
    html = (f'<div class="cv-page"{bg_style}>'
            f'<div class="cv-content">'
            f'<div class="cv-top"><div class="cv-wordmark">{wordmark}</div>{pills_html}</div>'
            f'<div class="cv-side">{incl_html}{teasers_html}</div>'
            f'<div class="cv-bottom">{title_html}{subtitle_html}{author_html}</div>'
            f'</div></div>')
    css = C.BAR_MINI_CSS + """
.st-01 .cv-page { position:relative; min-height:232mm; background-color:var(--brand-primary); background-size:cover; background-position:center; }
.st-01 .cv-content { position:relative; z-index:1; min-height:232mm; display:flex; flex-direction:column; }
.st-01 .cv-top { display:flex; justify-content:space-between; align-items:flex-start; }
.st-01 .cv-wordmark { font-family:'Montserrat',sans-serif; font-weight:700; font-size:10pt; color:#fff; letter-spacing:0.04em; }
.st-01 .cv-pills { text-align:right; }
.st-01 .cv-pill { display:inline-block; border:0.3mm solid var(--brand-accent); color:var(--brand-accent); font-family:'Montserrat',sans-serif; font-weight:700; font-size:7pt; letter-spacing:0.1em; padding:1.5mm 3mm; margin:0 0 1.5mm 1.5mm; }
.st-01 .cv-side { margin-top:8mm; max-width:78mm; align-self:flex-end; background:rgba(15,15,31,0.55); padding:5mm; }
.st-01 .cv-incl-label { font-family:'Montserrat',sans-serif; font-weight:700; font-size:8pt; letter-spacing:0.15em; color:var(--brand-accent); margin:0 0 2mm 0; }
.st-01 .cv-incl ul, .st-01 .cv-teasers ol { margin:0 0 3mm 0; padding-left:5mm; }
.st-01 .cv-incl li, .st-01 .cv-teasers li { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:8.5pt; line-height:1.35; color:#fff; margin:0 0 1.5mm 0; }
.st-01 .cv-teasers { margin-top:4mm; }
.st-01 .cv-bottom { margin-top:auto; }
.st-01 .cv-title { font-family:'Montserrat',sans-serif; font-weight:800; font-size:34pt; line-height:1.04; color:#fff; letter-spacing:-0.02em; margin:0 0 4mm 0; max-width:150mm; }
.st-01 .cv-subtitle { font-family:'Source Sans 3','Source Sans Pro',sans-serif; font-size:11pt; line-height:1.4; color:rgba(255,255,255,0.9); max-width:140mm; margin:0 0 4mm 0; }
.st-01 .cv-author { font-family:'Montserrat',sans-serif; font-weight:600; font-size:9pt; color:var(--brand-accent); }
"""
    return PageFragment(html=html, css=css)
```

- [ ] **Step 4: Register** in `patterns/__init__.py` — add imports `st_01, st_05, st_22` and entries `"ST-01": st_01.render, "ST-05": st_05.render, "ST-22": st_22.render`. The REGISTRY now has all 12 (+ ST-07A) = 13 ST types.

- [ ] **Step 5: Run — expect PASS**

Run: `… && python -m pytest tests/test_render_r2.py -k "stat_bar_flow or st01 or st05 or st22" -q`

- [ ] **Step 6: Verification checkpoint** — `… && python -m pytest tests/ -q` green.

---

## Task 9: Batch 4 fixture enrichment + visual-verify

**Files:** Modify `fixtures/apex/report_content.json` (slot 1 = ST-01, slot 3 = ST-05, slot 19 = ST-22) + `image_map.json` if a cover hero slot id differs.

- [ ] **Step 1: Enrich the three pages** from `content for apex.md` + the reference PDF p1/p3:
  - **Slot 1 (ST-01):** add `kicker_pills` (3-4 short topic tags inferred from the cover/inclusions, e.g. "PROZESSAUTOMATISIERUNG", "AI-AGENTEN", "B2B"), `inclusions` (the case-study/INKLUSIVE bullets), `proof_stats` (`[{"value":"100+","label":"AI-Projekte"},{"value":"30-50%","label":"Kostensenkung"}]` from the ABOUT credibility points), `teaser_items` (= the existing `teaser_bullets`), `author` (`{"name":"Jousef","role":"Gründer, APEX Consulting"}` from the ABOUT section). Keep `title`/`subtitle`. Confirm slot 1 still carries the `cover_hero` background asset (it does from R1/image_map).
  - **Slot 3 (ST-05):** add `stats` (`[{"value":"100+","label":"AI-Projekte"},{"value":"€200k+","label":"Einsparung/Jahr"},{"value":"30-50%","label":"Betriebskosten"}]` from CREDIBILITY POINTS), `partners` (the client names: "Frese Recruiting","Conesso GmbH","Pure Media Marketing"). Keep `body`/`credibility_points`.
  - **Slot 19 (ST-22):** convert the COLLABORATION SCHRITTE into `steps` = `[{"n":1,"title":<step name>,"body":<short paragraph>,"dauer":<the (N Tage) value>}]` for the 5 steps. Keep `title`/`body`.

- [ ] **Step 2: Regenerate** (pre-processor venv): `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python ../v7-renderer/fixtures/apex/build_package.py` → `pages=20 st07a=5 …`, no AssertionError.

- [ ] **Step 3: Render + visual-verify** — `python render.py`; dispatch a visual reviewer with `output/report-p1.png` (cover), `-p3.png` (about), `-p19.png` (collaboration) vs. reference PDF p1/p3 + the collaboration page. Confirm: cover has hero bg + kicker pills + inclusions/proof column + big title + author over a legible overlay; about has the dark stat panel + partner row; ST-22 is a horizontal connector flow. **Tune the `.st-01/.st-05/.st-22` CSS until they match the reference and nothing overflows** (cover title size, overlay strength, column widths, flow node spacing are the usual knobs).

- [ ] **Step 4: Checkpoint** — `… && python -m pytest tests/ -q` green; render shows no overflow for slots 1/3/19.

---

## Task 10: Final integration — full render, full visual-verify, both suites

**Files:** none new — this is the whole-report verification gate.

- [ ] **Step 1: Confirm REGISTRY is complete** — `patterns/__init__.py` maps all 13 ST types (ST-01, 02, 03, 05, 06, 07A, 07B, 08, 09, 14, 22, 31, 32, FAZIT). `get_renderer` returns `_generic` only for truly unknown types. Quick check:
```
cd /Users/utkarsh/Projects/richard/research/v7-renderer && source .venv/bin/activate && python -c "from patterns import REGISTRY; print(sorted(REGISTRY))"
```
Expected: every ST type above present.

- [ ] **Step 2: Full apex render** — `python render.py` → `logical pages: 20`, `accent_budget_passed: True`, **no overflow** on any slot (if any remains, tune that pattern's CSS), no warnings (no pattern fell back to `_generic`).

- [ ] **Step 3: Whole-report visual-verify** — dispatch a reviewer with ALL 20 `output/report-p*.png` and the full `APEX - KI DMC Report v1 (1).pdf`; ask for a page-by-page layout-language match verdict + a list of any page that still reads as generic/skeleton or off-brand. Fix any flagged page (CSS or fixture data) and re-render. Repeat until every page reads as a faithful, on-brand match.

- [ ] **Step 4: Full renderer suite** — `… && python -m pytest tests/ -q` → all green (26 R1 + all R2 unit tests), including `test_no_coral_in_chassis_logic`.

- [ ] **Step 5: Full pre-processor suite** — `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python -m pytest tests/ -q` → 220 green, including `test_no_client_name_in_preprocessor_logic`.

- [ ] **Step 6: Success-criteria sign-off** — confirm against the spec §12: all 12 patterns implemented + registered; apex images placed where layouts call for imagery; every page a faithful match; no overflow; both suites + guards green; chassis stays brand-agnostic + deterministic. Only now surface `report.pdf` to the user.

---

## Self-Review (planner checklist — completed)

**1. Spec coverage:** §4 components → Tasks 1/6/8 (all 7 built); §5 data contract → consumed by the 12 patterns (Tasks 2/4/6/8) + enriched in fixture (Tasks 3/5/7/9); §6 per-pattern layouts → one task each, all 12 covered (ST-01/02/03/05/06/07B/08/09/14/22/31/32/FAZIT); §7 anti-patterns/accent → components + patterns use `var(--brand-*)`, gated rounded corners, accent at §3.7 spots; §8 verification → unit tests every task + per-batch visual loop (Tasks 3/5/7/9) + whole-report loop (Task 10); §9 batches → Tasks grouped exactly; §10 enrichment → Tasks 3/5/7/9; §11 module layout → matches; §12 success → Task 10 Step 6.

**2. Placeholder scan:** No "TBD"/"implement later". First-pass CSS is complete + runnable; the visual-verify loop is an explicit, targeted task (against named reference pages), not a placeholder. The only transcription steps (fixture enrichment) reference the in-repo `content for apex.md` with exact schemas + examples.

**3. Type consistency:** every pattern is `render(page, ctx) -> PageFragment`; components return `str` with paired `*_CSS` constants of matching names (`NUMBERED_BLOCK_CSS`, `NUMBERED_STEP_CARD_CSS`, `DARK_CTA_PANEL_CSS`, `STAT_STRIP_CSS`, `BAR_MINI_CSS`, `HORIZONTAL_FLOW_CSS`); `_components.qr_svg` shared by st_07a (Task 1 Step 5); `REGISTRY` extended additively each batch; section-class scoping (`.st-XX` / unique `.br-page`) uniform per R-3.

**4. Open-loop checks:** breathing-asset reachability solved by mapping assets onto breathing slots in `image_map.json` (Task 7), not by adding report_assets plumbing; ST-32 reuses ST-31's render (no duplication); ST-08 has no apex page → synthetic-verified (Task 4) per the full-library decision; the `@page`/CSS-dedup/inline-dynamic rules (R-2/R-3/R-4) are restated as hard rules so no pattern leaks head CSS or bleeds across pages.

---

## Execution Handoff

Execute with **superpowers:subagent-driven-development** (fresh opus subagent per task; I review between tasks). No git in this repo — pytest + the per-batch visual-fidelity loop are the gates. Batches are sequential (1→4) then Task 10; the visual loop after each batch is where final CSS fidelity is achieved, and `report.pdf` is shown to the user only after Task 10 passes.
