# DMC Report — Visual-Appeal Master Backlog (2026-07-11; loop-updated 2026-07-13)

> **2026-07-13 LOOP STATUS.** Done + pixel-verified on the v4 christoph deck: A1/A2 host slots
> (fill + case + st_07b + st_14 + horizontal_process + a4_vertical_timeline + editorial fallback),
> B0 v4 adapter (kennzahlen/vorher_nachher/anteil/kostenrechnung/pullquote/bildwunsch-passthrough),
> C1 partial (grounded %-donut synthesis, one-device rule), J2 (ST-06 marble result footer via
> abschluss→ergebnis), J5 systemic (built-gate: stubs can never be assigned; render_fn honored;
> cache invalidated on register). A high-effort 8-angle /code-review (47 survived findings) ran;
> all ~15 distinct CORRECTNESS findings fixed same-day (crash-safe component reads + correct
> containment, >100% figures never drawn as rings, falsy-zero guards, cross-field donut dedup +
> caps, dict-pullquote legacy guard, ST-07A stats merge, `sub` source preserved + rendered,
> 'Effizienzgewinn' hardcode removed, color_flood coverage, em-dash sweep). 44 guard tests green.
> DEFERRED from the review (cleanup/altitude, tracked here): adapt-once-per-page memo (perf,
> O(candidates) adapt re-runs), founder_identity computed twice, _page_source_text triple walk,
> shared _str helper in build_live, st_07b template variant dedup, fb-proof→stat_strip reuse,
> generic .c-viz dark-ground token contract (H-grader adjacent), donut size variant on the
> component, dead `_has_own_portrait` + `closing_redirect` writes, `_normalize_page_data`
> god-function split (extract the v4 adapter into its own module).

The single, exhaustive list of everything that hinders the PDF's visual appeal, consolidated from:
the multi-agent disconnect analysis (7 investigators + synthesis + critic), the reference-QC-loop
code trace, the christoph deck walkthrough (dead-space inventory), and the fill-treatment work done
this session. Nothing omitted or minimized. Each item: **[severity | effort | status | depends-on]**,
what it is, why it hurts the visuals, and the exact files.

Severity = critical / high / medium / low. Effort = S/M/L/XL. Status = DONE / TODO / OWNER-GATED / CROSS-SESSION(n8n).

---

## NORTH STAR (the ranking, in owner's words)
Every page must reach **Richard-reference visual quality AUTOMATICALLY** — system-driven, no
hand-editing by me — verified by the **reference-PDF QC convergence loop** (compare each generated
page to the auto-selected same-type Richard page, iterate until visually appealing). Concretely that
means: real infographics/data-viz, device mockups, real images, the right treatment per page, and
**zero dead space** — produced by the system itself, not patched one page at a time.

## THE MASTER DISCONNECT (why everything below is currently invisible — VERIFIED in pixels)
The page-filling **TREATMENT** track and the richness-**GENERATOR** track are **mutually exclusive
render paths**. `assembler._render_one_page` = treatment-first, legacy-fallback. The generated charts
(`page["components"]`), viz presets (`data.viz`), and diagrams (`data.diagram`) render **only on the
legacy path**; **zero** built treatments read them. Proof: the one generated component (ST-06
"PROZESS · MECHANIK" SVG) is **absent from the final PDF** because ST-06 got a treatment. So Track A
below is the master gate — until it lands, everything else produces data that renders nowhere.

---

## TRACK 0 — DONE this session (baseline; keep)
- **[—|—|DONE|—] `a4_editorial_fill` treatment built** — 5 text page types (Outlook/About/Symptoms/Status-Quo/Fazit) now fill: equal-height numbered bands / centered prose / hero-quote climax / CTA-URL anchor. `templates/treatments/a4_editorial_fill.{html.jinja,css}`.
- **[—|—|DONE|—] Fixed the undefined `--type-h1` token bug** (headline was silently body-sized) in `a4_editorial_fill.css` + `a4_case_study.css` + `a3_case_study.css` → `--type-display`; added guard `test_tokens.py::test_css_references_only_defined_type_tokens`.
- **[—|—|DONE|—] Stylist:** fill is the graceful fallback (after data-gated treatments); added to `_REPEATABLE_TREATMENTS`.
- **⚠ CAVEAT (creates a dependency):** filling those pages with the always-fitting treatment ALSO routed them AROUND the legacy chart-hosting path → **Track A is now a hard prerequisite** for any chart to appear on them.

