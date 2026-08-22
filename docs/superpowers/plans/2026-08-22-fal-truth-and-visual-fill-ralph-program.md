# FAL Truth + Visual Fill — Ralph Program (2026-08-22)

> **For agentic workers:** execute ONE story per Ralph iteration. NEVER mark a
> story complete from markup/tests alone. The acceptance artifact is the
> rendered PNG of the affected page plus the physical==logical page-count check.
> Evidence file: `/tmp/vision_audit_20.json` (regenerate with
> `research/v7-renderer/audit_deck.py`). Vision ground truth = LM Studio
> `qwen3.5-9b-vlm` on the actual rendered pages — proxy metrics
> (ink coverage, DOM geometry, gate scores) are NOT evidence.

**Goal:** close the two systemic defects that make the deck feel "stale / empty
/ low-quality paper" (the user's words) WITH the fal-asset truth as the
baseline — and make the code honest: either a fal asset is wired and paints,
or it is deleted from the fixture, never kept as a dead file with a claim.

**Architecture:** the deck is one flowing document rendered by treatment
templates (`templates/treatments/*.jinja`), chosen by `treatment_stylist.py`
per ST type, driven by `treatment_engine.py` data prep. FAL assets enter via
`fixtures/apex/build_package.py` (image_map → asset_plan → `_SUPPRESS_SLOTS` →
`resolved_package.json` report_assets/attempts). The two layers that have been
disagreeing are **build** (what the package says should exist) and **render**
(what the treatment actually paints). Every story below resolves one concrete
"claimed but not painted" instance and is verified on PNG.

**Tech stack:** Python 3.11, Jinja, CSS paged media, Chromium/Playwright,
PyMuPDF, LM Studio VLM (`audit_deck.py`), `scripts/ralph/{prd.json,prompt.md}`.

---

## Non-negotiable rules

- **No fabrication, ever.** Every figure a device shows must appear verbatim in
  that page's own copy (`viz_curation.py::_figure_grounded`). Never weaken it.
