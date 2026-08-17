# Visual-Appeal Gap Map — 2026-06-05

**Goal of the project:** make the generated report PDF as visually appealing as Richard's
hand-designed InDesign decks.

**How this map was produced:** 12 deep-read auditors, each assigned an explicit set of source
files and required to Read every file in full (not skim), hunt only for what *downgrades visual
appeal vs a hand-designed deck*, cite `file:line`, and prove coverage. Every non-test `.py`, every
`.jinja`, every `.css`, and the token file in both `research/preprocessor` and `research/v7-renderer`
was covered. The highest-impact and contradictory claims were then re-verified by hand (see
"Verified by hand" below).

**Confidence / caveat:** this is a *source-level* audit. Findings are structural facts (what the
code/tokens do), verified against source. They are **not** pixel measurements — final confirmation
of any fix comes from rendering the full page and comparing to Richard (the standing verification
bar). Items confirmed against rendered pixels: none yet.

**Verified by hand (2026-06-05):**
- Type scale `base.tokens.json`: eyebrow 8 / label 9 / body 10 / h3 11 / h2 15 / display 24 / display-xl 40 / hero 48.
- Shout-moments at 15pt: `.c-these`, `.c-key-insight__body`, `.c-authority__heading`, `.c-stat-rail value` all `var(--type-h2)` = 15pt (components.css:572, 760, 834, 151). `.c-two-tone` = `--type-display` 24pt.
- `[data-ground-mode]` CSS **exists** at assembler.py:302-310 (inline string) — it paints only the 5% wash. `[data-texture]` has **no** consumer selector (only emitter compile_tokens.py:177).
- `fal_image_resolution="2K"`, `max_generations_per_report=12` (settings.py:34, 41).

---

## The 8 root causes

Severity = visual impact: **Critical** (reads as un-designed) / **High** / **Medium** / **Low**.

### Theme 1 — The design tokens are timid (the substrate every page inherits)
This is the highest-leverage theme: fixing the tokens lifts every page at once.

| Sev | Gap | Anchor |
|-----|-----|--------|
| Critical | "Shout" moments render at 15pt: thesis, key-insight, authority heading, stat values all `--type-h2`=15pt — only 1.5× body. The 40/48pt top of the ramp is used almost nowhere. | components.css:572,760,834,151; base.tokens.json |
| High | Type ramp has a dead step (body 10 → h3 11) and a void (h2 15 → display 24); no intermediate title tier (~20pt). | base.tokens.json |
| High | Spacing ramp maxes at 12mm; panel padding is 6-8mm; no large "section air" step for generous whitespace. | base.tokens.json; components.css:295,553 |
| High | `--color-ground-wash` = accent @ **5%** — imperceptible; it is the only page ground on 8 interior page types. | compile_tokens.py:149,154 |
| High | Headings render in the **body** face: Montserrat is resolved + copied but never `@font-face`-loaded (format-4 cmap) → stack falls to Source Sans 3 = body font. No display/body contrast. | resolve_fonts.py:40-43; assembler.py:155-158; base.tokens.json `$comment` |
| High | Zero depth system: no `box-shadow`, no grain, no gradient anywhere (only a couple flat 2-stop fallbacks). Everything is flat color + hairline borders. | components.css (whole); chassis_config.py:63-71 (shadows hard-banned) |
| Medium | Only 2 accent intensities derived (tint 12%, wash 5%), both flat; no tonal ramp / darker-accent / gradient token. | compile_tokens.py:148-149 |
| Medium | `[data-density="balanced"]` (the default) matches no rule → default deck gets zero density treatment; panel padding is hardcoded so "spacious" barely changes panels. | density.css:2-4 |

**Fix direction:** rework the token scale (bigger display tier actually used on shout-moments; add a
title rung; extend spacing with section-air steps; raise the ground tint to a perceptible value and
mix toward ink, not 5% accent); load a display face that actually renders; introduce grammar-permitted
depth (keylines/mats instead of banned shadows).

### Theme 2 — Strong layouts are built but switched OFF by default
| Sev | Gap | Anchor |
|-----|-----|--------|
| Critical | "fill" (full-height dark authority panel) is auto-enabled only for ST-07A. ST-FAZIT / ST-22 / ST-07B implement + test full "fill" branches that **never trigger** → they always ship the sparse "standard" variant with a dead bottom band. | plan_layout.py:73 `FILL_DEFAULT_TYPES={"ST-07A"}`; st_07b.py:98, st_22.py:121, st_fazit.py:113 |
| High | ST-07A "standard" variant itself is structurally a dead-band layout (table grid collapses to content height; QR floats mid-page). The fill variant fixes it but only if selected. | st_07a.html.jinja:111-151; st_07a.css:73-81; st_07a.py:216-217 |

**Fix direction:** extend `FILL_DEFAULT_TYPES` to `{ST-07A, ST-07B, ST-22, ST-FAZIT}` (renderer already
supports + clamps), or set `layout_variant` deterministically from a copy-length heuristic in plan_layout.