---

## TRACK A — MASTER GATE: make treatments HOST the rich devices *(nothing shows until this)*
- **[critical|M|✅DONE 2026-07-11|—] A1. Viz slot in the built treatments.** `td.viz` now renders via `viz.jinja` in `a4_editorial_fill` (.ef-vizband) + `a4_case_study` (.cs4-devices, foot of the cream field) + the legacy `st_07b` fill/standard variants (.th-viz). VERIFIED in pixels on the v4 render (3/3 viz specs visible; transform_arrow on case study + 2 theory pages). Plus a dark-beat legibility fix: dark page modes reassign --color-ink/muted to white, washing the light arrow chip — repointed its text to the un-reassigned --color-neutral-dark (viz.css).
- **[critical|M|✅DONE 2026-07-11|—] A2. Component-SVG slot in the built treatments.** `TreatmentData.components` + `_component_svgs()` resolve `page["components"]` to inline SVGs; hosted in `a4_editorial_fill` (.ef-compband) + `a4_case_study` (.cs4-devices). NOTE: `horizontal_process` (ST-06) intentionally NOT given the band yet — its treatment redraws the steps as cards, so the generated process SVG would duplicate; revisit when charts (not process comps) land on ST-06.
- **[critical|M|TODO|A-master] A3. Diagram slot in the built treatments** (`components/diagram.jinja` from `data.diagram`). **Critic correction:** do NOT add diagram reads to `patterns/st_07b.py`/`st_05.py` — those are legacy-path files and treated pages never reach them; the host must be treatment-level.
- **[medium|M|TODO|—] A4. Image slot in the text/stat treatments.** `a4_editorial_fill`, `a4_vertical_timeline`, `horizontal_process` are `needs_image=False` with no image element → they're text-only by construction. Add an image slot so portraits/mockups can land.
- **[XL|XL|TODO|A1] A5. Author `a4_bi_dashboard`** — the true "Power-BI" 50/50 data-infographic spread; the ONLY `dashboard`-archetype treatment, `required_fields=('viz',)`, currently a metadata-only STUB (no template/css). This is the ceiling for the dashboard look. `treatment_catalog.py:86`.

