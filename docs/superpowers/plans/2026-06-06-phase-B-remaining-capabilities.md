# Phase B-remaining (Renderer Capabilities & Wiring) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (fresh implementer + spec-review + code-quality-review per task). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Wire the produced-but-dropped visuals and built-but-off layouts back into the deck (grounds, fill defaults, social-proof, fazit bg, builder-SVG head-reader) + remove the case-study QR — without regressing the 198-green suite or the 21-page budget.

**Architecture:** Surgical per-item renderer wiring (new `RenderContext` helpers + `.st-XX`-scoped CSS + one `components/*.jinja` macro) + one preprocessor toggle (`plan_layout.FILL_DEFAULT_TYPES`) + fixture re-bake/enrichment. Every consumer degrades gracefully to today's rendering when its data is absent.

**Tech Stack:** WeasyPrint (HTML/CSS→PDF), Jinja2 macros, DTCG tokens, pytest. Renderer venv (`DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`); preprocessor venv for the re-bake. NO git.

**Spec:** `docs/superpowers/specs/2026-06-06-phase-B-remaining-capabilities-design.md` (§11 gap-audit is binding).

**Sequence (independent, by verifiability):** F → E → A → D → C → B-renderer → follow-up. Suite green + page-count/overflow checked after each.

**Standing verification after EVERY package-affecting task:**
```
cd research/v7-renderer && source .venv/bin/activate && export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
python render.py && python -c "import fitz; assert len(fitz.open('output/report.pdf'))==21, len(fitz.open('output/report.pdf'))"
python -c "from assembler import render_package; from pathlib import Path; import tempfile; print(render_package(Path('fixtures/apex'), Path(tempfile.mkdtemp())).overflow)"
# expect: ['slot 15 (ST-07A) overflow']  (no NEW slot)
python -m pytest tests/ -q   # expect 0 failed
```
Re-bake fixture (preprocessor venv) when a task changes the package:
```
cd research/preprocessor && .venv/bin/python ../v7-renderer/fixtures/apex/build_package.py   # must print pages=20 ... and exit 0
```

---

### Task F: Remove QR from case studies (ST-07A); keep ST-03

**Files:**
- Modify: `research/v7-renderer/patterns/st_07a.py` (QR generation ~line 162-166, pass-through ~line 252)
- Test: `research/v7-renderer/tests/test_st07a_fill_variant.py` (asserts QR present → assert ABSENT) + a keep-guard for ST-03
- Reference (DO NOT change): `research/v7-renderer/patterns/st_03.py` (QR stays)

- [ ] **Step 1 — failing test:** in `test_st07a_fill_variant.py`, change/add an assertion that the rendered ST-07A fill HTML contains **no** `cs-panel-qr` element (and no `<svg` QR). Add/confirm a test that ST-03 render still contains its QR markup. Run → fails (QR currently present).
- [ ] **Step 2 — implement:** in `st_07a.py`, stop building/passing the QR: set `qr_svg=""` to the template (remove the `_qr_svg(...)` call for ST-07A). Leave `st_03.py` untouched.
- [ ] **Step 3 — verify:** run `pytest tests/test_st07a_fill_variant.py tests/test_render_r2.py -q` → pass. Run the standing verification block → 21 pages, no new overflow, suite green.
- [ ] **Step 4 — PIXEL:** render; view a case-study page (fill) + ST-03 — QR gone from the case study, panel foot still anchored by the pull-quote (no dead space), ST-03 QR intact. Compare to Richard (case studies have no QR; the CTA page does).

### Task E: Fill default for ST-07B / ST-22 / ST-FAZIT (+ re-bake + un-xfail)

**Files:**
- Modify: `research/preprocessor/stages/plan_layout.py` (`FILL_DEFAULT_TYPES` frozenset)
- Modify: `research/v7-renderer/fixtures/apex/build_package.py` (assertion lines ~151-153)
- Test: the ST-07B dead-space fill tests currently `xpassed` (un-xfail → real); re-check ST-22/ST-FAZIT fill tests
- Re-bake: `fixtures/apex/resolved_package.json`