### Theme 3 — Produced-but-dropped visuals ("jumbled wiring")
| Sev | Gap | Anchor |
|-----|-----|--------|
| Critical | ST-builder SVGs (process_flow, matrix_2x2, metaphor_split, causality_chain, stat_block + showpieces curved_arrow_flow / paired_comparison / venn_diagram) are generated every render but the renderer reads only the chart-tail (`comps[-n:]`); ST-09/ST-14 read no components at all. The richest infographics produce zero pixels. | generate_components.py:1536,1088,1205,1314; base.py:103; st_09/st_14 (no chart_svgs) |
| High | `background_texture` / `atmospheric_gradient` consumed only by st_31/st_22; the 8 content pages never call `resolve_report_asset` → no textured ground. | st_31.py:65; st_22.py:64; content patterns |
| High | `fazit_background` is generated (costs fal) but st_fazit resolves **no** image — the closing page throws it away. | generate_assets.py:67-71; st_fazit.py (no resolve) |
| High | `social_proof` is extracted, validated, written to the package — and read by **no** renderer pattern. | structure_content.py:307; assemble_package.py:282; (no consumer) |
| High | `extra_wide` / `extra_square` report slots expected by st_22/st_31 are produced by **no** stage. | st_22.py:64; st_31.py:66; (no producer) |
| Medium | `device_mockup` feature dead: `composite_device_mockup` only called in tests; no pattern reads it. | device_mockup.py:21 |
| Medium | `authority_panel.jinja` macro defined + tested, imported by **0** templates (ST-05/FAZIT hand-roll dark panels instead). | authority_panel.jinja; (no import) |
| Medium | `texture`, `accent_mechanic`, `qr_enabled` axes resolved + serialized but inert in the renderer. | compile_tokens.py:177; resolve_axes.py:118-128 |
| Low | `cover_validation` / `headline_size_class`, `css_template` written, never read. | assemble_package.py:291-305 |

**Fix direction:** add `ctx.st_components(page)` (the `comps[:-n]` head) and have typed patterns embed
it, OR route builder data through the chart lane; wire content-page grounds + fazit_background; add a
`social_proof` component; either produce or delete `extra_wide`/`extra_square` and the dead device/axis/macro paths.

### Theme 4 — Generated imagery under-spec'd
| Sev | Gap | Anchor |
|-----|-----|--------|
| High | fal resolution "2K" (~2048px) is below the 300-DPI A4 floor (2480px) and ~half the declared bleed target → soft full-bleed images. | settings.py:34; generate_assets.py:94-100 |
| High | Image-prompt richness depends on BOTH `design_brief` and OpenRouter key present; otherwise silently collapses to thin strings ("a professional background"-tier). | build_image_prompts.py:168; generate_assets.py:233-238,737,750 |
| High | The rich brand brief (`shape_language`, `composition`, `typography_character`…) shapes **only** generated imagery — `grep` of the renderer for it = 0 hits. It never touches layout/type/CSS. | brand_brief.py:33-57; (no renderer ref) |
| High | `texture_templates.py` (the curated texture vocabulary) is orphaned; generate_assets ships its own generic inline strings. | texture_templates.py:37; generate_assets.py:726-751 |
| Medium | Report-level grounds generated **last** under a shared budget of 12 → can be starved/stubbed on dense decks → st_31/st_22 fall back to flat token gradient even in production. | generate_assets.py:723-751,772-805 |
| Medium | `_serialize_brief` drops `visual_style_summary`, `typography_character`, `iconography` before the image model sees them. | build_image_prompts.py:109-122 |

**Fix direction:** raise resolution for full-bleed slots + assert downloaded dims; make the *fallback*
prompt itself art-directed and log loudly when the LLM builder returns `{}`; feed the brief into the
renderer theme layer; route texture specs through `texture_prompt`; reserve/first-generate report grounds.

### Theme 5 — Founder-photo quality risks
| Sev | Gap | Anchor |
|-----|-----|--------|
| High | Routing path (`understand_and_route`) skips restorer, quality-gate, AND face-crop → raw scraped image copied straight to the slot. | router.py:155-164; slot_bridge.py:159-163; orchestrator.py:493-500 |
| High | No hard resolution floor: `cover_hero` requires only `frontal`; print-capability is ranking-only → a 240-320px IG avatar can win the A4 cover hero. | router.py:94-129; selector.py:59-63 |
| Medium | Restorer is Lanczos-only (no sharpening / no face restore) → a soft photo becomes a bigger soft photo. | restorer.py:74-95 |
| Medium | Face-crop uses the raw Haar box with fixed padding + per-edge clamp → off-center / chin-clipped hero crops; not run on routing path. | selector.py:249-288 |
| Medium | Appeal gate `APPEAL_MIN=2` (median of 0-3), value unclamped; sharpness floor lowered to 60. Slot path never calls the classifier at all. | router.py:34; classifier.py:208-212; selector.py:46 |
| Low | Slot path can reuse the same photo across cover + team (templated look); de-dup keys on path, not content. | orchestrator.py:181-214 |

