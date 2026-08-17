# Phase B (part 2) — Renderer Capabilities & Wiring — Design

**Date:** 2026-06-06 · **Status:** spec (gap-audited inline, §11) → plan → subagent build
**Scope:** Wire the *produced-but-dropped* visuals and *built-but-switched-off* layouts back into the rendered deck (gap map Themes 3 + 2 + the QR clean-up). Renderer patterns/templates/CSS + `patterns/base.py` helpers + one preprocessor toggle (`plan_layout.FILL_DEFAULT_TYPES`) + fixture re-bake/enrichment.
**Why:** Phase A (theme-lock) + Phase B-reflow fixed the *substrate* (type, depth, ground, fit). The remaining visual-appeal gap is that several rich elements are *generated/extracted/built and then thrown away* — flat content pages with no textured ground, dead bottom bands on three page types that already implement a "fill" layout, an extracted social-proof block no pattern reads, and a floating QR cluttering every case study. This phase turns those on.

**Predecessor:** `docs/superpowers/specs/2026-06-05-phase-B-reflow-design.md` (part 1, DONE). Gap map: `docs/superpowers/2026-06-05-visual-appeal-gap-map.md` Theme 3 (§"jumbled wiring"), Theme 2 (fill defaults), and the QR item.

---

## 0. Verified current state (ground truth, 2026-06-06 — NOT assumptions)

Renderer suite **198 passed / 0 failed / 4 xfailed / 2 xpassed**. Apex deck = **21 physical pages**; `render_package(...).overflow == ['slot 15 (ST-07A) overflow']` (the Hanisch copy-fit residual, owned by the preprocessor copy-fit task — out of scope here).

Fixture inspection (`fixtures/apex/resolved_package.json` + assets on disk) established the following — these correct three optimistic claims in the gap map and **must drive scoping**:

| Fact (verified) | Consequence |
|---|---|
| `report_assets` carries **real `status:generated`** images on disk: `report_background_texture.png` (1792×2400), `report_atmospheric_gradient.png` (1792×2400), `report_extra_square.png` (2048²), `report_extra_wide.png` (2752×1536), plus a status-quo scene. | Items A (grounds) and D (fazit bg) are **pixel-verifiable in the fixture as-is** — NOT stubs. (The gap map / a source-read called them stubs; the *default* `generate_assets.py` stubs them, but the apex fixture has real pre-baked grounds.) |
| Per-page `components` is **empty on every page except ST-06 (1 = a chart SVG)**. `generate_components_for_report()` on apex content returns components for **slot 16 only**. | Item B's premise ("ST-builder SVGs generated every render, dropped by the renderer") is **false for apex**: the builders are *not generated at all* for this content. Item B is therefore a **preprocessor content→infographic generation** gap first, renderer-slicing second. Rescoped in §6. |
| `social_proof` = **0 occurrences** in `report_content.json`; absent on every package page. | Item C needs **fixture content enrichment** (a representative social-proof block) to be pixel-verifiable. |
| `layout_variant == "fill"` on the 5 ST-07A pages only; ST-07B/ST-22/ST-FAZIT = standard. | Item E is a real, live default-off. |
| `chart_svgs()` reads `comps[-n:]` (the tail = chart SVGs). No helper reads the head. ST-06/ST-07A call `chart_svgs`; ST-09/ST-14 read nothing. | Confirms the renderer-side slice for Item B. |
| `resolve_report_asset(slot_ids, image_types)` exists on `RenderContext` (`patterns/base.py:163`); only `st_31`/`st_22` call it. `[data-ground-mode]` CSS exists in `assembler.py`; `[data-texture]` selectors exist but **no `data-texture` attribute is written to `<html>`** (no consumer). | Item A = add consumer calls to content patterns + emit the `data-texture` attribute. |

**Discipline note:** every claim above was read off the actual package/files/disk, not the gap map. Where the gap map and the artifacts disagreed, the artifacts win.

---

## 1. Goal

Turn ON the built-but-dropped richness so the deck reads like Richard's device-dense editorial spreads, **without** fabricating content, breaking the brand-agnostic guards, regressing the 198-green suite, or pushing the deck past its page budget. Each item is verified by **rendering the full page and comparing the whole composition to Richard** — never "did my edit show up."

Non-goals (explicitly routed elsewhere):
- **Generating** rich builder infographics from arbitrary content (the hard preprocessor content-mapping half of Item B) → **Phase C** (preprocessor data & imagery / brief→layout). This spec wires the renderer to *consume* builder SVGs when present + proves it on an enriched fixture, and honestly flags the generation half.
- **Producing** real textured grounds via fal at print resolution → **Phase C** (imagery). This spec *consumes* the grounds already in the package (real in the fixture) + graceful fallback.
- Hanisch copy-fit / clean-20 → **preprocessor copy-fit task** (next after this phase).