- [ ] **Step 1 — failing test:** add/adjust a `plan_layout` unit test asserting ST-07B/ST-22/ST-FAZIT now resolve `layout_variant="fill"` (and ST-07A still does; an unrelated type still resolves None). Run → fails.
- [ ] **Step 2 — implement (preprocessor):** `FILL_DEFAULT_TYPES = frozenset({"ST-07A","ST-07B","ST-22","ST-FAZIT"})`. Run the plan_layout test → pass; run preprocessor suite for plan_layout/assemble → green.
- [ ] **Step 3 — update fixture assertion FIRST (gap-audit #1):** in `build_package.py`, replace the "non-ST-07A carries no layout_variant" assertion with: every ST-07A/07B/22/FAZIT page carries `layout_variant=="fill"`; no OTHER type carries one.
- [ ] **Step 4 — re-bake:** `cd research/preprocessor && .venv/bin/python ../v7-renderer/fixtures/apex/build_package.py` → exit 0, pages=20.
- [ ] **Step 5 — CRITICAL verify (gap-audit #2):** standing verification block → **page count == 21 AND overflow gains NO new slot**. If a newly-filled ST-07B/22/FAZIT page overflows, STOP and tighten that pattern's fill CSS (`.st-XX`-scoped, reflow-style) until it fits; do NOT proceed with an overflow.
- [ ] **Step 6 — un-xfail:** flip the 2 now-passing ST-07B dead-space tests from `xfail`→ real assertions; re-evaluate ST-22/ST-FAZIT fill dead-space tests (un-xfail if they now pass, else leave with an updated reason). Run renderer suite → 0 failed, fewer xfails.
- [ ] **Step 7 — PIXEL:** view ST-07B, ST-22, ST-FAZIT — full-height authority panels, dead bottom bands GONE. Compare to Richard.

### Task A: Background/texture grounds on content pages

**Files:**
- Modify: `research/v7-renderer/assembler.py` (emit `data-texture` attribute; ground CSS for content pages) and/or `tokens/compile_tokens.py` (data_attrs)
- Modify content patterns + their `.st-XX` CSS: `patterns/st_05.py`+`styles/st_05.css`, `st_09`, `st_14`, `st_06` (add scoped ground)
- Test: `tests/test_render_r2.py` (assert ground img/attr present when asset resolves; absent/flat when not) + a `data-texture` emit test

- [ ] **Step 1 — failing test:** assert `<html ... data-texture="...">` is emitted from the resolved texture axis; assert a content page (e.g. ST-09) embeds the report-ground URI when `report_assets` carries it, and renders the flat token ground when it doesn't (graceful). Run → fails.
- [ ] **Step 2 — implement data-texture:** emit `data-texture={resolved texture axis}` on `<html>` (compile_tokens data_attrs / assembler). Confirm existing `[data-texture]` selectors apply.
- [ ] **Step 3 — implement grounds:** in ST-05/09/14/06 patterns, resolve a report ground via `ctx.resolve_report_asset((...),(...))` and render it as a full-bleed BEHIND-content layer at low opacity, gated on `data-ground-mode` (dark panels keep solid). `.st-XX`-scoped CSS. Graceful when None.
- [ ] **Step 4 — verify:** standing block → 21 pages, no new overflow, suite green. Contrast not regressed (no text over the ground).
- [ ] **Step 5 — PIXEL (gap-audit #4/#7):** view ST-05/09/14/06 — atmospheric ground reads richer, NOT noisier; text fully legible; each `[data-texture]` effect looks right (scope the selector if a texture reads wrong on a page type). Compare to Richard.

### Task D: fazit_background ground on ST-FAZIT

**Files:**
- Modify: `research/v7-renderer/patterns/st_fazit.py` (+ `templates/st_fazit.html.jinja`, `styles/st_fazit.css`)
- Test: `tests/` fazit test — ground present when asset resolves, graceful when not

- [ ] **Step 1 — failing test:** assert st_fazit embeds a background URI from `page["assets"]` (slot `fazit_background`/type `background`) else from `report_assets`; graceful None → text-only. Run → fails.
- [ ] **Step 2 — implement:** `_background_uri(page, ctx)` mirroring `st_31`; full-bleed ground under the closing statement; text on a legible scrim/panel. `.st-fazit`-scoped CSS.
- [ ] **Step 3 — verify:** standing block → 21 pages, no new overflow, suite green.
- [ ] **Step 4 — PIXEL:** view ST-FAZIT (now fill from Task E + ground) — reads as a designed finale, text legible over the ground. Compare to Richard.

### Task C: social_proof component (helper + macro + ST-09 host + fixture enrichment)

**Files:**
- Modify: `research/v7-renderer/patterns/base.py` (`RenderContext.social_proof(page)`)
- Create: `research/v7-renderer/components/social_proof.jinja` (token-only macro)
- Modify: `patterns/st_09.py` (+ `templates/st_09.html.jinja`, `styles/st_09.css`) to host the band
- Modify (fixture enrichment): `fixtures/apex/report_content.json` (add a representative social-proof block — labelled TEST data) + re-bake
- Test: `test_render_r2.py` (helper returns the dict; band renders when present, absent when not; guard tests pass)

- [ ] **Step 1 — failing test:** assert `RenderContext.social_proof(page)` returns the dict (or None graceful); assert ST-09 renders the social-proof band when present and renders unchanged when absent. Run → fails.
- [ ] **Step 2 — helper:** add `social_proof(page)` to `RenderContext` (mirror `slot_uri` graceful style).
- [ ] **Step 3 — macro:** `components/social_proof.jinja` — quote + attribution (+ optional stat), `var(--*)` tokens only (must pass `test_no_literals_in_architecture`). NEVER invents content.
- [ ] **Step 4 — host:** wire the macro into `st_09` (render band when `ctx.social_proof(page)`); `.st-09`-scoped CSS.
- [ ] **Step 5 — fixture enrichment + re-bake:** add a representative social-proof block to apex ST-09 content (clearly fixture test data); re-bake; standing block → 21 pages, no new overflow.
- [ ] **Step 6 — verify + PIXEL:** suite green; view ST-09 — credibility band reads like real social proof, on-brand, legible. Compare to Richard.

### Task B-renderer: ST-builder infographic head-reader (renderer half only)

**Files:**
- Modify: `research/v7-renderer/patterns/base.py` (`RenderContext.st_components(page)`)
- Modify: `patterns/st_06.py`, `st_09.py`, `st_14.py` (+ their CSS) to embed a builder SVG when present
- Test: `test_render_r2.py` with a SYNTHETIC builder component on an enriched fixture page

- [ ] **Step 1 — failing test:** assert `st_components(page)` returns the component HEAD (`comps[:-n]` where n = len(charts), else all), graceful `[]`; assert ST-09/ST-14/ST-06 embed a builder SVG when one is present (synthetic component injected), unchanged when absent. Run → fails.
- [ ] **Step 2 — helper:** add `st_components(page)` to `RenderContext` (mirror `chart_svgs`: read `components`, slice the head, resolve each via `resolve_component`, graceful `[]`).
- [ ] **Step 3 — embed:** in ST-06/09/14, render the first builder SVG in a dedicated `.st-XX`-scoped figure band when present; unchanged when absent.
- [ ] **Step 4 — verify:** suite green; standing block → 21 pages, no new overflow. (Apex renders no builders today, so the deck is visually unchanged — that's expected; the head-reader is proven by the synthetic-component test.)
- [ ] **Step 5 — flag:** record in the phase checkpoint that **B-renderer DONE / B-generation (preprocessor content→infographic mapping) → Phase C** (gap-audit #3). Do NOT claim infographics now render on apex.

### Task FU: ST-06 floated stat clip (follow-up, if cheap)

**Files:** `research/v7-renderer/styles/st_06.css` (+ pattern if needed)
- [ ] **Step 1:** render ST-06; check the `30-50%` stat for clipping at canon type.
- [ ] **Step 2:** if clipping, widen the cell / apply the `_is_long_value` stat path (`.st-06`-scoped); re-verify pixel. If not clipping, note resolved. Suite green.

### Final: phase-boundary checkpoint
- [ ] Full deck render; **page count == 21, overflow == ['slot 15 (ST-07A) overflow']** (no new slot); both suites green; xfail count reduced.
- [ ] Dispatch a final code-reviewer over the whole diff (brand-agnostic guards, graceful fallbacks, no fabrication).
- [ ] Update `context.md`: Phase B-remaining status (items A/D/E/F/C DONE + pixel-verified; B-renderer DONE, B-generation → Phase C); new test counts; pointer to this spec/plan.
- [ ] Honest checkpoint to the user with pixel proof + residuals (Hanisch copy-fit still pending → next task).

## Self-review (against spec)
- Spec coverage: A→Task A; B(renderer)→Task B-renderer (generation→Phase C, flagged); C→Task C; D→Task D; E→Task E; F→Task F; ST-06 clip→Task FU; gap-audit CRIT #1/#2 → Task E Steps 3/5; #3 → Task B-renderer Step 5; #4/#7 → Task A Step 5; #5 → Task C; #6 → Task F Step 4. ✓
- Placeholder scan: none. ✓
- Type consistency: helpers `st_components`/`social_proof` mirror existing `chart_svgs`/`slot_uri` graceful conventions; `FILL_DEFAULT_TYPES` is the exact existing symbol. ✓
