# Treatment System Build — Implementation Plan (v2, post-audit)

> **PROGRESS BANNER (2026-06-20):** Phase 0 + Phase 1 are BUILT + green. The AS-BUILT reality (which diverged from this plan via user feedback: editorial moved to the ABOUT page, ST-06 became a new `horizontal_process` treatment, a `qc_dead_space` gate was added, and the premium textures/footer pivoted to AI img2img generation) is documented atom-level in `docs/superpowers/CURRENT-STATE.md` §A-H (READ THAT FIRST) + memories [[treatment-library-state]], [[ai-decorative-assets]], [[regressions-and-guardrails]]. Phases 2-4 below (port the remaining treatments) are still the forward plan. The board has tasks TS-2.1..TS-4 + AI-FIRE/AI-WIRE/FIX/AI-STUB.

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).
> **v2 supersedes v1.** v1 was audited (4-auditor adversarial pass, 2026-06-18) and found NOT safe to execute: 6 critical, 8 high, 20 medium/low issues. Every confirmed finding is folded in below. Read "Audit corrections" first.

**Goal:** Bake the reviewed treatments into the v7 renderer as responsive, data-driven layouts, plus a `treatment_stylist` that assigns a treatment + page format (A3-landscape / A4-portrait) to each *eligible* deck page (by role, no two neighbours alike, data-gated), so the apex deck — and future decks — render with varied premium layouts that reflow with real content and never lose page chrome.

**Architecture:** `treatment_stylist` runs **inside `assembler.render_package()` immediately after `pkg = load_package(...)`** (assembler.py:571), gated by a `treatments: bool` param threaded from a `render.py --treatments` flag (**default OFF** until Phase 3 sign-off — this is also the rollback, since this tree is not under git). It annotates each *eligible* page with `treatment` + `page_format` (only when the page's data can populate that treatment's required fields, including a resolved image when the treatment is image-led). `treatment_engine.adapt(page, ctx)` maps the page's real data into a normalised `TreatmentData`; `treatment_engine.render` picks the template+CSS and returns a `PageFragment` — called **inside the existing dispatch try/except** (assembler.py:582-593) so a raising treatment degrades to `_generic`, never crashes. The assembler stamps `.page.treatment-<name>.format-<a3|a4>` and gains named `@page a3-landscape`/`@page a4-portrait` rules that **replicate the full margin-box chrome** (header + folio) and a **format-aware `min-height`**. Chromium-only. Treatments **reuse the existing `components/` macros + code-drawn viz** (no duplicate library). All token-driven, brand-agnostic; consume already-resolved package assets only.

**Tech Stack:** Python 3, Jinja2, Chromium (Playwright) `page.pdf(prefer_css_page_size=True)`, Ghostscript flatten, PyMuPDF, pytest. Dir `research/v7-renderer`; env `source .venv/bin/activate`, `export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`.

**Non-goals (explicit):** No fal / asset generation / `design_brief` — treatments consume `ctx.slot_uri`-resolved assets only (the wiring boundary that's been re-litigated 3×; keep it OUT). No re-skin of cover (ST-01), back-cover (ST-03), breathers (ST-31), or dark dividers (ST-07B) — these keep their existing full-bleed/special pages (bypass set). No git operations (this tree isn't a repo; rollback = the `--treatments` flag).

---

## Audit corrections (what v1 got wrong — do not regress)

**Critical:**
1. **Wiring point.** `render.py:112` has no `pkg`; `load_package` is at `assembler.py:571`. Stylist runs there, behind a `treatments` param, default OFF.
2. **A4 `min-height` spills A3.** `assembler.py:401` sets `.page{min-height:261mm}` (A4 box) + a `.page` border (`:530`). On A3-landscape (~259mm printable height) this forces a blank 2nd physical page per logical page — and trips the Chromium page-count validator (`assembler.py:702`). Fix: format-aware min-height (`.page.format-a3{min-height:0}` + flex, or A3 content height), suppress the `.page` border on treatment pages, and **assert physical==logical page count** in the Phase-0 test.
3. **Header/folio chrome doesn't inherit.** It's on the base `@page` margin-boxes only (`assembler.py:220-237` Chromium, `:242-252` WeasyPrint); `@page cover`/`bleed` must re-declare `content:none` *because there's no inheritance*. The named `@page a3-landscape`/`a4-portrait` must **replicate the full margin-box chrome** (landscape-sized), both engine branches. Test: folio+header present on a rendered A3 and A4 page.
4. **Role→treatment mapping** must be explicit for all 12 apex st_types, with a proven feasible assignment (see tables below).
5. **A3 anchors must be data-gated.** "before/after" and "hero case study" had no data; A3 promotion is now conditional on resolved data + an explicit `page_role` flag.
6. **The static conformance gate proves nothing about treatments** (`test_design_conformance.py:42-105` never renders). Add a real rasterise+sample check + a `styles/treatments/*.css` forbidden-value scan.