## TRACK B — FEED THE PRODUCERS: one German→contract adapter *(turns EXISTING data into visuals, no writer change)*
Root: builder predicates were copied from the old English schema; the writer emits German shapes → every builder returns `{}` (0 components verified). Put the bridge in ONE place (`build_live._normalize_page_data`, already invoked). **NOTE: all Track-B output (`page["components"]` / chart SVGs) renders ONLY on the legacy path → it is INVISIBLE on treated pages until A2 hosts components in treatments. So B1-B4/B6/B7 depend on A2 (and A1 for viz-shaped output), exactly like C1 depends on A1.**
- **[critical|M|✅DONE 2026-07-11|—] B0. writer-prompt-v4 VISUAL DATA adapter** (`build_live._normalize_page_data` tail): `kennzahlen{wert,label,quelle}`→canonical `stats{value,label,sub}` (writer figures lead, dedup); `vorher_nachher`→`transform_arrow` viz spec (prose-safe); `anteil`→`donut` (figure verbatim, arc = drawing param); `kostenrechnung`→`stat_strip`; string `pullquote`+`pullquote_attribution`→the quote dict `_quote_from` consumes; `bildwunsch` passthrough (Track F consumes). VERIFIED on the v4 render: kennzahlen stat rails on About + False-Beliefs, 3 transform_arrows, pullquotes in the case rail. (anteil/kostenrechnung branches built but UNEXERCISED — no such data in this JSON yet.)
- **[critical|M|TODO|A2] B1. `schritte{titel,beschreibung}` → `steps{n,short}`** — unblocks ST-06 `process_flow` component + process charts. `generate_components.py:1450`, `models_pagedata.py:124`.
- **[critical|M|TODO|A1,A2] B2. `ergebnis_metrics{label,wert}` → `stats{value,label}`** + fix `wert`↔`value` key + parse `X → Y`/`%` into before/after tokens — unblocks ST-07A `stat_block` + the before/after chart. `generate_components.py:1491`, `structure_content.py:88-90`, `models_pagedata.py:24`.
- **[high|M|TODO|A2] B3. `schmerzpunkte` → matrix/iceberg/bar shape (ST-09).** *Critic caveat:* pure prose, no x/y/numeric → yields styled cards, not a true matrix/bar. `generate_components.py:1469`.
- **[high|M|TODO|A2] B4. `irrtuemer` → pills/causality/compare pairs (ST-14).** `generate_components.py:1482`.
- **[medium|M|TODO|B1-B4] B5. Register builders for the 9 page types with NONE** (ST-01/02/05/07B×3/FAZIT/22/03 — `_ST_BUILDERS` has only 4 keys) OR route their lists through the adapter. `generate_components.py:1536`.
- **[medium|S|TODO|A2] B6. Wire the 3 dead-but-built builders into the dispatcher:** `curved_arrow_flow`, `paired_comparison`, `venn_diagram` (defined, callers = tests only). `generate_components.py:1088/1205/1314`.
- **[high|S|TODO|A2] B7. Chart-spec relay:** `structure_content` only emits a ChartSpec on explicit English signals (`chart/ohne/mit/breakdown/kosten/series…`) the writer never sends → have the adapter surface those signals so `charts_svg` (6 built themed SVGs, runs but gets 0 specs) fires. `structure_content.py:287-305`, `generate_components.py:1613`.
- **[high|S|TODO|A2] B8. Any-page extras path:** `_build_extras_for_any` (bar_chart/line_chart/compare_table) + `bar_chart.jinja`'s `data.bars` binding fire on 0 pages because the writer never emits `bar_data/line_data/compare_data` → surface these via the adapter too. `generate_components.py:1525-1532`, `bar_chart.jinja:32`.

## TRACK C — ENRICH THE LIVE VIZ PRODUCER (synthesize_visuals) *(offline, no API key)*
- **[critical|M|TODO|A1] C1.** Today `synthesize_visuals` emits **only** `bar_compare`, and only on `von X auf Y` phrasing → emit the full preset family deterministically (donut/gauge/ba_bars/stat_strip/kpi_card/phase_timeline/…) from normalized fields + verbatim numbers. 15 of 16 presets currently have **no producer anywhere**. `synthesize_visuals.py:233`.
- **[low|S|OWNER-GATED|C1] C2.** The LLM path is env-gated (`OPENROUTER_API_KEY`) — keep as an *enhancer* only; richness must not depend on a key. `synthesize_visuals.py:218`.
- **[low|M|TODO|A1] C3. Trend/time-series line chart is architecturally ABSENT** — `viz.jinja` dispatch has no line/area/trend branch (presets end at step_cascade); the only line renderer (`charts_svg.line_compare`) is dormant. This preset must be BUILT into the dispatch, not merely produced. `viz.jinja`, spec archetype #8.