**Fix direction:** run restorer + a real resolution floor on the routing path; bar `kind=avatar/thumbnail/frame`
from `cover_hero`/`device_mockup` below a native floor; add unsharp post-pass; re-center crops; clamp appeal + raise it for the cover.

### Theme 6 — Brand identity flattened at onboarding
| Sev | Gap | Anchor |
|-----|-----|--------|
| High | 5 of 7 axes are constant defaults unless `/onboard` overrides; only palette/accent_mechanic are derived → two brands with different colors get structurally identical decks. | resolve_axes.py:106-128 |
| Medium | Vision schema can't classify `palette`, `qr_enabled`, `density` (not in `_RESPONSE_SCHEMA`/`_ALLOWED_AXES`) → always None from onboarding. | vision_reading.py:59-103; models_onboard.py:97-104 |
| Medium | Measured 8-color palette is collapsed to primary+accent+3 neutrals; the layered color is discarded (only `palette_size` survives). | pixel_palette.py:17; reconcile.py:183-198 |
| Medium | CSS `--brand-*` color vars (often the cleanest brand-color source) are extracted then never read by reconcile. | dom_extract.py:67-78; reconcile.py (no read) |
| Medium | `brand_neutral_mid` has no measured fallback → every brand gets `#7A7A8C`. | reconcile.py:157-167 |

**Fix direction:** add the 3 missing axes to the vision schema; persist secondary/tertiary palette roles;
feed `css_color_vars` in as a high-confidence source; vary axis defaults on a brand seed; add a pixel fallback for neutral_mid.

### Theme 7 — Global page furniture is generic
| Sev | Gap | Anchor |
|-----|-----|--------|
| Medium | Margins asymmetric + tight (`16/14/20/18mm`; right < left reads accidental); no generous InDesign gutter. | assembler.py:162 |
| Medium | Running header = identical wordmark+URL row on every page; no section context, no accent device. Footer = bare page number. | assembler.py:244-289,180-184 |
| Medium | No global hairline/rule/section-divider system (only the header's own border). | assembler.py:250 |
| Low | Full-bleed only for cover/breathing; no per-page bleed hook; no print marks / bleed box. | assembler.py:186-220 |
| Low | `_generic` fallback uses a different token vocabulary (`--brand-primary`, hardcoded pt) → risk of unstyled output for unknown ST types. | _generic.py:158-194 |

**Fix direction:** rationalize margins to a designed grid; give the header section context + an accent
tick; pair the folio with a rule/mark; add a generic bleed opt-in; align `_generic` to the real token layer.

### Theme 8 — Validators (good news — nothing to undo)
| Sev | Gap | Anchor |
|-----|-----|--------|
| Info | `accent_budget` is a no-op stub; `contrast` is a docstring-only stub; `overflow` is advisory-only (never mutates/shrinks). They are **not** flattening anything today. | accent_budget.py:140; contrast.py; overflow.py:34 |
| Low | The one silent downsize: ST-07A "fill" stat steps 40pt→15pt for "long" values (localized heuristic). | st_07a.py:92-137; st_07a.css:324-334 |
| — | **Future risk:** if the accent-budget 10% cap is ever implemented hue-agnostically from one client's doc, it will cap bold color. Make it per-archetype/advisory. | accent_budget.py:9-19 |

---

## What is genuinely solid (do not "fix")
- Charts pipeline (charts_svg lane) is wired end-to-end, conservative (no fabrication), gracefully rendered by ST-06/ST-07A.
- Two-pass founder scraper: directories + filenames match; cover consumes `founder.jpg`; idempotent.
- Fonts that ARE bundled (Source Sans 3 / Source Serif 4) load correctly.
- Overflow validator's advisory posture (measure-and-flag, never silently degrade) is the right design.
- Missing-image handling avoids ugly grey placeholder boxes on st_07a/st_09.

---

## Recommended execution order (dependency-aware)
1. **Theme 1 (tokens)** — biggest multiplier; every page improves at once. Do first.
2. **Theme 2 (turn on fill variants)** — one-list change, large ROI, independent.
3. **Theme 3 (wire dropped visuals)** — recovers already-built richness; depends partly on Theme 1 for how the recovered components are styled.
4. **Theme 4 (imagery: resolution + prompts + brief→layout)** — needs API keys; verify on a real `/render`.
5. **Theme 5 (founder photo quality)** — independent; improves the human imagery the cover/about depend on.
6. **Theme 6 (onboarding identity)** — makes decks differ per brand; larger, can follow.
7. **Theme 7 (global furniture)** — polish pass.
8. **Theme 8** — nothing now; just guard the future accent-budget implementation.

**Every fix is verified under the standing bar: render the full page, compare the whole composition to Richard — never "did my edit show up."**
