# Renderer Phase 4b — v2.0 Package Consumption + DNA §F Expansion (Design)

**Status:** Design (pre-implementation). User pre-authorized building 4b in this session ("spec it out properly with research backing, then proceed to build … till phase 4b"); the design itself is the already-approved DNA §F applied to the now-shipped v2.0 package.
**Date:** 2026-06-02
**Component:** `research/v7-renderer/` (Layer 2 — WeasyPrint HTML/CSS → PDF)
**↑ Now PHASE A of the master architecture:** `docs/superpowers/specs/2026-06-03-self-correcting-quality-architecture-design.md`. This spec = the theme-lock + capability-widening pass that the closed loop's rubric clamps to (§5.5 there). Build the items here first; the loop wraps around them.
**Grounded in (read these):**
- `docs/superpowers/specs/2026-05-30-richard-design-dna.md` — **§F** (who-builds-what: the renderer component list, L169-174), **§C2** (photo doctrine), **§C3** (dark panels), **§C4** (social proof), **§C5** (charts), **§E** (the ranked gap list), **§D** (per-page recipes). THE design schema (6-deck analysis, user-approved).
- The **verified package→renderer contract map** produced during the 2026-06-02 Phase-4a review (3 opus agents, code-grounded with file:line citations) — the EXISTS/PARTIAL/MISSING inventory below is taken from it.
- `research/preprocessor/models_package.py` + the v2.0 golden `tests/golden/resolved_package.v2.json` — the contract the renderer must now consume.
- `context.md` (Renderer current state + PRIOR TRACK) + the renderer's own conventions (uv venv, `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`, visual-regression baselines, the brand-agnostic guards).

---

## 1. Goal & framing

The pre-processor (Phase 4a) now emits a **`ResolvedPackageManifest` v2.0**: 7-field typed `axes`, a transitional 4-field `brand_axes`, `provenance`, `slot_summary`, and per-page typed `data` + `charts` + `social_proof` + **`slots[]` with real photos COPIED into the package** (renderer-facing `slot_id`s: `founder`, `case_study_portrait`, `about_portrait`, `proof`, `press_logo`, `client_logo`, `about_logo`). The renderer today reads the v1.0 shape, consumes **only 4 of 7 axes**, and scans `pages[].assets[]` for photo `slot_id`s the pre-processor no longer routes there — so **photos never bind and 3 axes are inert.**

**Phase 4b makes the renderer consume v2.0 and BUILD the DNA §F components** that create Richard's quality. The headline outcome is concrete: **the Apex PDF visibly transforms** — founder.png as the human anchor, the Frese (case-study-3) portrait on its Fallstudie, the **3 real proof photos as a credibility gallery on the About page**, dark authority panels, two-tone headlines, denser layout. The pre-processor side is ready; this is the consumer.

**Cardinal rule unchanged:** no client name/hex/font literal in logic (guards: `test_no_coral_in_chassis_logic`, `test_no_literals_in_architecture`); serif comes from the `headline_type` axis, never hardcoded; the **DNA is the schema, the Apex PDF is the quality bar — never a schema source.**

## 2. Package → renderer contract changes (consume v2.0)

| Area | Today | 4b change |
|---|---|---|
| `package_loader.py` axes | reads `brand_axes`, whitelists 4 keys | read top-level **`axes`** (7 fields) when present, fall back to `brand_axes`; pass all 7 to `BrandAxes`. |
| `compile_tokens.py` `BrandAxes` | 4 fields (`headline_type, ground_mode, texture, accent_mechanic`) | add **`palette`, `qr_enabled`, `density`**; wire the 3 currently-inert axes: `texture`→`[data-texture]` CSS layer, `accent_mechanic`→contrasting-hue accent, add **`--color-on-primary`** (luminance-derived, mirroring the existing `--color-on-accent` at compile_tokens.py:82-85); `density`→spacing scale; `qr_enabled`→QR gate. |
| Per-page human photos | patterns scan `page["assets"][]` for `slot_id=="case_study_portrait"` / `_PORTRAIT_SLOTS` | patterns read **`page["slots"][]`** (the v2 block) by `slot_id`; the pre-processor already emits renderer-facing ids so binding is direct + graceful (missing → no entry / `status!="resolved"` → placeholder-less reflow). |
| Per-page data/charts/social_proof | reads raw `data` only | read typed `data` (same keys, `extra="allow"` so nothing lost), **`page["charts"][]`** (draw), **`page["social_proof"]`** (rating/review cards). |
| Generated scenes/textures/devices | `assets[]` / `report_assets[]` | unchanged — `generate_assets` still owns these; the two systems stay separated by source. |