## TRACK D — DIAGRAM PROOF LAYER (plan_diagrams → diagram.jinja)
- **[high|M|TODO|B1-B4,A3] D1. Implement the 3 missing detectors** — `before_after` (from ergebnis_metrics pairs), `process_flow` (from schritte), `q_a` (from irrtuemer): declared in `_PRIORITY` (5) but `_DETECTORS` has only 2. `plan_diagrams.py:42,98-101`.
- **[high|M|TODO|—] D2.** `_detect_convergence` is confirm-only (never authors); `_detect_stat_callout` returned None on all 15 pages → make them actually author. `plan_diagrams.py:74-94`.
- **[medium|S|TODO|—] D3. Relax the 0.62 headroom gate** for pure-diagram beats (drops diagrams on ~11 text-heavy pages). `plan_diagrams.py:160-168`.
- **[medium|S|TODO|—] D4. ST-07B page_mode guard** drops diagrams on the 3 theory pages. `plan_diagrams.py:130-133`.

## TRACK E — SPECIFIC WINS from data that ALREADY EXISTS *(fall out of A+B+C)*
- **[high|S|TODO|A1,B2] E1. Case-study `von 2 Std auf 20 Min` → real before/after bar** (ba_bars/transform_arrow) instead of a flat big-number string. Data present, just mis-shaped. `treatment_engine.py:371`.
- **[high|S|TODO|C1] E2. `horizontal_process` gauge is suppressed** (needs `td.result.figure`; ST-06 ergebnis text had no parseable %) → parse/synthesize a %-figure from ST-06 ergebnis (a figure-parser, closer to C1/synthesize than to B2's ST-07A metrics). `horizontal_process.html.jinja:41`.
- **[high|M|TODO|—] E3. `editorial` donut never renders** — ST-05 About wasn't selected as hero (`founder_identity`=NONE) so the needs_image editorial treatment never fit → relax hero selection OR host the donut in `a4_editorial_fill`. `treatment_stylist.py:211-227`.
- **[high|M|TODO|—] E4. `a3_case_study` ring never renders** — cases stayed A4 on the chart-less `a4_case_study` (no explicit A3 signal) → promote, OR add the ring/viz to `a4_case_study`. `treatment_stylist.py:254-272`.

## TRACK F — IMAGES & DEVICE MOCKUPS *(the Yosef axis — his images/mockups plug in here)*
- **[high|M|TODO|—] F1. One documented image door:** drop client files into `client_assets/<slug>/` with the drive-key filenames `resolve_slots` expects (case-study-N, proof*, about-portrait, *-logo). `build_live.py:399`, `resolve_slots.py:98-107`.
- **[high|S|TODO|—] F2. Fix `build_live.SLOT_TO_ST`** — maps only 5 bg/logo slots; `cover_author→portrait` is a DEAD mapping → add case_study_portrait/founder/about_portrait/proof/device. `build_live.py:51-57`.
- **[high|S|TODO|F2] F3. Fix `generate_assets.IMAGE_REQUIREMENTS`** — ST-01 only declares cover_hero/background, so a `portrait` item has no matching requirement and is never downloaded. `generate_assets.py:60-81,672-676`.
- **[medium|S|OWNER-GATED|—] F4. Set `FAL_KEY`** → generated cover/scene/fazit backgrounds + texture/gradient (all currently `stub_not_generated` → flat token gradient). `build_live.py:372`, `generate_assets.py:872-887`.
- **[high|XL|TODO|A4,F1] F5. Device-mockup pipeline:** ship a brand-agnostic device-frame PNG library (laptop/phone/iPad — NONE exist); wire `composite_device_mockup` (ZERO production callers) into a case-study treatment slot; keep composite slots alive through `assemble_package` (only `source=='drive'` survives today). `device_mockup.py:21`, `assemble_package.py:201-208`.
- **[medium|M|TODO|G2,A4] F6. `phone_mockup`** is read by `patterns/st_31.py` (the SOCIAL-DIVIDER page whose whole purpose is the mockup) AND `patterns/st_07a.py:206`; it needs `page.data.social` from the founder-scraper (which `build_live` never imports) → wire the scraper (or supply social assets). ALSO: treated ST-07A renders via the `a4_case_study` treatment, so the phone macro is off the legacy path → it needs a TREATMENT-level host too (the A4 master-gate logic). See ST-31 in Track J.
- **[low|L|TODO|F5] F7. Build laptop/iPad components** (spec'd in VISUAL_ASSETS.md; none exist).

## TRACK G — CONVERGE THE ORCHESTRATION (kill the "mycelium")
- **[high|L|TODO|—] G1. ONE assembler.** `service.py` → `build_live` (a drifted clone of `main.py:/render`) → converge into one canonical build; a THIRD (`build_package.py`) shares `route_package`. `service.py:117`, `main.py:/render`.
- **[high|M|TODO|G1] G2. build_live drops the founder-scrape/device stage + ship spine** → import them (this is what unblocks device mockups + social). `main.py:358-364`.
- **[medium|S|TODO|—] G3. Stage 8.5 try/except silently swallows the whole cadence/diagram pass** offline → surface the error. `build_live.py:462-472`.
- **[medium|S|TODO|G1] G4. build_live calls `route_package(manifest=None)`** → the entire social/proof_gallery/logo_wall binding block is skipped. `build_live.py:463`, `route_package.py:44-88`.
- **[medium|S|OWNER-GATED|—] G5. LLM copy-fit restructure key-gated OFF** → over-budget pages keep overflow/dead space (`OPENROUTER_API_KEY`). `route_package.py:96`.

## TRACK H — MAKE THE REFERENCE-PDF QC CONVERGENCE LOOP REAL *(the automation the owner designed)*
Exists as scaffolding (`research/quality_loop/`: reference PDFs, `references/classify.py`+`index.json`, `vis_prompt.py`+`vis_client.py`, `conductor.py`, `stage_converge.py`, `compose.py`) but never functioned as a live gate. **Prerequisite: H-grader (below) must read the Chromium artifact before H1 can wire the VISUAL grade in.**
- **[critical|M|TODO|A-F,H-grader] H1. Not wired into the ship path.** service.py: *"no inline auto-redo… separate offline tool"* — the inline compose loop that DID exist was removed in the Path-B rewrite (`service.py:11-15`). → re-wire CONVERGE into the live render. Depends on Tracks A–F (real knobs) AND H-grader (a grader that can read the shipped Chromium PDF).
- **[critical|L|TODO|A-F] H2. The compose-and-emit path EXISTS but only merges ONE knob and was unwired.** `compose.py::compose_converged_package` is implemented + was shipped once (REBUILD-LOG 2026-07-04 apex_v3_converged), but it merges only the per-page `layout_variant` knob — NOT density or any richer knob — and the inline loop was later removed from ship. → extend compose to carry every knob + re-wire it. `stage_converge.py:131-146`, `compose.py`.
- **[critical|L|TODO|A-F] H3. The conductor's live knobs only address dead-space (N08); NONE inserts richness.** It has TWO renderer knobs — `density` (line-spacing) and `case_study_layout` standard→fill for {ST-07A,ST-22,ST-FAZIT} (`conductor.py:51,67-69,160-173,275,360-378`; the "single knob" top-of-file docstring is STALE) — but it cannot add a chart/mockup/diagram/image/treatment-swap. → add richness knobs (insert chart/mockup/diagram, swap treatment, add image). Only POSSIBLE after Tracks A–F. `conductor.py` LAYOUT_LADDER/DEFECT_KNOBS.
- **[critical|M|TODO|K1] H-grader (was H4+K3, merged; PREREQUISITE of H1). The visual grade + reference comparison is WeasyPrint-calibrated and cannot read the Chromium ship PDF** — N03 `display_font_embedded` is a HARD-FAIL row (`rubric.py:118-119`) that latches on every Chromium page (PyMuPDF returns no font table) → the grader reports a clean deck as 0-cleared (`service.py:44-51`, `perception.py:33-36`). Until this is recalibrated for Chromium, a wired loop fails-closed on every page regardless of A–F.
- **[critical|M|TODO|—] H4. Reference index covers only ~4 of the deck's page types — the comparison the whole system is named after is unwired for the majority.** `references/classify.py:32-39` emits a CLOSED SET of 6 labels; the built index is `OTHER:54, ST-07A:16, ST-01:6, ST-FAZIT:4, ST-05:3, LOGO-WALL:1`, and `retrieve_references` matches on exact `st_type ==` (`references/__init__.py:34`). So generated **ST-02/ST-06/ST-07B/ST-09/ST-14/ST-22/ST-03** pages match NOTHING → the vision grader gets 0 reference images (~9 of 15 pages). → classify the reference corpus into ALL page types (or a fuzzy fallback) so every generated page has a same-type Richard reference.
- **[high|M|TODO|—] H5. Two known convergence-loop CRASH bugs** (ST-01 + an ST-07A page) are swallowed into error PageResults (`brain.converge_deck:554-568`) → those pages silently never converge. Must fix before H1/H2 are real. (REBUILD-LOG 2026-07-04.)
- **[high|S|TODO|H2] H6. Disk-hygiene / compose self-recursion (the "20GB" trap).** `compose_converged_package` copied the package into itself → ENAMETOOLONG + 20GB ENOSPC that killed the run; fixed with `ignore_patterns("out","__pycache__")` but the service MUST delete `converge/pages` + `converge/merged` after composing. Any re-wiring of H1/H2 must carry this or the loop dies on disk. `compose.py`.
- **[medium|M|TODO|—] H7. Most rubric rows are not deterministically scorable + one blind spot that matters once charts render.** ~13 of 16 positive rows + several negatives carry `fact_key=None` ("needs_fact", `rubric.py`) — notably **N13 empty/stub-chart** (`:148`) is blind, so once Tracks A/B produce charts the grader cannot detect an empty/stub chart frame; DET∧VIS rows are skipped without the vision key. Also ensure **running header/footer furniture** (P08/N09, LIVE via `header_furniture_present` `perception.py:371-381`) renders — the grader rewards/penalizes it.

## TRACK I — WRITER / UPSTREAM SUBSTANCE *(the deepest cause; n8n lane)*
- **[high|M|CROSS-SESSION|—] I1. Writer schema is contractually TEXT-ONLY** (`writer-prompt-v3.md:136` "Add no key not in the schema"); only quantitative field = ergebnis_metrics (3 pages). → decide: (a) manufacture visuals from prose via the adapter/synthesizer (Tracks B/C, no writer change) AND/OR (b) extend the schema with explicit chart/viz/image keys for author-driven richness.
- **[high|M|CROSS-SESSION|—] I2. Only 3 of 15 pages carry any number** → richer, figure-bearing copy (content-gap-audit / writer-prompt) so more pages HAVE something to visualize. `content-gap-audit.md:43-66`.
- **[—|—|NOTE|—] I3. HONEST CEILING:** Tracks B/C from existing data yield "process flows + comparisons + a few gauges," NOT a full Power-BI dashboard. The full dashboard needs I1/I2 (real numeric data) + A5 (a4_bi_dashboard).

## TRACK J — RESIDUAL DEAD-SPACE / PER-TREATMENT POLISH *(from the deck walkthrough)*
- **[medium|M|TODO|A2] J1. `a4_case_study` lower-LEFT narrative void** (dark right rail is full). p6/8/10.
- **[medium|M|TODO|—] J2. `horizontal_process` (A3 mechanism)** — cards leave lower ~40% empty; doesn't stretch vertically. p12.
- **[low|S|TODO|—] J3. ST-14 beliefs (legacy pattern)** — room below the last item. p5.
- **[low|—|→Track I|I2] J4. ST-22 / thin closing pages** — gap before CTA = thin writer copy. p14.
- **[medium|S|TODO|—] J5. 10 of 16 registered treatments are unbuilt stubs** (glass_card, split_portrait, a4_metric_column, a4_two_stack, a4_dark_divider, a4_quote_portrait, a4_side_rail, a4_stacked_hero, a4_portrait_card, a4_bi_dashboard) → build the useful ones (A5) or remove from candidate lists so they don't shadow/mislead. `treatment_catalog.py:83-105`.
- **[medium|M|TODO|F6,A4] J6. ST-31 social-divider page** — its whole purpose is the phone-mockup of the client's live social presence; the conductor flags it as a KNOWN under-fill (asset_gen/content: "no scene photo, no breather phrase," not renderer-fixable — `conductor.py:57-59`). Needs the social assets (F6) + a treatment host (A4). (Only appears when the deck includes an ST-31 page.)

## TRACK K — ENGINE / FONT / BRAND-COLOR / OVERFLOW HYGIENE
- **[high|M|TODO|—] K0. NO `brand_tokens{}` on the envelope → deck renders in DEFAULT/fallback brand colors, off-brand.** The christoph envelope top keys are `{meta,pages}` only — no `brand_tokens{}` — so every deck renders the same fallback palette instead of the client's, and `perception.min_text_contrast` grades against fallback `brand_neutral_dark/light`. Distinct from the font bug (K1). → ensure the envelope carries brand_tokens (n8n lane) + `build_live`'s brand resolver uses them. `perception.py:212-222`.
- **[medium|M|TODO|—] K1. Brand display font silent fallback.** Ship display face is **Source Serif 4** (`perception.py:33`); format-4-cmap-only faces (Montserrat/etc.) silently fall back to PT-Serif/Hiragino (`perception.py:36`). This drives **N03 `display_font_embedded`, a HARD-FAIL row** (`rubric.py:118`) — and N03 latching on the fontless Chromium PDF is the actual mechanism behind H-grader's "0-cleared." → bundle/alias brand faces to a real embedded face.
- **[medium|S|TODO|G5] K2. Overflow / physical-spill** — the gate exists but spills historically shipped; ensure no page overflows (copy-fit is key-gated, see G5). NOTE: N04 catches only PAGE-BOUNDS overflow, not text spilling a chart's circle/panel (`perception.py:163-192`) — once charts render, within-viz overflow is only caught by the (unwired) vision grader.
- **[—|—|MERGED→H-grader|—] K3.** (Perception grader WeasyPrint-calibrated / can't read Chromium fonts) — merged into **H-grader** in Track H; it is a PREREQUISITE of wiring the loop (H1), not a standalone downstream item.

---

## THE ACCEPTANCE MEASURE (how "done" is judged from now on)
Render the **real** envelope → open the **final** PDF → **count** visible charts / diagrams / mockups /
images per page → cross-check **generated-vs-visible** (catch produced-but-invisible, like the ST-06 SVG)
→ and once Track H is real, **converge each page to its selected Richard reference**. Not tests, not
HTTP 200, not %PDF bytes, not a page slice.

## RECOMMENDED EXECUTION ORDER (dependency-correct; adjustable to your ranking)
1. **Track A** (master gate: host slots) — A1→A2→A3→A4, then A5 later.
2. **Track B** (German→contract adapter) — B1/B2 first (highest leverage), then B3/B4/B5/B6/B7.
3. **Track C** (enrich synthesize_visuals).
4. **Track E** (specific wins that fall out of A+B+C).
5. **Track D** (diagram detectors).
6. **Track F** (images/mockups — Yosef's axis; F1–F3 now, F4 owner-gated, F5–F7 larger).
7. **Track G** (converge orchestration; unlocks founder/device path).
8. **Track H** (make the reference-QC loop real). Order WITHIN H: H-grader (Chromium recalibration) + H4 (broaden the reference index to all page types) + H5 (crash bugs) + H6 (disk hygiene) are PREREQUISITES; then H1/H2/H3 (wire + compose-all-knobs + richness knobs) — and H3's richness knobs need A–F to exist.
9. **Track K0/K1** (brand-tokens palette + font embedding) — do alongside H because they feed the grader (K1 drives the N03 hard-fail); K0 (off-brand color) is independently high-value for appeal.
10. **Track I** (writer substance — n8n lane; raises the ceiling).
11. **Tracks J / rest of K** (polish + hygiene — ongoing, some fall out of A/G).

---
## STATUS SYNC 2026-07-13 (end of day; see docs/SESSION-STATE-2026-07-13.md for detail)
DONE since the last sync: F1/F2-partial/F4 (client-assets door live w/ founder+5 product mockups; FAL key loaded + all generations cached; SLOT_TO_ST untouched beyond existing), bildwunsch->product routing + ST-06 hero default, fal scene-band host, About portrait-rail, st_14 one-row proof band + donut gradient restore, footer chrome alignment, horizontal_process rebuilt to the reference anatomy (J2 superseded), K-partial (.env loading; httpx timeout).
NEW DEFECTS (owner screenshots 2026-07-13 night, all TODO):
- **[critical] D1a ST-FAZIT rail misfire** — portrait-rail variant keyed on bare td.image; ST-FAZIT slot recipe carries founder_hero so the rail fires there (empty navy column). Gate the variant to ST-05.
- **[critical] D1b ST-FAZIT hero-quote clipped** mid-word (28pt statement in the rail-narrowed 58% column).
- **[critical] D1c ST-FAZIT sceneband/CTA overlap** — the fazit "background" asset must not render as a 40mm strip; foot collides.
- **[high] D2 ST-03 back cover ~60% void** (lone geo triangle) — rebuild to reference closers (boss p10 / niklas p20 / aerztepartner p11).
- **[high] D4a case-study left-foot void returns on device-less cases** (3/4/5) + **D4b weak statement-stat styling** (hyphenated prose values, "(vorher:)" parentheticals) + **D4c NN avatar monotony** (5 identical).
- **[medium] D3 ST-22 middle void** (thin copy; writer lever or designed middle device).
- **[medium] D5 cover photo soft** (500px source; owner decision hi-res vs gating).
- **[medium] D6 scene band = crop strip** — references integrate photos as duotone plates/full-bleed grounds w/ overlapping mockups.
- **[high] Container is STALE** vs tonight's local code — rebuild + verify over HTTP when the dust settles.
GATING: owner gives the authoritative detailed feedback AFTER compaction — reconcile this list against his, fix reference-first (retrieve Richard's same-type page before touching any treatment).

---
## STATUS SYNC 2026-07-16 — READ `docs/STATE-OF-THE-BUILD.md` FIRST

CLOSED since the last sync (all pixel-verified, see REBUILD-LOG 07-14/15/16):
- D1 FAZIT rail misfire + quote clip + scene/CTA collision -> variant contract.
- D2 ST-03 back-cover void -> full-bleed atmosphere closer.
- D3 ST-22 middle void -> ablauf_text sentences become verbatim numbered steps.
- D4 case-study feet/stat styling/avatar monotony -> device completion (every
  case now carries a DIFFERENT product mockup), s.sub citations, paren-split.
- D6 scene crop-strip -> duotone plate.
- The fake bleeds (cream halos on every rail) -> tp-rail bleed routing.
- The ~85% SILENT GLOBAL SHRINK -> deck now prints at TRUE design scale.
- Montserrat -> the deck finally renders in the brand face.
- Container -> rebuilt, live, ships client_assets.

D5 (cover photo) STILL OPEN: owner must supply a hi-res founder photo.

**THE BACKLOG'S CENTRE OF GRAVITY HAS MOVED.** The remaining "visual appeal" gap
is no longer voids/treatments — it is the DEVICE VOCABULARY: the renderer draws
16 presets, the adapter emits 4, so 12 are built-and-unreachable and every page
reads the same. That is now the #1 item and it is a 3-layer fix (A writer
contract [owner's n8n lane, gates the ceiling] / B role->device selector / C
missing primitives + an icon set). Catalog + role->device table:
`docs/DEVICE-VOCABULARY-GAP-2026-07-16.md`. Owner's go pending as of 2026-07-16.