---

## 2. Approach (decision)

**Surgical, per-item, `.st-XX`-scoped renderer wiring + one preprocessor toggle**, mirroring the reflow approach: lowest-risk, preserves canon, touches shared head only where a primitive is genuinely shared. New rendering of dropped data goes through **new `RenderContext` helpers** (so patterns stay declarative and the resolution/graceful-fallback logic is unit-tested once) and **new `.st-XX`-scoped CSS / one new `components/*.jinja` macro**. The preprocessor change is a **single frozenset edit** (`FILL_DEFAULT_TYPES`) plus the fixture re-bake it forces.

NOT: a global theme rewrite (Phase A is done); NOT inventing content (no-fabrication); NOT a generation pipeline (Phase C).

---

## 3. Item A — Background/texture grounds on content pages (Theme 3 High)

**Producer:** `report_assets[]` (real in fixture). **Consumer today:** only `st_31`/`st_22`. **Gap:** the 8 flat content pages never call `resolve_report_asset`; `data-texture` attribute never emitted.

**Change:**
1. New `RenderContext.report_ground_uri(*, slot_ids, image_types)` thin convenience wrapper (or reuse `resolve_report_asset` directly) — already exists; no new helper strictly required.
2. Add a **scoped, low-intensity ground** to content patterns that currently render a flat token ground: candidate set **ST-05, ST-09, ST-14, ST-06** (the text-on-panel pages). The ground is rendered as a **full-bleed `<img>` or CSS `background-image` BEHIND the content at low opacity**, never over text, and **respecting `data-ground-mode`** (light pages get the atmospheric gradient / paper texture; dark/authority panels keep their solid ground). Pixel-verify contrast is not harmed (Phase-A grain already establishes a baseline ground; this adds per-page atmosphere, not noise).
3. **Emit `data-texture`** on `<html>` from the resolved `texture` axis (in `compile_tokens.py` data_attrs / `assembler.py`) so the existing `[data-texture="marble_paper"|"crumpled_paper"]` selectors finally apply. This is **pure CSS treatment, no asset** — independently verifiable.

**Constraint:** the ground must DEGRADE GRACEFULLY to the current flat token ground when no report asset resolves (production decks without grounds must look exactly as they do today). Contrast floor preserved (the quality-loop `min_text_contrast` must not regress).

**Risk:** muddy/over-busy ground or reduced text contrast → mitigated by low opacity + `data-ground-mode` gating + **pixel sign-off** on each touched page vs the current render (must read richer, not noisier).

## 4. Item D — fazit_background (Theme 3 High)

**Gap:** `st_fazit` resolves NO image; `fazit_background` (per-page) / report grounds are available. **Change:** add `_background_uri(page, ctx)` to `st_fazit.py` mirroring `st_31` — check `page["assets"]` for `slot_id="fazit_background"`/`image_type="background"`, else `ctx.resolve_report_asset(("extra_wide","extra_square","atmospheric_gradient"), ("background","scene","gradient"))`; pass to the template as a full-bleed ground under the closing statement (text stays on a legible panel/scrim). Graceful → current text-only fazit when nothing resolves. Pixel-verify the closing page reads as a designed finale, not a muddy photo wash.

## 5. Item E — fill default for ST-07B / ST-22 / ST-FAZIT (Theme 2 Critical)

**Gap:** all three patterns implement+test a "fill" branch (full-height authority panel) that never triggers because `plan_layout.FILL_DEFAULT_TYPES == {"ST-07A"}`.

**Change (preprocessor, 1 line):** `FILL_DEFAULT_TYPES = frozenset({"ST-07A","ST-07B","ST-22","ST-FAZIT"})`. Renderer already reads + clamps `layout_variant`; no renderer change required for the variant to trigger.