## 3. Component inventory (from the verified map) + build scope

Status from the 4b gap analysis. **Action** = what 4b does. **Pri** = APEX (visible in the Apex demo now) / GEN (full generality; Apex content doesn't exercise it).

| DNA §F component | Status today | 4b action | Pri |
|---|---|---|---|
| `founder_hero` (cover/about anchor) | PARTIAL (generic `image_type=="background"`) | bind to `slots[] slot_id=="founder"`; large hero on cover + recurring small beside quotes | **APEX** |
| `client_portrait` (large, fixed slot, **graceful photo-less**) | PARTIAL (scans wrong id) | bind ST-07A to `slots[] slot_id=="case_study_portrait"`; `media_figure` already degrades gracefully (has `--empty`); ensure ~24-40% width per DNA §C2 | **APEX** |
| `proof_gallery` on About (DNA §C4) | MISSING | NEW: render `slots[] slot_id=="proof"` as a framed credibility gallery on ST-05 (the 3 Apex proof photos) | **APEX** |
| dark `authority_panel`/`recap_panel` + `--color-on-primary` | PARTIAL (`dark_recap_panel` exists; token missing) | add `--color-on-primary` token; generalize a reusable dark panel; apply to About positioning / case-study stat rails / CTA | **APEX** |
| `two_tone_headline` (serif neutral + bold-caps accent) | MISSING | NEW macro; apply on cover + section headers | **APEX** |
| `running_header` (logo + booking tagline + URL) | PARTIAL (wordmark only) | add booking tagline + URL band (DNA §C6) | **APEX** |
| smaller QR / `density` | PARTIAL | shrink QR to secondary; `density` axis → tighter multi-column | **APEX** |
| `texture_layer` (axis-driven) | MISSING (inert `[data-texture]`) | CSS keyed on `[data-texture]` behind content | APEX-ish |
| `rating_card` (Trustpilot/Google) | MISSING | NEW macro reading `social_proof.ratings` | GEN |
| `review_card` + `review_grid` | MISSING | NEW macros reading `social_proof.reviews` | GEN |
| `client_logo_wall` (grayscale) / `press_logo_wall` | PARTIAL (`logo_wall` exists) | distinct press vs client walls; read `slots[]` logos | GEN |
| **TESTIMONIALS** + **LOGO-WALL** page types | MISSING | NEW patterns + registry + ST codes (also needs pre-processor `TestimonialsData`/`LogoWallData` — see §6) | GEN |
| charts: `before_after_bars` | PARTIAL (`bar_chart`) | read `page["charts"]`; before/after variant | GEN |
| charts: `line_compare`/`donut`/`money_infographic`/`cost_math_strip`/`comparison_columns` | MISSING/PARTIAL | NEW (inline SVG — see §5 research) | GEN |
| `result_box` (green) + green token | MISSING | NEW macro + `--color-positive` token | APEX-ish |
| `device_mockup` placement | MISSING | place the Pillow-composited image (gated on frame PNGs) | GEN |
| spread (left/right) format | MISSING | dual-page layout for the short-deck format | GEN |

## 4. Decomposition (build order)

**Phase 4b-1 — APEX-CRITICAL (the visible transformation; build first, flagship-first):**
1. **Consume v2.0**: `package_loader` reads `axes`(7)+`slots[]`/`charts`/`social_proof`; `BrandAxes`→7 fields; `--color-on-primary` token. (foundation — nothing visible yet, visual-regression stays green.)
2. **Founder hero** (cover) + recurring small founder.
3. **Client portrait** on ST-07A from `slots[]` (graceful photo-less for the 4 missing Apex case studies).
4. **Proof gallery** on About from `slots[]` proof (the 3 Apex photos) — the Apex social-proof beat.
5. **Dark authority panels** (About positioning, case-study stat rail, CTA) using `--color-primary`/`--color-ink` + `--color-on-primary`.
6. **Two-tone headlines** + **running-header booking tagline+URL** + **smaller QR** + **denser** layout.
7. **Regenerate the Apex v2 package** (client_slug=apex, against `client_assets/apex/`) → **render** → compare to Richard's reference + the DNA §E gap list → re-baseline visual-regression per approved page.

**Phase 4b-2 — GENERAL (full generality; Apex content uses none of these — build after 4b-1 lands):**
8. Social-proof component library (`rating_card`, `review_card`/`review_grid`, distinct logo walls) reading `page["social_proof"]`.
9. **TESTIMONIALS + LOGO-WALL** page types (renderer patterns + pre-processor models — §6).
10. Charts from `page["charts"]` (inline SVG: line/donut/money/cost-math/comparison) + `result_box`/green.
11. `device_mockup` placement (gated on frame-PNG authoring) + `texture_layer` polish + spread format.

This mirrors the renderer's proven **flagship-first** discipline (build one transformed page — the **About page** is the best flagship: it shows founder anchor + proof gallery + dark panel + stat trio at once — show vs reference, lock the bar, then roll out).

## 5. Apex render verification + research notes

- **Render check:** regenerate an Apex v2.0 package (the pre-processor real path — `founder`/`case_study_portrait`/`proof` resolve from `client_assets/apex/`, generated scenes stubbed/generated), render via `render.py`, and judge each page against Richard's `APEX - KI DMC Report v1 (1).pdf` + the DNA §E gaps. The visible win is photos + dark panels + density, NOT charts (Apex content carries no chart data — that's why charts are 4b-2).
- **Research — charts in WeasyPrint (4b-2 only):** WeasyPrint's `conic-gradient` support is unreliable; **donut/pie/line/money charts → inline `<svg>`** (WeasyPrint renders SVG robustly), built deterministically from `page["charts"]` data. `bar_chart` (pure CSS) already works. Confirm technique when 4b-2 starts; Apex needs none of it.
- **`--color-on-primary`:** WCAG relative-luminance threshold on `brand_primary` → white or `--color-ink` text, exactly mirroring the existing `--color-on-accent` derivation (compile_tokens.py:82-85). Pure function of the brand token, brand-agnostic.
- **Photos already in the package:** 4a copies resolved photos into the package `assets/`; the renderer resolves `slots[].path` (package-relative) via the existing `ctx.resolve_asset`. No new asset I/O.