**High:** no-literals guard is non-recursive (`glob('*.jinja')`) — make it `rglob` and run per-treatment from Phase 1; the Stage-9 convergence loop (default ON unless `--fast`) grades by st_type against A4 refs and will false-flag A3/treatment pages — gate it OFF for treatment pages + grade vs the committed mockup refs; dark panels must ground on `var(--color-ink)` with `var(--color-on-dark)` numerals (the shipped-and-fixed invisible-stat bug, since apex primary==accent) — extend `test_panel_contrast.py`; the mockups are **absolute-positioned rebuilds, not ports** — reclassify by reflow difficulty + test with longest real copy; **4/5 case-study portraits are `miss`** — stylist must be image-aware; treatments must honour the never-crash + a per-treatment min-data contract; persist-or-render-time decision for the frozen fixture; **copy the /tmp mockups into the repo** (volatile).

**Medium/Low (folded into tasks/porting rule):** objective pixel-match gate (committed ref PNG + diff threshold); re-baseline `test_visual_regression` after sign-off; reconcile the 3 layout systems (st_type / layout_type / treatment); skip the WeasyPrint overflow path for treatment pages; measure sizes on the **gs-flattened** `report.pdf`; assert mixed raster dims; A3/A4 are **distinct templates** (not one conditional template) sharing an archetype tag; scan templates for fabricated apex defaults; stylist constraint-relaxation order (relax cap before no-adjacent-repeat, never crash) + A4-heavy stress test; map every non-token mockup shade to a token explicitly; **reuse `components/` macros** (eyebrow, two_tone_headline, stat_strip, viz donut/bar, media_figure, before_after) — no `_t_macros` dup; strip em-dashes from authored text (U+2014 in 12/44 mockups) + regression scan; treatment CSS uses only `var(--font-*)` (only Source Serif 4 + Sans 3 embed); replace inert git steps with the flag-based rollback; correct stale cites at implementation time.

---

## Real apex deck (20 pages, verified from resolved_package.json)

| idx | st_type | mode | image | data | → eligibility |
|--|--|--|--|--|--|
|0|ST-01|cover|founder ✓|—|**bypass** (legacy cover)|
|1|ST-02|—|—|viz|treatment (data/outlook)|
|2|ST-05|—|portrait ✗, logos ✗|—|treatment (about, no-image variant)|
|3|ST-09|—|—|viz|treatment (data/status-quo)|
|4|ST-14|—|—|—|treatment (myths/belief rows)|
|5|ST-31|—|—|—|**bypass** (breather)|
|6|ST-07A|—|portrait ✗|metrics,quote,viz,kunde|treatment (case, no-image)|
|7|ST-07B|dark_divider|—|—|**bypass** (dark divider)|
|8|ST-07A|—|portrait ✗|metrics,quote,viz,kunde|treatment (case, no-image)|
|9|ST-07B|dark_divider|—|—|**bypass**|
|10|ST-31|—|—|—|**bypass** (breather)|
|11|ST-07A|—|**portrait ✓**|metrics,quote,viz,kunde|treatment (**hero** case, image-led, A3)|
|12|ST-07B|dark_divider|—|—|**bypass**|
|13|ST-07A|—|portrait ✗|metrics,quote,viz,kunde|treatment (case, no-image)|
|14|ST-07A|—|portrait ✗|metrics,quote,viz,kunde|treatment (case, no-image)|
|15|ST-06|—|—|—|treatment (process/mechanism)|
|16|ST-31|—|—|—|**bypass** (breather)|
|17|ST-FAZIT|—|founder ✓|viz|treatment (summary, image ok)|
|18|ST-22|—|—|—|treatment (5-step process)|
|19|ST-03|—|—|—|**bypass** (legacy back-cover CTA)|

