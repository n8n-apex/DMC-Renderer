> **STALE: DO NOT ORIENT FROM THIS FILE.** It describes an earlier frame and is wrong on load-bearing facts. Authoritative current sources: `context.md`, `docs/superpowers/CURRENT-STATE.md`, `richard-grammar-v2.md`. Corrections that bite: the engine is **Chromium print-to-PDF plus Ghostscript flatten**, NOT WeasyPrint (legacy `--engine weasyprint` fallback only); bundled fonts are **Source Serif 4 and Source Sans 3** variable faces, NOT Montserrat; the renderer consumes a **multi-page `resolved_package.json` via `--package-dir`**, NOT a single-page GEVA fixture. (Banner added 2026-06-21.)

# BUILD-NOTES — Historical retrospective (Phase 4, May 17 2026)

> **STATUS: HISTORICAL.** This file documents the original Phase 4 build
> which has been fully decontaminated (Moves 0-2c, May 23 2026).
> For the **CURRENT** chassis state, read `CHASSIS-NOTES.md`.
>
> The build described below used Inter / Source Serif 4 fonts, a
> CoralValidator with two-path selection, APEX default profiles, and
> design_preferences — **ALL of which have been removed**. Do not
> rebuild any of these. They are documented here only for historical
> reference (build log integrity; editing the record would be dishonest).
>
> Refer here ONLY to understand why a particular structural decision
> was made or unmade, never as a guide to current behaviour. Every
> "current state" claim below predates the decontamination.

---

# BUILD-NOTES — Phase 4 GEVA build (original title, retained below)

The ST-07A LRP page for GEVA (mein_werkzeugkoffer), rendered through the Phase 3 chassis. This document records (a) which grammar sections drove which decisions, (b) explicit confirmation the page consumed the chassis instead of bypassing it, (c) every judgment I had to make that the grammar/matrix did not cover, and (d) the honest defect list — what I actually see in the output versus what richard-design-system §2/§4 specifies, NOT a parity claim.

The verification-trap rule from `design-findings.md` §3 applies throughout: element-presence is not quality.

---

## Grammar sections that drove decisions (every one via `grammar_loader`)

The pattern (`patterns/st_07a.py` `render_lrp`) calls `grammar.get_section(N)` for each of the following — each call FAIL-LOUDs if the section is missing. Patterns never re-read SKILL.md ad hoc.

| Decision | Grammar section | What it drove |
|---|---|---|
| Two navys distinction | §1 (palette + "would collapse this distinction") | `--brand-primary` (display navy) vs `--brand-secondary-panel` (panel navy) via D2 — two distinct CSS vars, never collapsed to one |
| Coral firing locations (incl. attribution + URL + stamp) | §1 REVISED firing-locations list | Coral used at stamp box, oversized quote glyph, attribution, URL, callout-row rules — none in body paragraphs or section headers (which are navy bold per D1) |
| LRP geometry — rail width, photo placement, navy-panel sizing | §2 Variant B′ | 28% rail width (ratio, not mm); rectangular ~50mm photo at top of rail with NO frame and NO border; navy panel below sized to content, NOT full-height |
| Pullquote treatment (italic Source Serif, white on panel navy) | §3 + §5b (oversized coral glyph) | `pullquote_treatment: "navy_panel_with_oversized_quote_glyph"` from `design_preferences` selects the §5b variant (oversized coral „) over §3's restrained version |
| Case composition order (stamp → headline → lede → body sections → callout mid-body) | §4 | Right column composition matches §4 step order |
| FALLSTUDIE stamp box (border + padding + uppercase letter-spaced coral) | §5a (literal CSS sample in the section) | 1.5px coral border, Inter 700, letter-spacing 0.18em, uppercase, coral text — matches §5a's CSS verbatim except border-radius and shadow which come from `chassis_config` (both 0 in HARD mode) |
| Marble texture background | §5d | `background-image: url('marble-cream.png')` on @page; `background-size: cover` |
| Type system — display headline / section labels / body / pullquote / folio / URL | §10 (type-system table) | Extracted at render time by `_extract_type_system(g_type.body)`; family + weight + size per role come from §10 cells |
| Section labels = navy bold, NOT gray | §10 Section labels row + D1 ratification | `.body-section h3 { font-family: 'Inter'; font-weight: 700; color: var(--brand-primary) }` — explicit refusal of `--brand-neutral-mid` for section labels |
| Folio + URL = Inter Regular (weight 400) | §10 Folio + URL/meta rows + E4 ratification | `@page @bottom-left { font-weight: 400 }` and `@page @top-left { font-weight: 400 }` — relies on bundled Inter-Regular.ttf, no silent fallback |
| Body bold = Source Serif 4 Bold, SAME family | §10 Body bold row + F3 ratification | `.body-section p strong { font-family: 'Source Serif 4'; font-weight: 700 }` — no Inter cross-family substitution |
| No rounded corners / no drop shadows anywhere | Anti-patterns #1 + #2 (matrix PARKED override) | NOT hardcoded in the template — pattern asks `chassis_config.allow_rounded_corners(None)` and `chassis_config.allow_drop_shadows(None)`; both return False in HARD mode |
| Callout-row coral micro-headers | §5c + §10 ("coral micro-headers on body callout rows") + B2 | 2-column callout table with coral horizontal rules top/bottom/between rows, cells in Inter Bold coral; built from `preprocess.parse_callout_row(wendepunkt)` — NOT markdown-preprocessed |
| No running per-page footer CTA | §9 anti-pattern #13 | No `@bottom-right` CTA box; only the folio at `@bottom-left` |

