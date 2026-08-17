# Renderer Phase R1 — Foundation (Design / PRD)

**Status:** Approved — ready for implementation planning
**Date:** 2026-05-29
**Component:** `research/v7-renderer/` (Layer 2 chassis) + one additive change to `research/preprocessor/`
**Predecessor analysis:** `docs/superpowers/specs/2026-05-29-renderer-scope-analysis.md`

**Verified against code (2026-05-29):** `st_07a` declares `@font-face` / `:root` / `@page` (movable to the shared head ✓) and reads keys `kurzportraet / ausgangsproblem / ziel / loesung / ergebnis_text / pullquote{text,attribution} / kunde{name,funktion,company_url} / ergebnis_metrics / fallstudie_number / ergebnis_headline` (§7 corrected to match ✓); `tests/test_chassis_contract.py` imports none of `render.py` / `st_07a` / `render_lrp` (refactor-safe ✓); the apex package `brand` block has all 10 `parse_brand_tokens` keys ✓ and pages lack `page_numbers` (upstream add is real ✓). The current `fixtures/apex` package is the SAMPLE page structure — R1 regenerates it from the apex content (§7).

## 1. Goal

Wire the renderer to consume the pre-processor's `resolved_package.json` and emit a **working multi-page apex PDF**: case-study pages rendered real (via the refactored `st_07a`), every other page rendered as a clean **brand-styled skeleton**, all driven by the package + the apex content. This closes every contract open-loop end-to-end. The 12 specific ST patterns are **Phase R2** (separate cycle).

**Approved decisions:** (1) patterns **return their own CSS** (assembler collects it); (2) **one A4 page per package page** — facing-page spreads (`§S` axis) deferred to R2+; (3) graceful error handling (never crash; always emit a PDF).

## 2. The pattern interface (keystone)

```python
# patterns/base.py  (new)
@dataclass(frozen=True)
class PageFragment:
    html: str   # the page's body markup (goes inside one .page container)
    css: str    # pattern-scoped CSS (collected once into the shared <head>)

@dataclass(frozen=True)
class RenderContext:
    brand: BrandConfig
    grammar: Grammar
    package_dir: Path
    def resolve_asset(self, rel: Optional[str]) -> Optional[Path]: ...   # package_dir/rel if exists else None
    def resolve_component(self, rel: Optional[str]) -> Optional[str]: ... # read SVG text if exists else None

# Every pattern module exposes EXACTLY:
def render(page: dict, ctx: RenderContext) -> PageFragment: ...
```
`page` is one package page dict: `{slot, st_type, css_template, has_cta, data, assets, components, cover_validation, page_numbers}`.

**Dispatch registry** (`patterns/__init__.py`): `{ "ST-07A": st_07a.render }`, default → `_generic.render`. R2 adds the rest.

## 3. Assembler + shared head

```python
# assembler.py (new)
@dataclass
class RenderResult:
    pdf_path: Path
    png_paths: list[Path]
    page_count: int
    overflow: list[str]        # per-page overflow flags (advisory)
    accent_budget_passed: bool
    warnings: list[str]        # render-time fallbacks/skips

def render_package(package_dir: Path, output_dir: Path) -> RenderResult: ...
```
Flow: `load_package()` → for each page dispatch → `PageFragment` → assemble ONE document:
```
<html lang="de"><head><style>
  {SHARED_HEAD_CSS(brand, font_dir)}          # @page A4 + 3mm bleed + margins + @bottom-left folio;
                                              # @font-face ×4; :root brand CSS-vars; body #333 Blocksatz hyphens
  {deduped concatenation of every fragment.css}
</style></head><body>
  {for each page: <div class="page st-XX">{fragment.html}</div>  with break-after:page}
</body></html>
```
→ WeasyPrint `write_pdf` → PyMuPDF rasterize PNGs → run overflow + accent-budget validators.

**Shared head CSS** owns the cross-page rules (moved out of `st_07a`): `@page` (A4, 3mm bleed, margins T16/O14/B20/I18 per CHASSIS-NOTES, `@bottom-left` folio = `page_numbers`), `@font-face` for the 4 variable fonts (path resolved: package `fonts/` if present else chassis `fonts/`), `:root { --brand-primary … }` from BrandConfig, `body { color:#333; font-family:'Source Sans 3'…; line-height:1.42; text-align:justify; hyphens:auto }`, `.page { … }`, `break-after:page`.

## 4. package_loader.py (new)