**Forced consequences (these ARE the work):**
- **Re-bake `fixtures/apex/resolved_package.json`** via `build_package.py` (preprocessor venv).
- `build_package.py` assertion at **lines 151–153** (`not any("layout_variant" in p for non-ST-07A)`) **WILL BREAK** — must be updated to assert the new fill-default set (ST-07A/07B/22/FAZIT carry `fill`; everything else carries none). (See §11 gap #1.)
- **Un-xfail the 2 now-passing ST-07B dead-space tests** (the 2 current `xpassed`) — they pass because the fill branch now renders; flip `xfail`→ real assertions. Re-evaluate the ST-22/ST-FAZIT dead-space fill tests similarly.
- **VERIFY DECK PAGE COUNT + OVERFLOW do not regress** — fill is full-height and could change pagination or introduce overflow on ST-07B/22/FAZIT. After the re-bake, `len(report.pdf) == 21` (still, pending Hanisch) and `overflow` lists no NEW slot. If a newly-filled page overflows, that is a §11 gap to resolve (tighten that pattern's fill CSS, like the reflow), NOT to ship. (See §11 gap #2.)

## 6. Item B — ST-builder infographics (Theme 3 Critical) — RESCOPED

**Verified:** builders are **not generated** for apex content (only the ST-06 chart). So "recover dropped visuals" splits:
- **B-renderer (IN SCOPE):** add `RenderContext.st_components(page)` returning the **head** of `components` (everything before the last-N chart SVGs: `comps[:-n] if n else comps`), graceful `[]`. Add a consuming region to **ST-06 / ST-09 / ST-14** (the typed patterns the gap map names) that embeds a builder SVG when present (a dedicated figure band), unchanged layout when absent. Unit-test the helper + the embed with a **synthetic builder component** on an enriched fixture page.
- **B-preprocessor (OUT OF SCOPE → Phase C):** make `generate_components_for_report` actually emit process_flow/matrix_2x2/metaphor_split/causality_chain/venn/paired_comparison from typical content. This is a content→infographic *mapping* problem (brief→layout), the heart of Phase C. **Honestly flagged here**, not silently dropped.

**Why this split is correct:** shipping the renderer head-reader now is cheap, unblocks Phase C (which only needs to feed components), and is provable on an enriched fixture — but pretending Item B is "done" when apex still renders zero infographics would violate the verify-on-pixels bar. The phase-boundary checkpoint will state B-renderer DONE / B-generation → Phase C.

## 7. Item C — social_proof component (Theme 3 High)

**Gap:** `social_proof` extracted+packaged, read by no pattern; absent from apex fixture content. **Change:**
1. `RenderContext.social_proof(page)` → the page's `social_proof` dict or None (graceful).
2. New `components/social_proof.jinja` macro — a testimonial / credibility band (quote + attribution + optional stat), token-only styling (NO client literals; passes `test_no_literals_in_architecture`).
3. Host it on **ST-09 (status quo / credibility posture)** — render the band when `social_proof` present, unchanged when absent.
4. **Fixture enrichment:** add a representative social-proof block to the apex fixture content so it renders and is pixel-verifiable. **No-fabrication rule:** this is clearly-labelled *fixture test data*; the PRODUCTION path renders only REAL extracted/auto-fetched social proof (never LLM-synthesized). The macro/pattern never invents content — it renders what the package carries or nothing.

## 8. Item F — Remove QR from case studies (the clutter tell)

**Gap:** ST-07A renders a QR in both standard (`.cs-panel-qr`) and fill (`.cs-panel-qr--fill`, in the authority panel foot) variants; it floats/clutters the case study. **Keep** the ST-03 back-cover CTA QR.

**Change:** in `st_07a.py` stop generating/passing the QR (`qr_svg=""`), so both template `{% if qr_svg %}` blocks naturally skip. Verify the **fill authority panel still anchors** (pull-quote alone fills `.cs-panelfill-foot`; no layout collapse) and the standard variant's panel doesn't gain dead space. Update `tests/test_st07a_fill_variant.py` (asserts QR present) → assert QR ABSENT. ST-03 QR untouched + a test asserts ST-03 still renders its QR (guard the "keep" half). Pixel-verify a case study reads cleaner.

## 9. Follow-up — ST-06 floated stat clip

The ST-06 `30-50%` stat slightly clips (flagged in reflow). Small: confirm on pixels post-changes; if still clipping, widen its cell / apply the existing `_is_long_value` stat path. Not load-bearing for the phase; fix if cheap, else flag.

## 10. Constraints (hard)

- **Brand-agnostic:** no client name/hex/font literal in logic, templates, or new CSS (`test_no_literals_in_architecture`, `test_no_client_name_in_logic`, `test_no_coral_in_chassis_logic`). New macro styles = `var(--*)` tokens only.
- **No fabrication:** social-proof macro renders only package-carried data; fixture social-proof is labelled test data; no synthesized person/quote in the production path.
- **Graceful degradation everywhere:** every new consumer returns to today's exact rendering when its data is absent (grounds, fazit bg, builder SVGs, social proof). Production decks without these assets must be unchanged.
- **No canon regression:** type tiers, panel tokens, grain, margins (Phase A) untouched. Shared-component changes only as `.st-XX`-scoped overrides.
- **Page budget:** deck stays 21 physical (no NEW overflow); fill defaults must not spill. Verify with `fitz` page count + `render_package(...).overflow` after every package-affecting change.
- **Two venvs / DYLD / NO git.** Re-bake fixture from the **preprocessor** venv; render/test from the **renderer** venv with `DYLD_FALLBACK_LIBRARY_PATH`.

## 11. Adversarial gap-audit (folded BEFORE build)

| # | sev | gap | resolution |
|---|---|---|---|
| 1 | CRIT | Item E re-bake breaks `build_package.py:151-153` (asserts non-ST-07A pages carry NO `layout_variant`). | Build E **must update that assertion first** to the new fill set (ST-07A/07B/22/FAZIT carry `fill`; others none) — same task as the frozenset edit + re-bake. |
| 2 | CRIT | Fill is full-height; turning it on for ST-07B/22/FAZIT may overflow or change page count → silent deck regression. | After the E re-bake, **assert `fitz` page count == 21 and `overflow` gains no new slot**. If a filled page overflows, tighten THAT pattern's fill CSS (reflow-style) before proceeding; do NOT ship an overflow. Pixel-verify each newly-filled page. |
| 3 | HIGH | Item B premise ("generated every render") is false for apex → a naive "renderer reads head" fix renders nothing, looking done while invisible. | Rescoped (§6): renderer head-reader IN SCOPE + proven on an **enriched-fixture / synthetic** component; generation half explicitly → Phase C. Checkpoint states B-renderer DONE, B-generation deferred. |
| 4 | HIGH | Item A/D grounds could reduce text contrast → fail the quality-loop `min_text_contrast` / read noisier. | Render BEHIND content at low opacity, **gated on `data-ground-mode`** (dark panels keep solid ground); pixel-verify contrast vs current render; keep graceful fallback so no-asset decks are unchanged. |
| 5 | HIGH | Item C fixture social-proof risks looking like fabrication / a brand literal. | Labelled fixture TEST data; macro is token-only + renders only package data; production path = REAL social proof only. Guard tests must pass. |
| 6 | MED | Item F QR removal could collapse the fill authority-panel foot (QR was a layout anchor). | Verify `.cs-panelfill-foot` still fills with pull-quote alone; pixel-check both variants; add a test asserting ST-03 QR is KEPT (don't over-remove). |
| 7 | MED | `data-texture` emit (Item A) may activate `marble_paper`/`crumpled_paper` selectors on pages where they look wrong. | Emit the attribute, but pixel-verify each `[data-texture]` selector's effect on real pages; if a texture reads wrong on a given page type, scope the selector. Apex axis value determines what actually shows — verify it. |
| 8 | MED | Re-bake + enrichment shift many render tests + the (xfailed) visual-regression baseline. | visual-regression stays xfailed until the clean-20 + sign-off (post copy-fit). Update only the tests whose ASSERTED behavior genuinely changed (E fill tests, F QR tests); don't blanket-re-bake baselines. |
| 9 | MED | Bundling 6 items risks one breakage stalling all. | Plan sequences them **independent + by verifiability**: F → E → A → D → C → B-renderer. Each task self-contained, suite-green before the next. |
| 10 | LOW | New `RenderContext` helpers (`st_components`, `social_proof`) expand the context surface. | Mirror existing helper conventions (graceful, typed, unit-tested in isolation like `chart_svgs`/`slot_uri`); one test each. |

**Net:** the wiring approach is sound; build with these folded. Two CRITs (the build_package assertion + the fill page-budget) are the real traps — both caught here, both guarded by a hard page-count/overflow assertion in the E task. Item B is honestly split (renderer now, generation → Phase C). Nothing ships on a "did my edit show up" check — every item has a full-page pixel sign-off.

## 12. Testing & verification bar

- **Unit:** one test per new helper (`st_components`, `social_proof`); `data-texture` emitted; QR absent on ST-07A / present on ST-03; fill variant triggers for the 3 new types.
- **Integration:** re-bake `build_package.py` green (updated assertions); full deck render → **page count == 21, no new overflow**; both suites green; un-xfailed ST-07B tests pass as real assertions.
- **Pixel (the bar):** render the full deck and view, per item — grounds (ST-05/09/14/06), filled ST-07B/22/FAZIT, social-proof band (ST-09), de-QR'd case study, fazit ground — **compare each whole page to Richard**. A change "showing up" is not sufficient; the page must read richer/cleaner.
- visual-regression re-bake deferred to post-copy-fit clean-20 + human sign-off.