---

## Chassis-consumption confirmation (the load-bearing claim)

The page consumed every chassis surface; nothing bypassed.

1. **Grammar loader (`grammar_loader.load_grammar`)** — called ONCE in `render.py` line 99. Result passed to `render_lrp`. Inside the pattern, every grammar fact is read via `grammar.get_section(...)`; SKILL.md is never re-read ad hoc. The seven `get_section` calls at the top of `render_lrp` would have FAIL-LOUDed if any section disappeared.

2. **Brand tokens (`brand_tokens.parse_brand_tokens`)** — called ONCE in `render.py` line 91. Returned `BrandConfig` with `design_preferences_present=True` and `coral_budget_per_page=5` (matrix C1 ingestion path). GEVA's `design_preferences` were honored. Apex's would have routed to the default profile. The new `BrandConfigError` raises BEFORE any render begins if a future opt-in brand forgets `coral_budget_per_page`.

3. **`chassis_config.allow_rounded_corners` / `allow_drop_shadows`** — called inside `render_lrp` lines 159–160. In HARD mode (default), both returned False. The page's CSS uses computed `radius_css` and `shadow_css` strings derived from those answers; no `border-radius: 4mm` or `box-shadow: …` is hardcoded in the template. When the user flips `ANTIPATTERN_MODE` to `BRAND_PREF`, the page's behavior changes WITHOUT any template edit — that flip is currently parked.

4. **`CoralValidator`** — instantiated in `render.py` line 158. Constructor selected `path='location'` based on `BrandConfig.design_preferences_present=True` (matrix C2). The page asserts `validator.path == "location"` and would raise on regression. `validate()` returned a stub-passed result tagged `path='location'`. The full pixel/DOM location-rule logic is still Phase-3-stubbed; that is per spec ("requirement here is that the page routes through it and the path selection is correct, NOT that location validation is fully implemented").

5. **`preprocess.preprocess_body` and `preprocess.parse_callout_row`** — body fields (`kurzportraet`, `ausgangsproblem`, `ziel`, `loesung`, `ergebnis_text`, `pullquote.text`) went through `preprocess_body` per ARCHITECTURE.md §6. `wendepunkt` went through `parse_callout_row` instead per matrix B2 — markdown preprocessor was NOT applied to the 2×2 grid.

No part of the pattern looked at fixture data, brand values, font paths, or anti-pattern decisions except via these chassis entries.

---

## Uncovered judgments — flagged, not silently decided

Every judgment I had to make where the grammar or matrix did not give an unambiguous answer. None hidden.