**Bypass set (8 pages keep legacy patterns):** ST-01, ST-03, 3×ST-31, 3×ST-07B. **Treatment-eligible (12):** ST-02, ST-05, ST-09, ST-14, 5×ST-07A, ST-06, ST-FAZIT, ST-22. Constraint hotspots: idx 13/14 adjacent ST-07A (must differ); only idx 11 has an image.

## st_type → role → candidate treatments (A4 unless noted)

| st_type | role | candidate treatments (data-gated) |
|--|--|--|
| ST-02 | outlook/data | a4_bi_dashboard, a4_metric_column, a4_two_stack |
| ST-05 | about/authority | a4_side_rail*, a4_metric_column, a4_dark_divider (*portrait absent → side_rail must have a no-image variant) |
| ST-09 | status-quo/data | a4_metric_column, a4_bi_dashboard, a4_dark_divider |
| ST-14 | myths/belief | a4_two_stack, a4_metric_column, a4_stacked_hero (text-led) |
| ST-07A (hero, idx11, image✓) | case-study hero | **editorial (A3)**, glass_card (A3), split_portrait (A3) |
| ST-07A (no image) | case-study | a4_two_stack, a4_quote_portrait(no-image→quote-led), a4_metric_column, a4_dark_divider, a4_bi_dashboard (rotate so 13≠14) |
| ST-06 | process | a4_vertical_timeline |
| ST-22 | 5-step process | a4_vertical_timeline (alt), a4_metric_column |
| ST-FAZIT | summary | a4_stacked_hero, a4_two_stack, a4_portrait_card (founder✓) |

**A3 promotion (data-gated):** idx 11 (hero, image✓) → editorial A3. Optionally one data page (ST-02 or ST-09) → bi_dashboard A3 if it reads well; capped at ≤3, only when data supports the wide canvas. `before_after` is NOT forced onto apex (no page-level vorher/nachher dataset; its `ba_bars` viz lives inside case studies) — it stays in the library, available when a deck has the data. The hero ST-07A is identified by a `page_role:"hero"` flag set in `build_package` (Task 1.3a), not guessed.

---

## File structure

- `treatment_stylist.py` (assignment: eligibility, role, candidates, data-fit + image-aware gate, no-adjacent-repeat, cap with relaxation order, A3 promotion, audit log).
- `treatment_engine.py` (`TreatmentData`, `adapt`, `render` dispatch, `TREATMENTS` registry with per-treatment `required_fields`/`needs_image`/`formats`/`archetype`).
- `treatments/refs/` — **copied** mockup HTML + reference PNGs (canonical spec; not `/tmp`).
- `templates/treatments/<name>.html.jinja` (distinct per name; **import `components/` macros**, minimal `_t_compose.jinja` only for novel composition).
- `styles/treatments/<name>.css` (scoped `.page.treatment-<name>[.format-*]`, tokens only, ink-grounded dark panels).
- Modify `assembler.py`: named `@page` rules + chrome replication + format-aware min-height/border (head CSS ~:267-315 & :401/:530); `_section()` classes (~:543-562); stylist call after :571; treatment branch inside dispatch try/except (:577-594); skip WeasyPrint overflow path for treatment/A3 pages (:707-718).
- Modify `render.py`: `--treatments` flag (default OFF) threaded to `render_package`; Stage-9 convergence gated OFF for treatment pages (or treatment+format-aware refs).
- Tests: `test_treatment_pagesize.py` (dims **+ page count + chrome present**, on the gs-flattened pdf), `test_treatment_stylist.py`, `test_treatment_engine.py`, `test_treatment_conformance.py` (rasterise+sample + css forbidden-value scan), extend `test_panel_contrast.py`, extend `test_no_literals_in_architecture.py` (rglob), em-dash scan, longest-copy overflow test; re-baseline `test_visual_regression`.
- Docs: `docs/treatments.md`; update `CURRENT-STATE.md`; memory `treatment-library-state.md`.

---

## Phase 0 — De-risk + foundation (must pass before any porting)

### Task 0.1 — Copy mockups into the repo
- [ ] Copy all reviewed mockups (`/tmp/treat_*.html`, `/tmp/fb_uniform.html`, `/tmp/rep_*.html`, `/tmp/a4_*.html`, `/tmp/treat_editorial_v2.html`, `/tmp/treat_before_after_v2.html`) + their `output/*.png` renders into `research/v7-renderer/treatments/refs/`. Re-point all later steps at repo paths.

