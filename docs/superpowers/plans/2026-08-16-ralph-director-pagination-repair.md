# Director Pagination Repair — Ralph Plan (2026-08-16)

> **For agentic workers:** execute one story per Ralph iteration. NEVER mark a
> story complete from markup/tests alone — the acceptance artifact is the
> rendered PNG of the affected page/arc plus a physical-page-count check.
> Evidence file: `/tmp/vision_audit_20.json` (full per-page defect JSON).

**Goal:** Replace the fixed one-page section skeleton with a reference-grounded
Director and an explicit section→physical-page plan, so real content expands
cleanly across pages. Pilot: the still-clipped `30-50%` (p16) and the
p18→p19 contamination.

**Architecture:** Keep the renderer page-oriented; insert a planning seam before
it. A logical report section owns source content, references, claims, and a page
arc. The preprocessor expands it into one or more physical page plans with
continuation identity, format, regions, and device assignments. The renderer
consumes those plans. QA runs on the FINAL composed artifact with the real
references and Director metadata.

**Tech stack:** Python 3.11, Pydantic v2, Jinja, CSS paged media,
Chromium/Playwright, PyMuPDF, OpenRouter vision (`VisionClient`),
Supabase Director catalog, `scripts/ralph/prd.json`.

---

## Non-negotiable rules

- A section may use any number of physical pages its content and chosen arc
  require. `page_count_target` is a soft target — never a reason to clip,
  squeeze, or merge sections.
- A continuation page carries explicit `section_id`, `continuation_index`,
  `continuation_role`, `page_id`. A section's content ends before the next
  section's page begins (no p18→p19 bleed).
- Every figure stays grounded in the source section's own copy (no fabrication).
- Fal = contextual art only; renderer-native devices own numbers/charts/arrows.
- The final visual gate inspects the FINAL composed PDF with real reference
  images and Director metadata. A zero-reference score is not acceptance.
- Reopen US-402, US-403, US-408, US-509, US-510 in `prd.json` (passes=false).

## Current evidence (20/20 pages fail)

| Page | Worst defect |
|---|---|
| p16 | `30-50%` clipped — `clientWidth=111px` vs `scrollWidth=176px`; '%' cut off |
| p18→p19 | Founder headshot/name bleeds into ST-22 banner; ST-22 header obscured |
| p15 | 'ohne Headco…' hard-clipped at right page edge |
| p12 | Arrow device: 'MIT APEX → Minuten' with NO destination number |
| p7 | KPIs '> 200.000 €' + '4 automatisierte Kernprozesse' rendered twice |
| p5 | Venn overprints item-3 text |
| p2 | Ring sizes inconsistent ('30 bis 50 %' ring smaller) |
| p8/p10/p13 | Dark theory pages: bottom ~40% empty |
| p20 | Lower half ~45% empty; ghost '20' clipped at page edges |

Full JSON: `/tmp/vision_audit_20.json`.

---

## Ralph stories

### US-601 — Make the 30-50% clip a hard regression

**Files:** `research/v7-renderer/styles/st_06.css`, `templates/st_06.html.jinja`,
`patterns/st_06.py`, new `tests/test_st06_pagination.py`

**Acceptance:**
- Render p16; the value node satisfies `scrollWidth <= clientWidth` (no clip).
- The stat gets a real region with enough width — no letter-spacing/font-size
  shrinking to hide the problem.
- ST-06 may legitimately expand to two physical pages; the value must stay whole.
- Read `output/report-p16.png` after rendering; confirm visually.

### US-602 — Logical-section and physical-page identity

**Files:** `research/preprocessor/stages/plan_layout.py`,
`models_package.py`, `stages/assemble_package.py`,
`research/v7-renderer/package_loader.py`, related tests

**Acceptance:** Every emitted physical page carries
`{page_id, section_id, source_slot, continuation_index, continuation_role,
section_page_count, page_format}`. `pages[]` stays renderer-friendly but no
longer implies 1 section = 1 sheet. `page_count_target` is metadata, not a
truncation bound.

### US-603 — Section pagination planner (semantic split)

**Files:** create `research/preprocessor/stages/plan_section_pages.py`; modify
`plan_layout.py`, `assemble_package.py`; new tests.

**Acceptance:** short section → 1 page; heavy section → 2+ pages at semantic
boundaries (intro/mechanism/proof/result/close roles); source blocks appear
exactly once; continuations never interleave sections.