## 6. Dependencies & out of scope
- **TESTIMONIALS/LOGO-WALL page types** need pre-processor `TestimonialsData`/`LogoWallData` models + slot recipes + ST codes (PRD §3.7) — a small pre-processor addition paired with the 4b-2 renderer patterns. Deferred with 4b-2 (no Apex page uses them).
- **Social-proof DATA** (ratings/reviews) is the deferred 2nd-pass acquisition + an input-contract field — `social_proof` renders only when present; Apex currently supplies none, so `rating_card`/`review_grid` show on other clients, not the Apex demo.
- **device-frame PNGs** (phone/laptop/book) need one-time authoring before `device_mockup` renders.
- **Live Drive** removed (n8n bridges).

## 7. Discipline (non-negotiable)
- **Brand-agnostic guards** extended to every new macro/template/style (semantic tokens only; serif via axis).
- **Visual-regression net** re-baselined deliberately, page-by-page, only after a page is approved against the reference (the proven Plan-A/B method).
- **WeasyPrint env:** activate `research/v7-renderer/.venv` (sets `DYLD_FALLBACK_LIBRARY_PATH`); uv-managed.
- **Subagent-driven-development**, flagship-first, two-stage review per task.

## 8. Self-review
- **Coverage:** every DNA §F component is in the §3 table with a 4b action + priority; the v2.0 contract (§2) is the consumption spec; the §4 decomposition sequences APEX-critical before GEN, matching the user's "transform the Apex PDF" goal.
- **Consistency:** the slot_ids in §2/§3 match exactly what the pre-processor emits (verified: `founder`/`case_study_portrait`/`about_portrait`/`proof` from slot_registry); axes match `ResolvedAxes`'s 7 fields.
- **Scope:** one subsystem (the renderer consuming v2.0). New page TYPES + charts + social-proof cards are explicitly GEN/4b-2 because the Apex demo doesn't exercise them — avoids over-building before the visible win lands.
- **Research backing:** the design is the user-approved 6-deck DNA; the contract is code-verified (file:line); the one genuine technique unknown (charts in WeasyPrint) is isolated to 4b-2 with a documented SVG approach.
- **Brand-agnostic:** photos/axes/social-proof are DATA from the package; macros name roles; guards lock it.
```