```python
@dataclass
class LoadedPackage:
    brand: BrandConfig
    pages: list[dict]           # package pages incl. page_numbers
    report_assets: list[dict]
    fonts: dict
    package_dir: Path

def load_package(package_dir: Path) -> LoadedPackage: ...
```
Reads `resolved_package.json`; `parse_brand_tokens(pkg["brand"])` (exact match — no change to brand_tokens.py); resolves font paths (package `fonts/` → else chassis `fonts/`); returns pages verbatim (relative asset/component paths resolved lazily by `RenderContext`). FAIL-LOUD if `resolved_package.json` missing or `brand` incomplete (reuses `parse_brand_tokens` ValueError).

## 5. st_07a refactor (full-doc → fragment)

Change `render_lrp(...)` → `render(page, ctx) -> PageFragment`:
- Move `@page` / `@font-face` / `:root` / `body` rules to the shared head (§3); keep `.lrp`, `.rail-photo`, `.pullquote-panel`, `.quote-*` etc. as `fragment.css`.
- `fragment.html` = the existing LRP table body.
- Read content from `page["data"]` per the **ST-07A data contract** (§7). Portrait from `page["assets"]` (`case_study_portrait`) via `ctx.resolve_asset`, else omit the rail photo gracefully. QR from `ctx.brand.qr_target_url`.
- Visual output preserved (same LRP geometry).

## 6. patterns/_generic.py (new) — the R1 skeleton

`render(page, ctx) -> PageFragment` for every not-yet-built ST type. Renders, brand-styled, from whatever `data` is present:
- a **headline** (first of `data.title` / `data.headline` / `data.these` / first string field),
- a **body** (joined prose from `data.body`/`data.intro`/remaining string fields, via `preprocess_body`),
- a folio (via shared head), optional page background (report texture, §8).
- Never assumes specific keys; an empty `data` → a near-empty but valid page. This makes the full multi-page doc coherent in R1.

## 7. Apex content fixture + slot plan + ST-07A data contract

**The current `fixtures/apex/` package is the SAMPLE structure** (mein-werkzeugkoffer: 20 pages, 3× ST-07A, has ST-08/ST-31, no ST-FAZIT) — it carries the apex IMAGES but the wrong page set/data. R1 **regenerates** it from the apex content.

A generator script maps `content for apex.md` → a `report_json`, runs the pre-processor `/render`, and writes the package to `fixtures/apex/`. Existing apex images are reused where slots align (fed back via the image manifest as already-generated); genuinely-missing ones (e.g. `fazit_background`) are regenerated.

**Slot plan / page count.** The apex content has ~17 logical sections (cover, outlook, about, status-quo, false-beliefs, 5× case study, 3× theory, mechanism, summary, collaboration, CTA) and was authored as a **20-page report using doublespreads**. Since R1 collapses spreads to single A4 pages, the generator builds a **valid single-page `report_json`** satisfying Stage 1: `page_count_target ∈ {16,20,24,28}`, slot 1 = ST-01, last = ST-03, ≥3 ST-07A (apex has 5 ✓). **Recommended: a 20-page plan** = the 17 sections as single pages + 3 ST-31 Atemseite breathing pages (spaced per Stage 7 rhythm) to reach 20. Exact sequencing is finalized when the report_json is built — it's our construction, fully under our control.

**ST-07A `data` contract — the ACTUAL keys `st_07a` reads** (verified against the code, not assumed):
```
{ "fallstudie_number": int,
  "ergebnis_headline": str,                              # case title
  "kurzportraet": str,                                   # KURZPORTRÄT (lede)
  "ausgangsproblem": str,                                # AUSGANGSPROBLEM
  "ziel": str,                                           # ← map WENDEPUNKT here (apex has no "Ziel")
  "loesung": str,                                        # LÖSUNG
  "ergebnis_text": str,                                  # ERGEBNIS
  "ergebnis_metrics": [ {...} ],                         # METRIKEN — READ but NOT rendered today
  "pullquote": { "text": str, "attribution": str },     # quote + "— Name"
  "kunde": { "name": str, "funktion": str, "company_url": str } }  # KUNDE
```
**Apex→keys mapping:** KURZPORTRÄT→`kurzportraet`, AUSGANGSPROBLEM→`ausgangsproblem`, WENDEPUNKT→`ziel` (where present, else ""), LÖSUNG→`loesung`, ERGEBNIS→`ergebnis_text`, METRIKEN→`ergebnis_metrics`, quote→`pullquote.text`, "— Name"→`pullquote.attribution`, KUNDE→`kunde.name`/`funktion`.