### Task 0.2 — Page-size + chrome + page-count spike (frozen as regression)
- [ ] Add named `@page a3-landscape{size:A3 landscape;margin:…}` / `@page a4-portrait{size:A4 portrait;margin:…}` to `shared_head_css`, **each replicating the full margin-box chrome** (Chromium `@top-left/@top-right/@bottom-right` wordmark+CTA+`counter(page)`; WeasyPrint `@top-center element(pageheader)`+`@bottom-right string(pagefolio)`), landscape-sized. Add `.page.format-a3{page:a3-landscape;min-height:0;border:none}` / `.page.format-a4{page:a4-portrait}`.
- [ ] `test_treatment_pagesize.py`: render a 3-section doc (A3, A4, A3) via the **real assembler Chromium path incl. gs flatten**; open the **flattened `report.pdf`** with fitz; assert (a) page sizes 420×297 / 210×297 / 420×297 (±3pt), (b) **page_count == 3** (no spill), (c) rasterise and assert the two A3 PNGs and the A4 PNG open at the expected differing dims, (d) header text + folio appear on an A3 and an A4 page (sample pixels or text). Expected PASS. If page-size survives gs but count fails → apply the min-height/border fix and re-run. If gs normalises sizes → switch to per-page single-size PDFs concatenated in deck order (corrected fallback), or escalate.

### Task 0.3 — Recursive brand-agnostic guard (active from now on)
- [ ] Change `test_no_literals_in_architecture.py` globs to `rglob('*.jinja')`/`rglob('*.css')` and include `treatment_stylist.py`/`treatment_engine.py`; add a U+2014 (em-dash) scan over `templates/treatments`+`styles/treatments`. Runs RED until each ported treatment is token-clean + em-dash-free. (Genuine German DATA is exempt; authored chrome/comments are not.)

---

## Phase 1 — Engine + stylist + 2-treatment vertical slice

### Task 1.1 — `TreatmentData` + `adapt` (+ grounding & fabrication guards)
- [ ] Failing test: `adapt(page, ctx)` on real apex pages returns grounded fields, raises nothing on missing data, and a `fabrication` scan finds NO apex literal baked as a template default. Implement `TreatmentData` + `adapt` (generic + per-st_type overrides), images via `ctx.slot_uri/slot_uris`.

### Task 1.2 — `TREATMENTS` registry + dispatch (reusing components/)
- [ ] Failing test: `render(page,ctx)` for `editorial`/`a3` returns the right fragment; unknown treatment AND known-treatment-missing-required-data both fall back safely. Implement registry (`required_fields`, `needs_image`, `formats`, `archetype`), dispatch importing existing `components/` macros.

### Task 1.3 — `treatment_stylist` (eligibility, data-fit, image-aware, constraints)
- [ ] Failing tests: bypass set never assigned a treatment; eligible pages get a treatment whose required data (and image, if `needs_image`) is present; no two adjacent treated pages share a treatment (verify on idx 13/14); cap respected with documented relaxation order (relax cap → relax variety → never crash); A3 promotion only on `page_role:"hero"`/data-gated pages; deterministic (index-seeded). Implement; return an audit list.
- [ ] **Task 1.3a** — set `page_role:"hero"` on the image-bearing ST-07A (idx 11) in `build_package.py` (the only persistence touch; see Task 3.3 for the rest).

### Task 1.4 — Assembler + render.py wiring
- [ ] `_section()` adds `treatment-<name>`+`format-<fmt>` classes. Stylist called in `render_package` after `load_package` (assembler.py:571) behind `treatments` param. Treatment branch INSIDE the dispatch try/except (:582-593). Skip the WeasyPrint overflow path for treatment/A3 sections (:707-718). `render.py --treatments` (default OFF) + Stage-9 gated OFF for treatment pages.

### Task 1.5 — Author 2 slice treatments + integration
- [ ] Port `editorial` (A3, image-led, from `treatments/refs/treat_editorial_v2.html`) and `a4_vertical_timeline` (A4) via the Porting Procedure. Force a 3-page test package (cover-bypass A4 + editorial A3 + timeline A4), clean render, READ all PNGs vs refs, assert sizes/count/chrome, run `test_treatment_conformance` + `test_panel_contrast` + no-literals. Iterate to clean.

---