- **No client literals, no raw hex, no em dashes (U+2014)** in templates/,
  styles/, patterns/, components/, dmc-renderer/*.py. Brand tokens are all that
  may appear in logic; names/numbers live in fixtures.
- **Never weaken a guard/gate to pass a test.** Fix the drifted side.
- **Verify the whole page on pixels** (Read `output/report-pN.png`), never
  "did my change show up." Physical page count must stay == logical (currently
  the deck renders 25 physical pages — do not re-take this baseline until the
  fill program stabilizes it).
- **box-shadow banned on viz** (`test_viz_flat_on_cream`). Use hairline border
  + surface fill.
- **Real type tiers only:** `--type-stat-xl` 60pt, `--type-stat` 40pt,
  `--type-display` 32pt, `--type-signature` 28pt, `--type-h2` 20pt,
  `--type-pullquote` 18pt, `--type-h3` 14pt. NO `--type-h1`.
- **A fal asset either paints or is deleted.** No dead files with claims in
  comments. Every story that touches a suppressed/orphaned fal asset
  re-verifies image_map ↔ package ↔ render agreement.

---

## Baseline truth (2026-08-22, verified)

### FAL assets: generated → status on today's `output/report.pdf`

| File | Campaign | Status on the PDF | Root cause |
|---|---|---|---|
| `report_navy_stone.png` | 3 (img2img) | **PAINTS — 7×, `--panel-marble`** | wired as `panel_texture` report-asset |
| `report_background_texture.png` | 1+2 (t2i) | paints, but it's the **procedural marble** (ground_marble.py) — the fal version is the `.fal.png` backup | PBR-J "code beats fal" decision overwrote the slot |
| `4_status_quo_scene.png` | 1+2 | **0 refs in render** | build re-adds it (build_package.py:254-262) but `a4_editorial_fill.html.jinja:118-120` refuses unlabeled fal plates → build/render disagree |
| `1_cover_hero.png` | 2 | 0 refs | slop campaign rip-out; build_package.py:460-462 asserts absence; real founder photo wins |
| `report_atmospheric_gradient.png` | 1+2 | 0 refs | `_SUPPRESS_SLOTS` (build_package.py:260-263) |
| `5_status_quo_scene.png` | 1 | 0 refs | `_SUPPRESS_SLOTS` |
| `18_fazit_background.png` | 2 | 0 refs | never in `image_map.json` / report_assets — orphan |
| `report_navy_footer.png` | 3 | 0 refs (only stale `out/report.html`) | never mapped |
| `report_fazit_field.png` | 3 | 0 refs | never mapped |
| `report_cream_paper.png` | 3 | never generated | — |
| `N_csN_scene.png` / `N_case_scene.png` | case scenes | 0 refs | written as `case_scene` slots (build_package.py:356-376) but `a4_case_study.html.jinja:55-59` refuses; `test_viz_host_st07a.py` asserts no `csh-scene` |

### Systemic visual defects (2026-08-19 vision audit — still present)

- **S1 — bottom-quarter dead space on ~20/25 pages.** Content fills only
  70-75% of the sheet. Root cause: the treatment layouts are NOT flex-filling
  to the sheet foot. This is the "stale / low-quality paper" the client flags.
- **S2 — ghost numeral / oversized stat overlaps body copy** on case-study
  spreads (p10/p12/p13/p15-p18/p25 per the 08-19 audit; re-run the audit to
  refresh).
- **S3 (2026-08-16 grammar audit):** rounded SaaS-y cards/pills/shadows,
  abstract fal art, 100+ char measures, prose-in-metric-slots, header CTA
  repetition — the whole catalog in `2026-08-16-richard-grammar-replication.md`
  §2-4.

---

## Ralph stories (prioritized; one per iteration)

### US-701 — FAL TRUTH: make the build/manifest/render agreement a hard gate

**Files:** `fixtures/apex/build_package.py`,
`fixtures/apex/image_map.json`, `tests/test_wiring_conformance.py`

**Acceptance:**
- Every file referenced by `image_map.json` and `resolved_package.json`
  (`report_assets` + page `assets`) is verifiable, and every such asset is
  either (a) referenced ≥1× in the rendered `output/report.html` of the final
  composed deck, or (b) on an explicit, commented, reason-carrying deny-list.
- Assert the exact current survivors: `background_texture` (marble),
  `panel_texture` (navy_stone), real IG/cs photos. `4_status_quo_scene`,
  `18_fazit_background`, `report_navy_footer`, `report_fazit_field`,
  `N_csN_scene` are EITHER rendered or removed from the fixture — never both
  present-and-unrendered.
- Existing dead files are deleted from `fixtures/apex/assets/`, and the stale
  `fixtures/apex/out/report.html` artifact is removed (it misleads every grep).

**Evidence:** after the change, `grep -c '<asset>' output/report.html` for
each survivor ≥1; dead files gone; full render page count unchanged.

### US-702 — S1 FILL: every treatment flex-fills to the sheet foot

**Files:** `styles/treatments/a4_case_study.css`,
`styles/treatments/a4_editorial_fill.css`, `styles/treatments/a4_two_stack.css`,
`styles/treatments/a4_vertical_timeline.css`, `styles/treatments/a4_stacked_hero.css`

**Acceptance:**
- Render p1/p3/p5/p7/p9/p11/p13/p15/p17/p19/p21/p23 (every other page);
  the VLM reports no "bottom X% dead" at MAJOR or CRITICAL on any of them.
- The `.cs4-main`, `.ef-mid`, `.sq-*`, timeline, and stacked-hero column
  containers use the SAME column/row flex that already works on
  `a4_case_study` (cream reaches the sheet foot — see commits 2b66d5a ,
  d1dfb94) — applied per treatment, NOT by one-off dump hacks that move
  content to the bottom and leave a mid-band void.

**Evidence:** `audit_deck.py` on the re-rendered deck; no S1 at CRITICAL on
the audited pages; physical==logical page count.

### US-703 — S2 FIX: ghost numeral behind content + reserves its space

**Files:** `styles/treatments/a4_case_study.css`,
`templates/treatments/a4_case_study.html.jinja`

**Acceptance:**
- The `cs4-numeral` (ghost section numeral) sits at `z-index` behind the rail
  body AND the rail reserves its space (no paint-under). Fix p10/p12/p13/
  p15-p18/p25 overlaps verified on PNG.
- No rule weakens `test_viz_flat_on_cream` (hairline + surface, no shadows).

### US-704 — TREATMENT HOST SLOTS: prove produced devices actually render

**Files:** `templates/treatments/a4_editorial_fill.html.jinja`,
`templates/treatments/a4_case_study.html.jinja`, `treatment_engine.py`

**Acceptance:**
- For every treatment: `td.viz`, `td.components` (generated chart/diagram
  SVGs), and real captioned photos each render a named host slot that is
  non-empty when the data exists. Add a per-treatment "host-slot render count"
  assertion in the renderer suite (count `.ef-vizband`, `.cs4-devices`,
  `.ef-compband`, `.csh-scene`-only-when-real-photo).
- Disconnect noted in US-701: unlabeled fal plates stay banned, but a real
  captioned scene (`image_type == "photo"` + caption) MUST have a host band on
  the treatment, so the 2026-08-19 "kept and routed" status-quo scene becomes
  either a real photo with a band or is removed.

### US-705 — GRAMMAR F3/F4: flat + sharp purge of the audit catalog

**Files:** `styles/components.css`, `styles/treatments/*.css`

**Acceptance:**
- Remove the rounded-corner/pill/drop-shadow category on cards, panels,
  pills, checkmarks; replace with flat rules, sharp corners, ghost section
  numerals. Kill abstract fal waves/ghost-'A' art per
  `2026-08-16-richard-grammar-replication.md` §5 (US-505).
- 20/20 pages audited; ≥5 pages verdict=yes and NO rejects on the core pages
  (per the grammar program's US-509).

### US-706 — MEASURE + LEADING (F1) + typographic polish (F5)

**Files:** `styles/components.css`, `styles/treatments/*.css`

**Acceptance:**
- Body max-width capped to ~70 chars equivalent, line-height 1.5-1.6,
  paragraph spacing; German sentence case in metrics; `transform_arrow` uses a
  real arrow glyph; `30-50%` clip re-fixed and guarded (scrollWidth <=
  clientWidth).

### US-707 — FINAL QA + deliverable

**Files:** none (verification)

**Acceptance:**
- Full `audit_deck.py` run; compile the honest per-page ledger into
  `/tmp/vision_audit_20.json`.
- Physical == logical page count.
- Deck re-rendered to `output/report.pdf` and handed to the user.

---

## Verification protocol (every story)

1. Build the fixture: `cd research/preprocessor && source .venv/bin/activate
   && python ../v7-renderer/fixtures/apex/build_package.py`
2. Render: `cd research/v7-renderer && source .venv/bin/activate &&
   DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib python render.py`
3. Read the affected `output/report-pN.png` via the Read tool.
4. Odd pages re-audit: `cd research/v7-renderer && .venv/bin/python
   audit_deck.py` (uses local VLM, free).
5. Page count: `python -c "import fitz; print(len(fitz.open('output/report_print.pdf')))"`

## File map (context for future iterations)

- Build / asset truth: `research/v7-renderer/fixtures/apex/build_package.py`,
  `research/v7-renderer/fixtures/apex/image_map.json`,
  `research/v7-renderer/fixtures/apex/resolved_package.json`,
  `research/v7-renderer/fixtures/apex/ground_marble.py`
- Render layer: `research/v7-renderer/assembler.py`,
  `treatment_stylist.py`, `treatment_engine.py`, `templates/treatments/*.jinja`,
  `styles/treatments/*.css`
- FAL tooling: `research/preprocessor/stages/generate_assets.py`
  (`fal_generate_image`, `fal_generate_image_edit`),
  `research/preprocessor/tools/gen_decorative_assets.py`
- QA: `research/v7-renderer/audit_deck.py`
- Prior audits: `docs/superpowers/plans/2026-08-19-visual-defect-audit.md`,
  `2026-08-16-richard-grammar-replication.md`,
  `2026-08-16-ralph-director-pagination-repair.md`