### US-604 — ST-06 two-page pilot

**Files:** `research/v7-renderer/patterns/st_06.py`, `templates/st_06.html.jinja`,
`styles/st_06.css`, `tests/test_st06_pagination.py`

**Acceptance:** the planner may produce a clean 2-page ST-06 (page 1 = setup +
early steps; page 2 = remaining steps + result device). `30-50%` complete and
intentionally placed. ST-06 ends before the next section.

### US-605 — FAZIT continuation boundaries

**Files:** `research/v7-renderer/patterns/st_fazit.py`,
`templates/st_fazit.html.jinja`, `styles/st_fazit.css`,
`tests/test_stfazit_fill_variant.py` + new boundary test

**Acceptance:** no FAZIT content fragments into the next section. If FAZIT
needs two pages, both carry FAZIT continuation identity. ST-22 starts at its own
boundary. p18/p19 pair shows zero bleed.

### US-606 — Real Director page brief

**Files:** `research/preprocessor/stages/director.py`,
`stages/generate_assets.py`, model module; `tests/test_director.py`

**Acceptance:** brief includes `client_slug, report_id, page_key, section_id,
st_type, selected_reference{...}, rationale, visual_job, must_show,
must_not_imply, page_arc, region_plan, renderer_devices`. Selector gets
st_type+format+density+exclude_report; diversified; requires a real raster.
Brief persisted IN THE PACKAGE (not only Supabase). Provenance written AFTER the
call with the exact sent prompt/ref-hash/model/seed/output-hash.

### US-607 — Renderer consumes physical-page plans

**Files:** `research/v7-renderer/assembler.py`, `patterns/base.py`, affected
ST patterns/templates; renderer continuation tests.

**Acceptance:** renderer receives physical-page plans; `region_plan` governs
named regions where present; `casestudy_hero` is an optional role, not the
mandatory one-sheet contract; a section may produce a4→a4→a3→a4; no template
uses fixed-height overflow as pagination.

### US-608 — Reference-grounded final-artifact QA

**Files:** `research/quality_loop/references/__init__.py`, `brain.py`,
`vis_prompt.py`, `vis_client.py`, `stage_converge.py`,
`research/v7-renderer/render.py`; tests.

**Acceptance:**
- Reference PNGs + Director metadata reach every visual review call.
- Rubric IDs normalized before prompt/client (no `P11*`-style leaks).
- Final composed PDF is re-gated after convergence (overlap + visual +
  clipping + boundary).
- Intrinsic clipping, cross-section contamination, and physical-vs-planned
  page counts are blocking defects.
- No hard-coded apex fixture path in the gate when another package is supplied.

### US-609 — Acceptance run + evidence ledger

**Files:** `scripts/ralph/prd.json`, `scripts/ralph/progress.txt`,
`docs/superpowers/CURRENT-STATE.md`; artifacts in `research/v7-renderer/output/`.

**Acceptance:** rebuild → render → visually inspect p16, p18, p19, p14, p15
(+ spot-check the rest) → verify `30-50%` whole, zero contamination, physical
count == planned count (may exceed 20) → reference-grounded QA on the final
artifact → reopen US-402/403/408/509/510 until these hold.

---

## Ralph execution order (one story per iteration)

1. US-601 (prove the clip + regression)
2. US-602 (identity)
3. US-603 (pagination)
4. US-604 (ST-06 pilot)
5. US-605 (FAZIT boundary)
6. US-606 (Director brief)
7. US-607 (renderer consumption)
8. US-608 (QA repair)
9. US-609 (acceptance)

Each iteration: read `scripts/ralph/CLAUDE.md` + `progress.txt` + this plan →
pick highest-priority `passes:false` story → failing test first → focused
suite → RENDER the affected page(s) → inspect the PNG → verify physical page
count → commit `feat: <ID> - <title>` → append progress.txt → set passes=true.

## Definition of done

- Report may exceed 20 physical pages when content requires it.
- `30-50%` fully visible on p16.
- FAZIT/ST-22 clean boundary (no bleed).
- Director brief in the package; consumed by pagination + placement.
- References reach generation + final QA as real images/metadata.
- Final composed artifact passes the blocking gates.
- No gate weakened or bypassed to get the result.