1. **Display headline size set to 24pt — BELOW §10's 26–30pt range.** GEVA's company name ("GEVA Gas- und Energieverteilungsanlagen GmbH") is 50 characters long. At 26pt with the right column width, it wraps to 4+ lines, eating most of the vertical budget. I chose 24pt to keep it at 3 lines. **This is OUT of the §10 grammar range.** Alternatives: (a) split the headline at the company-name boundary (e.g. headline = "GEVA Gas- und Energieverteilungsanlagen GmbH" with a sub-line); (b) accept 4-line wrap; (c) extend §10 to permit a smaller size for long brand names. **Awaiting Utkarsh ruling** before pattern is generalized.

2. **Pullquote attribution color = coral (not muted-light/white per §3).** §3 says attribution is "small caps Bold, ~8pt, +150 units letter-spaced, in muted-light or white". §1 firing-locations list says "Attribution text below pullquote" is a legitimate coral firing location for mw (per the REVISED rule). These two sections disagree. I picked coral because §1 REVISED is the authoritative ruling that took precedence over the older aerztepartner-extracted §3 text (same fault line as C1's "1 fire/page" fossil). **Flagged**; if §3 wins, swap to a muted-light color.

3. **Photo crop = `background-size: cover; background-position: center`.** No grammar guidance on the focal point. The GEVA team photo crops centered; in design-findings.md §3.2 I previously called out that the source is landscape and centering can hide subjects. **Flagged**; a `focal_point` field on the image (per architecture-v2 §3 `Image` dataclass) would let the page specify e.g. `position: left center` — not implemented in this pattern.

4. **§3 vs §5b tension for pullquote quote-mark.** §3 says "No quote-mark graphic ornament" — explicitly forbidding an oversized glyph. §5b describes an oversized coral „ "ABOVE the pullquote body text" as a decorative element. These directly contradict. I followed §5b because `design_preferences.pullquote_treatment = "navy_panel_with_oversized_quote_glyph"` selects the §5b variant for GEVA. **Surfaced; not autonomously resolved.** The cleanest reconciliation would be to amend §3 to acknowledge §5b applies when the brand's `pullquote_treatment` requests it.

5. **Folio font size 7.5pt — slightly under §10's ~9pt.** I chose 7.5pt to match the visual restraint of mw's reference page. §10 says "~9pt"; the tilde implies a range but 7.5 is outside the tolerance most readers would call "~9". **Flagged for ratification.**

6. **`@top-left` running header at 8pt — §10 URL/meta says ~7pt.** Same axis as #5; chose slightly larger because the brand wordmark wants more presence. **Flagged.**

7. **Numeric values inlined as Python constants rather than parsed from grammar.** §2's "28%", §2's "~50mm", §5a's "1.5px / 6mm 12mm padding / 0.18em letter-spacing" are typed as CSS literals in the pattern with `/* §X */` citations rather than parsed from the section bodies at runtime. **Flagged** — when a second pattern (Phase 5+) also needs §5a or §2 values, the right move is to add a `grammar.get_decorative_system()` helper to `grammar_loader.py` and have both patterns read through it. Doing that now would be over-engineering ahead of need.

8. **`hyphens: auto` on body paragraphs without a configured German hyphenation dictionary.** WeasyPrint v68 supports `hyphens: auto` but needs a Pyphen-loaded language to actually break German compounds. `preprocess.py` does not yet load Pyphen for `de`. Long words (e.g. "Energieverteilungsanlagen") may not break cleanly at column edges. **Chassis gap; Phase 5 preprocessor work.**

9. **`hr` separator added inside the pullquote panel above the QR code.** Not in §3 or §5b; I added it as visual separation between attribution and QR. **Decoration beyond grammar; flagged.** Easy to remove.

10. **WeasyPrint v68 vs v66 from `render_v7.py`.** I'm using v68 (installed fresh into the chassis venv). `render_v7.py` used v66. CSS interpretation differs in places (flex, `@page` margin boxes). **Flagged** — when promoting to `dmc-renderer/`, the production version should be pinned.

11. **No font subsetting verification for German umlauts.** Inter-Regular.ttf supports the Latin Extended-A range; haven't verified `ü`, `ä`, `ö`, `ß` render correctly in all weights. Visual inspection shows them correct in the rendered page, but no programmatic check. **Verification gap.**

12. **Inline CSS in the pattern module rather than a separate file under `shared/css/`.** Phase 3 created `shared/css/` empty; I did not factor CSS out because there is only one pattern. **Flagged** — when Phase 5 adds a second pattern (probably ST-07B Theory), the right move is to extract common rules into `shared/css/` and use Jinja-style includes.

---

## Honest defect list (what I actually see in `output/geva-p1.png`)

I rasterized the rendered PDF at 2.5× (180 DPI) and inspected the resulting 1489×2105 PNG. Defects below are mine, observed against §2/§4 visual specifications.

### Real render defects (the page is wrong against grammar in these places)

D1. **Duplicate opening „ glyph in the pullquote panel.** The §5b oversized coral „ glyph renders at the top of the panel AS DESIGNED. But the body quote text also starts with a literal „ (because the GEVA fixture's `pullquote.text` begins with one). Result: TWO opening guillemets visible — one big coral, one small white inside the italic text. The §5b decoration was designed to replace the in-text opening glyph, not stack on top of it. Render bug. **Fix:** strip a leading „ (and English variants) from the quote text in the pattern before emitting. `render_v7.py` did this with `.lstrip('„').lstrip('"')`; my pattern omitted that step.

D2. **Headline overflow risk.** "GEVA Gas- und Energieverteilungsanlagen GmbH" wraps to 3 lines at my chosen 24pt. At grammar-compliant 26pt it would wrap to 4 lines. Either way the headline dominates more visual real estate than Richard's reference (where shorter headlines fit in 2 lines). The grammar does not specify what to do when a headline is unusually long. See uncovered judgment #1.

D3. **Background texture is flat.** The `assets/marble-cream.png` symlink points to the same texture as v7-test. In the rendered output it reads as a smooth cream wash rather than the visible paper grain §5d describes ("subtle mottled paper-grain texture overlays the cream page background on every page. Most visible in upper portions of pages"). The asset itself is the limit here; chassis CSS already does `background-blend-mode` is NOT set (I omitted it — let me recheck). Actually I omitted `background-blend-mode: multiply` from §5d's sample CSS. **Render bug:** add `background-blend-mode: multiply` to `@page`. May or may not improve the appearance given the asset.

D4. **Background appears solid cream in the right column area.** The marble texture is on `@page` background but the right column's body content sits on the same cream. The grammar doesn't separate this — both rail and right column should share the textured cream. The output shows uniform color where I would expect variation. Confirmed: asset is too uniform.

D5. **Quote attribution sits very tight to the QR code area** in the rendered output. The `hr` separator I added (uncovered judgment #9) plus `margin: 3mm 0 0 0` on the URL is OK but the visual breathing between blocks in the navy panel is slightly cramped. Defect: minor spacing.

D6. **Section labels render correctly in navy bold (D1 ✓)** — but I cannot mechanically verify this from the PNG; visual inspection confirms they are not gray. **Validator gap, not a render bug** — the chassis does not yet enforce "section labels are navy" mechanically.

D7. **Folio "14" is visible bottom-left but at 7.5pt is below the §10 ~9pt.** See uncovered judgment #5.

D8. **The right column ends with ~25mm of empty space below the Ergebnis section.** Page does not fill to the bottom. mw_p14's reference fills more — likely because GEVA's body text is shorter than mw's other case studies. Compositional, not a bug.

D9. **Body bold is not exercised by the GEVA fixture.** No `**markdown**` markers appear in any body field. The same-family-bold (F3) typography is implemented in CSS but is not visible in the render. **Test coverage gap** — the next case study fixture should include bold to exercise this path.

D10. **Photo crop centers, possibly hiding faces.** See uncovered judgment #3. Background-position is `center`; the GEVA team photo's prominent subject is roughly in the left third of the original image; centering crops it asymmetrically. **Render is sub-optimal but not technically wrong against grammar** (grammar specifies rectangular crop, not focal point).

### Things that look CORRECT against grammar (mechanical, observable)

- Photo is rectangular at the top of the left rail. NO frame. NO border. NO border-radius (visual edge is hard). NO box-shadow (panel is flat against cream). ✓ §2 Variant B′.
- Navy pullquote panel below photo. Panel navy is visibly distinct from the headline navy. ✓ D2.
- Oversized coral „ glyph above the quote text. ✓ §5b.
- White italic Serif quote text on navy panel. ✓ §3 + §10 Pullquote row.
- Coral attribution small-caps letter-spaced. (Tension with §3 noted in uncovered judgment #2.)
- QR code: white modules on navy panel background. ✓ §5b panel composition.
- Coral URL below QR. ✓ §1 firing locations.
- Right column: coral-outlined FALLSTUDIE 03 stamp box at top. Hard rectangular edges. Coral letter-spaced uppercase. ✓ §5a + chassis HARD mode.
- Display headline in display navy, Inter heavy weight. ✓ §10 Display headline row (modulo D2 size question).
- Italic Source Serif lede below headline. ✓ §4 step 3.
- Body sections in §4-specified order: Ausgangssituation → callout-row → Ziel → Lösung → Ergebnis. ✓
- Section labels in navy bold (not gray). ✓ D1.
- 2×2 callout grid with coral top/middle/bottom rules. ✓ §5c + matrix B2.
- Folio bottom-left, mid-gray, Inter Regular (modulo size question). ✓ §10 Folio.
- NO running per-page footer CTA. ✓ anti-pattern #13.
- Cream page background. ✓ §1 + §5d (modulo texture question D3).

### Things I cannot verify from a single rendered page

- Coral budget enforcement (location-rule path is stubbed in Phase 3).
- Whether all coral fires in the page would pass a proper §1 firing-locations validator (visual inspection counts 7 coral elements: stamp border, stamp text, quote glyph, attribution, URL, callout rules, callout text — all in legitimate §1 locations, but no DOM-classifier ran).
- WCAG contrast on the pullquote panel (white-on-#1F3D6D should be fine, but `validators/contrast.py` is stubbed).
- Whether the rasterized PNG matches what a print-pipeline CMYK conversion would produce (Phase 6).
- Pixel-level fidelity to mw_p14 reference. I am NOT making that claim; matching mw_p14 was never the Phase 4 goal — proving the chassis carries weight is.

---

## What did NOT happen (the boundary held)

- `render_v7.py` was not touched.
- The matrix file was not touched (row-edit authority CLOSED).
- No contract doc (`API_CONTRACT.md`, `ARCHITECTURE.md`, `BRAND_TOKENS.md`, `FONT_LOADING.md`, `CACHE_STRATEGY.md`) was touched.
- No scraper, no automated brand-guideline pipeline.
- No second pass — I did not iterate the GEVA page to "fix" defects; the spec said do not iterate and do not self-congratulate. The defects above are recorded for review.

---

## Files produced

- `output/geva.html` (34,121 bytes) — generated HTML (for debugging; not the deliverable)
- `output/geva.pdf` (808,668 bytes) — **the deliverable**
- `output/geva-p1.png` (1489×2105) — rasterized first page for inspection
- This file: `BUILD-NOTES.md`
- New: `preprocess.py` filled in (was stub in Phase 3)
- New: `patterns/st_07a.py` filled in (was stub in Phase 3)
- New: `render.py` filled in (was stub in Phase 3)
- New: `fonts/Inter-Regular.ttf` fetched from rsms/inter 4.1 release
- New: `fonts/Inter-{700,800,900}.ttf`, `SourceSerif4-{Regular,Italic,Bold}.ttf`, `Vollkorn-Bold.ttf` (symlinks to `dmc-renderer/fonts/`)
- New: `assets/marble-cream.png`, `assets/geva-team-placeholder.png` (symlinks to `v7-test/assets/`)
- New: `.venv/` (chassis-local Python 3.11 venv with WeasyPrint 68.1 + qrcode + pymupdf + Pillow)

`CHASSIS-NOTES.md` updated append-only with the new "AWAITING UTKARSH RATIFICATION" section.

---

## Boundary-of-this-build note

A clean Phase 4 yielding a render that looks "good enough" on first try is exactly the failure mode the verification trap rule warns about. I have rendered ONE page through the chassis; observed defects D1–D10; flagged 12 uncovered judgments; confirmed the chassis was consumed not bypassed; and stopped. The next move is yours.