**Known limitation (R1):** `st_07a` reads `ergebnis_metrics` but renders **no stat block** (lines 205-207 are a placeholder) — so METRIKEN won't display in R1. A small stat-strip is an optional R1 add or deferred to R2. Generic pages get `{ "headline", "body", + any structured lists }`; all patterns degrade gracefully on missing keys.

## 8. Assets, components, report_assets

- `page.assets[].path` → `<img>` / `background-image` (resolve via `ctx.resolve_asset`; missing → skip).
- `page.components[]` → inline SVG (`ctx.resolve_component`; missing → skip).
- `report_assets` texture/gradient → applied as a page background **driven by the `ground_mode` axis** on the brand profile (data-driven; for R1 the generic + cover skeletons may use the texture as a subtle full-page background where ground_mode indicates a textured/light ground). Never hardcoded per client.

## 9. validators/overflow.py (real, replaces stub)

Post-layout truth: for each single-page pattern, render its fragment as a standalone 1-page doc; if WeasyPrint emits **>1 physical page**, the content overflowed → record `f"slot {n} ({st_type}) overflow"`. Advisory (does not block; surfaced in `RenderResult.overflow`), mirroring `accent_budget`. (Per-page render is fine at QA/build time; optimize later.)

## 10. Upstream (Layer 1) — one additive change

Add `page_numbers` to the pre-processor package page manifest: `plan_layout.PlannedPage` gains `page_numbers` (copied from `ReportPage.page_numbers`); `assemble_package` emits it in each page entry. Additive — the 217 pre-processor tests stay green + one new assertion.

## 11. Error handling (never crash; always emit a PDF)

| Failure | Behavior |
|---|---|
| A pattern's `render()` raises | assembler catches → substitutes `_generic` for that page → appends a `warnings` entry |
| Missing asset / component file | `resolve_*` returns None → pattern skips that visual |
| Missing `data` keys | pattern omits those fields (generic renders what's present) |
| Empty package / zero pages | emit a valid empty PDF + a warning |
| WeasyPrint error on a page | isolate: render that page as generic; if still failing, emit a placeholder page + warning |

The render ALWAYS returns a `RenderResult` with a PDF + a `warnings` list; QA reviews warnings out of band.

## 12. Testing

Keep the renderer's **11 contract tests + `test_no_coral` guard** green. Add (renderer venv has WeasyPrint):
- `package_loader`: load `fixtures/apex` → BrandConfig + N pages (+ page_numbers).
- `assembler`: assembled doc has one `.page` container per package page + exactly one shared `<head>`; deduped CSS.
- pattern interface: `st_07a.render(page, ctx)` returns a `PageFragment` (html + css non-empty); `_generic.render` handles full data AND empty `{}`.
- dispatch registry: `ST-07A`→st_07a, unknown→generic.
- `overflow`: a deliberately-overflowing fragment is flagged; a fitting one is not.
- **Integration:** `render_package(fixtures/apex)` → PDF with the expected page count + PNGs (visually inspected).
Pre-processor: additive `page_numbers` test; suite stays green.

## 13. Module layout

```
research/v7-renderer/
  render.py                 # reworked: CLI → render_package(fixtures/apex) (replaces single-page GEVA harness)
  package_loader.py         # NEW
  assembler.py              # NEW (shared head + dispatch + WeasyPrint + validators)
  patterns/
    base.py                 # NEW (PageFragment, RenderContext)
    __init__.py             # NEW dispatch registry
    st_07a.py               # refactor → render(page, ctx) -> PageFragment
    _generic.py             # NEW skeleton/fallback
  validators/overflow.py    # real implementation
  tests/test_render_r1.py   # NEW (loader/assembler/interface/overflow/integration)
research/preprocessor/
  stages/plan_layout.py     # + page_numbers on PlannedPage
  stages/assemble_package.py# + page_numbers in page manifest
  (+ generator: map content for apex.md → report_json → /render → fixtures/apex)
```

## 14. Scope boundaries

**R1 DOES:** package loader, assembler + shared head, pattern interface, `st_07a` refactor, `_generic` skeleton, real `overflow` validator, asset/component/report_asset embedding, apex content fixture, `page_numbers` upstream add, reworked `render.py`.
**R1 does NOT:** the 12 specific ST patterns (R2); facing-page spreads (deferred); real `accent_budget` rasterization (stays stub); whitespace/colour-count/atemseite validators (pre-processor Stage 7 + future); Layer-3 CMYK.

**Success =** `render_package(fixtures/apex)` emits a multi-page RGB PDF (case studies real, others skeleton) with correct page count + folios; renderer 11 contract tests + no-coral guard + the new R1 tests green; pre-processor 217 + page_numbers test green; chassis stays brand-agnostic.
