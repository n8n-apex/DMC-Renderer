# Reference-Grounded Closed Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (or executing-plans) to implement task-by-task. Steps use checkbox (`- [ ]`) syntax. **Environment note:** subagent spawning is unavailable here (1M-context credit limit), so execute INLINE. Targeted tests only (NO full pytest suite). NO git in this repo. Verify on pixels against `refs/`.

**Goal:** Wire `research/quality_loop` into the build so Richard's reference decks both drive and check it: turn on reference-grounded vision grading, run the loop as an inline post-render stage, grow the auto-fix surface (incl. the overflow fact), and replace the hardcoded layout mapping with reference-derived templates.

**Architecture:** See spec [2026-06-16-reference-grounded-closed-loop-design.md](../specs/2026-06-16-reference-grounded-closed-loop-design.md). Pipeline becomes: preprocessor Stages 1-8 -> v7-renderer render -> **Stage 9 converge (vision loop)** -> Ghostscript flatten.

**Tech stack:** Python (quality_loop runs in `research/v7-renderer/.venv`), OpenRouter vision (`anthropic/claude-sonnet-4.6`), PyMuPDF + Pillow perception, Chromium print-to-PDF + Ghostscript render.

**Standing conventions (every task):**
- Renderer venv python: `/Users/utkarsh/Projects/richard/research/v7-renderer/.venv/bin/python`
- Run quality_loop tests: `PYTHONPATH=/Users/utkarsh/Projects/richard/research/quality_loop <venv-python> -m pytest <path> -q`
- Any render needs: `export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`
- Brand-agnostic: no client hex / name / font literals in logic; client data lives in fixtures.
- Vision key only from `.env`; never print/log it.

---

## Phase 1: turn on reference-grounded vision grading

The vision wiring already exists end to end (`brain` threads `vis_client`; `analysis.score(..., vis_results=)` adjudicates; reference PNGs exist). Phase 1 makes the endpoint provider-agnostic, confirms the strong model, and validates the live grader.

### Task 1.1: provider-agnostic vision endpoint

**Files:**
- Modify: `research/quality_loop/vis_client.py` (the `VisionClient.__init__` and the two `client.post(...)` sites in `classify` and `_call_openrouter`)
- Test: `research/quality_loop/tests/test_vis_client.py`

- [ ] **Step 1: Write failing tests** — three offline tests: default `_api_base` is the OpenRouter URL; an explicit `api_base` arg and a `VISION_API_BASE` env var override it; and the configured base is the URL actually posted to (httpx mocked).
- [ ] **Step 2: Run, expect fail** (`AttributeError: _api_base`).
- [ ] **Step 3: Implement** — add a keyword-only `api_base` param to `__init__`; set `self._api_base = api_base or _read_env_file("VISION_API_BASE") or _OPENROUTER_URL`; replace both hardcoded `_OPENROUTER_URL` post targets with `self._api_base`.
- [ ] **Step 4: Run the whole `test_vis_client.py`** (offline) — all pass, no regression in the existing fenced-reply test.

### Task 1.2: confirm the strong model (no code)

- [ ] `OPENROUTER_VISION_MODEL` is already `anthropic/claude-sonnet-4.6` (strong, vision-capable). No `.env` change. If Phase-1 smoke grades read noisy, bump to an Opus-class vision model (config-only).

### Task 1.3: live grader smoke check

**Files:**
- Create: `research/quality_loop/tools/grader_smoke.py` (a script, NOT a pytest test, because it makes a live paid call)

- [ ] Score a known-good apex reference page against itself/its type on two VIS rows, and score a deliberately blank/broken page on the same rows. Assert the reply is well-formed `{row_id: {score, rationale}}` and that the good page scores strictly higher on a positive row (the discrimination check). Print both results.
- [ ] Run once with the renderer venv (one or two cached OpenRouter calls). If it cannot discriminate, stop and reconsider model/prompt before trusting the grader.

**Phase 1 done when:** the client posts to a configurable endpoint (tested offline) and the live grader cleanly separates a good page from a broken one.

---

## Phase 2: run the loop as inline Stage 9 (post-render)

### Task 2.1: convergence entry + report model
- Files: Create `research/quality_loop/stage_converge.py`; reuse `brain.converge_deck(..., vis_client=VisionClient())`. Define a `ConvergenceReport` (per-page: cleared, reward, fired defects, fixes applied, residual-by-owner) serialized to `convergence_report.json`.
- Verify: a converged run writes the report; converged PDF never worse than initial (monotone-best guard already in `brain`).

### Task 2.2: wire into the end-to-end build with `--fast`
- Files: Modify `research/v7-renderer/render.py` to add a converge step after the initial render and before Ghostscript, skipped by `--fast`.
- Verify: default build runs Stage 9 and emits the report; `--fast` skips it; deck still flattens to `report.pdf`.

(Expanded to bite-sized steps when Phase 1 lands.)

---

## Phase 3: overflow fact + new conductor knobs

### Task 3.1: deterministic overflow/clip fact (kills the ring-class bug)
- Files: Modify `research/quality_loop/perception.py` (add `overflow_detected` + regions, computed from content bbox vs container/page bounds via PyMuPDF/Pillow); wire as `N04`'s `fact_key` in `rubric.py`.
- Verify: a deliberately overflowing viz (the "6 von 6" ring) fires `N04` (hard-fail); a clean page does not.

### Task 3.2: new knobs
- Files: Modify `research/quality_loop/conductor.py` (`DEFECT_KNOBS` + ladders) and the renderer axes it drives: viz-fit (N04), panel-treatment (N02), qr (N06), photo-treatment (N10), header-furniture (N09). Where the renderer lacks the axis, keep flagging honestly.
- Verify: each knob steps its axis and reduces its defect on a real page; where unsupported, the loop flags rather than fakes.

(Expanded to bite-sized steps when Phase 2 lands.)

---

## Phase 4: reference-derived structured layout templates (own detailed plan)

Large; gets its own bite-sized plan when reached. Outline: extract `LayoutTemplate` per reference page (VLM) clustered by st_type; store under `references/templates/`; build one template-driven renderer that places the existing component macros per template geometry; migrate one st_type at a time (case_study first), each double-gated by `test_design_conformance.py` and the vision loop against its `source_refs`; change `plan_layout.py` Stage 7 to select a template instead of naming a CSS file. Extend `test_no_literals_in_architecture.py` to scan `references/templates/`.

---

## Self-review

- Spec coverage: Phases 1-4 map to spec Parts 1-4. Yes.
- Placeholders: Phase 1 is bite-sized with concrete files/edits; Phases 2-4 are deliberately task-level outlines, expanded just-in-time (Part 4 noted for its own plan). Acceptable given size + the inline, gate-between-phases execution model.
- Type consistency: `api_base`/`_api_base`, `VISION_API_BASE`, `ConvergenceReport`, `overflow_detected` used consistently.