## Porting Procedure (per treatment — the medium/low fixes live here)
1. Read `treatments/refs/<key>.html` + its PNG.
2. New `templates/treatments/<name>.html.jinja`: replace apex literals with `TreatmentData` fields + **imported `components/` macros**; rebuild absolute-positioned blocks as responsive flex/grid (mm/%/rem) that fill the @page content box and reflow. (A3 and A4 of an archetype are **separate templates**.)
3. New `styles/treatments/<name>.css` scoped to `.page.treatment-<name>[.format-*]`: map every mockup hex to a token (define derived tints or collapse-to-3, verify on pixels); **dark panels ground on `var(--color-ink)`, dark numerals `var(--color-on-dark)`** (never `--color-primary`/`--color-accent`); `var(--font-*)` only; strip em-dashes from authored text; honour native-aspect image boxes; fix the known mockup nits.
4. Register in `TREATMENTS` (required_fields, needs_image, formats, archetype).
5. Render the mapped apex page (or a single-page harness) **with the LONGEST real apex field values**; READ the PNG vs the ref; gate on: pixel-match (committed ref PNG + diff threshold, or vision rubric), no overflow/no-extra-page, faces intact, panel-contrast numeric pass, conformance sample, no-literals + em-dash green. Iterate to clean.
6. Checkpoint (copy changed files to a timestamped backup dir; no git here).

## Phase 2 — Port the apex-used treatments first, then the rest of the library
- [ ] 2.1 Apex-critical: a4_vertical_timeline (done 1.5), editorial (done 1.5), a4_bi_dashboard, a4_metric_column, a4_two_stack, a4_dark_divider, a4_quote_portrait(+no-image variant), a4_side_rail(+no-image variant), a4_stacked_hero, glass_card(A3). (These cover the 12 eligible apex pages.) Each via the Procedure, verified in-deck.
- [ ] 2.2 Remaining library (not used by apex yet, for future decks): before_after (ba_bars adapter), mega_quote, diptych, zigzag, bi_dashboard(A3), stat_band, centered_hero, left_rail, split_portrait, fullbleed_overlay, three_column, photo_grid, timeline_h, dark_stat_hero, a4_top_image, a4_portrait_card. Reclassify by reflow difficulty; budget absolute-heavy ones (editorial, diptych, glass_card, dark_stat_hero, fullbleed_overlay) as multi-step responsive redesigns.

## Phase 3 — Whole-deck integration + tuning
- [ ] 3.1 Run the stylist on apex; log + eyeball the concrete 20-row assignment; confirm bypass set untouched, no-adjacent-repeat holds (13/14), A3 set data-gated.
- [ ] 3.2 Full **clean non-fast** Chromium render with `--treatments` ON; rasterise; READ every page; no overflow/spill; mixed sizes correct on the flattened pdf; chrome present; premium feel.
- [ ] 3.3 Decide persistence: keep render-time stylist; rewrite the wiring-gate row to assert `treatment-<name>` classes in the **rendered report.html** after a clean rebuild (not the JSON). Run `test_design_conformance` + the new `test_treatment_conformance` + wiring gate. Reconcile layout systems (map each treatment→a `layout_type` or update the conformance variety test to assert treatment variety).
- [ ] 3.4 Re-baseline `test_visual_regression` (`UPDATE_BASELINES=1`) after sign-off; update the xfail reason; capture mixed-size PNGs. Set a render-time performance budget. Present the full deck.

## Phase 4 — Guardrails, docs, memory
- [ ] 4.1 Confirm recursive no-literals + em-dash + panel-contrast + treatment-conformance all green across `treatments/`.
- [ ] 4.2 `docs/treatments.md` (catalogue: role, formats, data contract, ref). Flip `--treatments` default ON for apex once green.
- [ ] 4.3 Update `CURRENT-STATE.md` + memory `treatment-library-state.md` (BUILT; final assignment).

---

## Self-review
- All 6 critical + 8 high audit findings have a dedicated task or are gated in Phase 0/1 (not deferred). Medium/low live in the Porting Procedure + Phase 3/4.
- The assignment is grounded in the verified 20-page apex order (not hand-waved); feasibility is proven by `test_treatment_stylist` on the real package, with a documented relaxation order so it can't deadlock.
- Image-led treatments are data-gated (4/5 portraits are `miss`); dark panels carry the ink-grounding rule (the fixed invisible-stat bug); chrome + page-count are asserted on the flattened PDF; the static conformance gate is replaced by a real pixel/CSS check.
- Rollback is the `--treatments` flag (default OFF; this tree isn't git). fal/design_brief explicitly out of scope.
