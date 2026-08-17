# Phase 4: Reference-Derived Layout Templates Implementation Plan

> **For agentic workers:** execute INLINE (subagents unavailable). Targeted tests only. NO git. Verify on pixels against `refs/`. Each st_type migration is double-gated: `tests/test_design_conformance.py` (deterministic) + the vision grader vs the template's `source_refs`.

**Goal:** Replace the hardcoded `st_type -> hand-written CSS template` mapping with templates whose composition is EXTRACTED from Richard's reference pages, so a new brand's content drops into reference-grounded slots. This is the true "copy and repurpose."

**Architecture:** A `LayoutTemplate` (geometry + roles, brand-agnostic) is extracted per reference page by a VLM, clustered by st_type, and the best exemplar per type becomes the v1 archetype. One template-driven renderer places the EXISTING component macro library (portrait, stat_rail, viz, ghost_numeral, pull_quote, etc.) into absolutely-positioned region frames per the template geometry. `plan_layout` selects the template by st_type (+axes). Migration is one st_type at a time, case_study first, each gated.

**Tech stack:** Python (dataclass model in `v7-renderer`, extraction in `quality_loop` reusing the vision client), Jinja (template-driven pattern), the existing component macros.

**Standing conventions:** renderer venv python `research/v7-renderer/.venv/bin/python`; `export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`; quality_loop tests `PYTHONPATH=research/quality_loop`. Brand-agnostic: templates carry geometry + ROLE names + categorical axes ONLY (no client hex / name / font literals).

---

## LayoutTemplate schema (the contract)

```
LayoutTemplate:
  st_type: str                      # e.g. "ST-07A"
  variant: str                      # e.g. "authority-rail"
  grid:   { columns: int, margin: {top,right,bottom,left: float}, gutter: float }   # page fractions
  regions: [ { role: str,           # headline|lede|body|portrait|stat_rail|viz|footer|
                                    #   ghost_numeral|logo_wall|quote|cta|kicker|eyebrow
               x: float, y: float, w: float, h: float,   # 0..1 page fractions
               z: int,              # stacking for overlaps
               fit: str } ]         # "shrink"|"wrap"|"clamp" (optional; default "wrap")
  type_roles:  { headline: <scale-role>, lede: <scale-role>, body: <scale-role>, label: <scale-role> }
  color_roles: { ground: <token-role>, ink: <token-role>, accent: <token-role>, footer: <token-role> }
  whitespace_target: float          # 0..1, intentional empty fraction
  source_refs: [ { deck: str, page_no: int } ]
```

Validation: `st_type` non-empty; every region role in the allowed ROLE vocabulary; `0 <= x,y,w,h <= 1` and `x+w <= 1.001`, `y+h <= 1.001` (inside the page); `color_roles` values from the token-role vocabulary, NEVER a hex/`#`; `type_roles` from the scale-role vocabulary; `whitespace_target` in `[0,1]`; `source_refs` non-empty.

---

## Task 1: the LayoutTemplate model + validation (THIS CHUNK)

**Files:** Create `research/v7-renderer/layout_template.py`; Test `research/v7-renderer/tests/test_layout_template.py`

- [ ] **Step 1: failing tests** — a valid template dict parses via `LayoutTemplate.from_dict`; an out-of-bounds region (`x+w > 1`) raises `ValueError`; an unknown region role raises; a `color_roles` value containing `#` (a hex, brand leak) raises; `validate()` passes on the valid one.
- [ ] **Step 2: run, expect fail** (module missing).
- [ ] **Step 3: implement** — dataclasses `Region`, `Grid`, `LayoutTemplate`; module constants `REGION_ROLES`, `SCALE_ROLES`, `COLOR_ROLES` (frozensets); `LayoutTemplate.from_dict(d)` builds + calls `validate()`; `validate()` enforces the rules above (raises `ValueError` with a precise message). Brand-agnostic: only role names + geometry, no client literals.
- [ ] **Step 4: run the test file** — all pass.

---

## Task 2: VLM extraction stage

**Files:** Create `research/quality_loop/references/extract_templates.py` + a brand-agnostic extraction prompt; Test with a `FakeVisionClient`.
- For each reference page PNG (`references/pages/<deck>/pN.png`) + its text layer, ask the VLM for the regions/grid/roles -> a `LayoutTemplate` dict; validate via `LayoutTemplate.from_dict`. Cluster by st_type (`references/classify.py`); pick the best exemplar per st_type as the v1 archetype (no averaging). Write `layout_templates/<st_type>/<variant>.json`.
- The prompt asks ONLY about composition/geometry/roles (DNA §C: references ground composition, not brand values). No client names/hex/fonts requested or stored.
- Verify: extraction on one ST-07A reference yields a schema-valid template with sensible regions; offline test with a fake client returning a canned region map.

## Task 3: the template-driven renderer

**Files:** Create `research/v7-renderer/patterns/_template_driven.py`.
- `render_from_template(template, page, ctx) -> PageFragment`: emit a page-sized relative box; for each region, an absolutely-positioned frame at `x/y/w/h%`; dispatch the region's role to the existing component macro (headline -> two_tone_headline, portrait -> media_figure, stat_rail -> the rail, viz -> viz dispatch, etc.), themed by the token `:root`. Roles with no content gracefully omit.
- Verify on pixels: render a case_study via the template and Read the PNG.

## Task 4: selection + dispatch

**Files:** Modify `research/preprocessor/stages/plan_layout.py` (select a `LayoutTemplate` by st_type+axes instead of only naming a CSS file) and the renderer pattern registry (route a template-backed st_type to `_template_driven`, behind a per-type switch so un-migrated types keep their current pattern).

## Task 5: migrate case_study (ST-07A) first

- Switch ST-07A to the template-driven path using its extracted template. Gate: `test_design_conformance.py` green AND the vision grader scores the rendered page at/above threshold vs the template's `source_refs`. Verify on pixels vs `refs/`. Only then proceed.

## Task 6: extend the no-literals guard

**Files:** Modify `test_no_literals_in_architecture.py` to also scan `layout_templates/` for client hex/name/font literals (templates must stay brand-agnostic).

## Task 7+: migrate the remaining st_types

One per chunk (cover, content, data, fact_sheet, closing), each double-gated + pixel-verified, until `ST_TO_TEMPLATE` is fully replaced by template selection.

---

## Self-review
- Spec coverage: maps to spec Part 4 (4a extract, 4b store, 4c engine, 4d select, 4e closure). Yes.
- Placeholders: Task 1 is bite-sized; Tasks 2-7 are task-level (expanded just-in-time), which suits the incremental, gate-between-each model.
- Type consistency: `LayoutTemplate`, `Region`, `from_dict`, `validate`, `REGION_ROLES`, `render_from_template`, `source_refs` used consistently.
