# Phase B — The Self-Correcting Quality Loop, proven on ONE page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]` checkboxes. **NO GIT** (checkpoint = full suite + guards green). Activate the renderer venv for any WeasyPrint call (`source research/v7-renderer/.venv/bin/activate`).

**Goal:** Build the agreed architecture — **Brain → Conductor → Interceptor (Perception + Analysis)** + the **per-page convergence loop** — and prove it by converging **one** page (the Apex case study, ST-07A, where the worst problems are): render → perceive → score against the reference library → localize one defect → route a fix → re-render → re-score, until the page clears the bar or hits the cap and ships-best-with-flags.

**Why this, not more manual CSS:** the references/perception/scoring/fixing is the *system's* job. Manual hand-tweaking is the bottleneck. The loop drives quality to the renderer's ceiling and **flags capability gaps** (device mockups, missing client photos, texture-behind-content) as explicit outputs instead of me guessing.

**Grounded in (already analyzed — do NOT re-derive):**
- `docs/superpowers/specs/2026-06-03-self-correcting-quality-architecture-design.md` — §3 topology, §4 reference-grounding, §5 per-page loop + 3 guards, §6 the two rubric tables + reward scheme, §7 perception stack, §11 determinism/risks. **The build blueprint.**
- `docs/superpowers/specs/2026-05-30-richard-design-dna.md` — **§C → positive rubric rows; §E → negative rubric rows; §B axes; §D recipes.** The rubric is DATA derived from here. References score *composition/devices*, never brand values (§2 brand-agnostic safeguard).
- The 6 reference PDFs at repo root + the agent page-identifications (which pages are Fallstudien per deck) — the reference library content.

**Architecture / tech:** a NEW top-level layer `research/quality_loop/` (pure Python; wraps the existing pre-processor + renderer, edits neither's contracts). Deterministic core in Python; the few VIS rows behind a swappable cheap-vision client (stubbed for this one-page proof, wired but skippable). Local reference index + local score JSON for the proof (Supabase persistence deferred per spec §9 — wired later). pytest TDD throughout.

**Scope discipline (what this plan does NOT do — deferred, noted as flags):** the VIS vision-model rows (Gemini) are wired but stubbed; Supabase persistence; the whole-deck Brain over 20 pages; the document-coherence pass (§5.4). This plan delivers the *mechanism*, proven on one page, with the deterministic rubric live.

---

## File structure (new `research/quality_loop/`)
- `references/build_index.py` + `references/index.json` + `references/pages/*.png` — the reference library (rasterized reference decks, tagged {deck, page_no, st_type, axes}) + axis-distance retrieval.
- `perception.py` — `perceive(rendered_pdf, page_png, page_data, axes) -> PageFacts` (the DET core; VIS rows flagged "needs_vision").
- `rubric.py` — the two tables (positive from DNA §C, negative from DNA §E) as versioned config: each row = {id, detect: DET|VIS, weight|HARD_FAIL, capability_flag, applies_to_st_types}.
- `analysis.py` — `score(facts, matched_refs, rubric) -> PageScore` (per-row results, reward 0–1M per §6.3, hard-fail latches, ranked localized defects each tagged with a `knob_class`).
- `conductor.py` — bridges: `render_page() → perceive → analyze`; turns the top defect into a `Fix{knob_class, target, proposal}` and routes it (renderer-knob applied; preprocessor/asset-gen = flag).
- `brain.py` — the per-page convergence loop + the 3 guards (§5.2): iteration cap (~3), monotone-best retention, oscillation detector → clear OR ship-best + flag.
- `run_one_page.py` — the proof: run the loop on the Apex ST-07A case study; print the score trajectory + the fixes applied + the capability-gap flags.
- `tests/` — TDD for every module.

---

### Task 1 — Scaffold + reference library
**Files:** create `research/quality_loop/` package; `references/build_index.py`, `references/index.json`, `references/pages/`; `tests/test_references.py`.
- [ ] **Failing test:** `retrieve_references(st_type="ST-07A", axes={...}, k=3)` returns ≤3 reference rows of the SAME st_type, ordered by axis-distance (closest first), each with a `png_path` that exists.
- [ ] Run → FAIL.
- [ ] Implement `build_index.py`: rasterize each repo-root reference PDF to per-page PNGs (PyMuPDF, 150dpi) into `references/pages/<deck>/pN.png`; write `index.json` rows `{deck, page_no, st_type, axes{...}, png_path}`. Tag st_type + axes from the KNOWN page map (encode the agent-identified Fallstudie/about/cta pages per deck — Boss 8/10/12, Niklas 8/10/12, Buchagentur 8/10/12, etc. — and the per-deck axes from DNA §B). This is *using* the existing analysis, not re-deriving it.
- [ ] Implement `retrieve_references()`: filter by st_type, sort by a simple axis-distance (categorical mismatch count over the §B axes), return top-k.
- [ ] Run → PASS. Checkpoint: `python -m pytest research/quality_loop/tests/ -q`.

### Task 2 — Perception DET core
**Files:** `perception.py`, `tests/test_perception.py`. Reuse: `test_font_embedding.py` font-table logic; `validators/overflow.py`.
- [ ] **Failing tests** (one per fact): given a rendered page (PDF+PNG) + its package `data`/`slots`, `perceive(...)` returns a `PageFacts` with: `display_font_embedded` (PyMuPDF font table — NOT PT-Serif/Hiragino), `overflowed` (reuse check_overflow), `min_text_contrast` (computed WCAG over text vs ground), `required_slots_missing` (from `slots[].status`), `dead_space_fraction` (pixel-variance: fraction of the lower page region that is uniform/empty), `placeholder_text_present` (PDF text scan for lorem/"could not"/"First Name Last Name"), `header_furniture_present`, `qr_present` vs `axes.qr_enabled`.
- [ ] Run → FAIL → implement each as a small pure function reading the rendered artifacts + package. (`dead_space_fraction`: rasterize the page, compute per-row pixel variance, report the contiguous low-variance bottom fraction — this is the metric that catches the case-study dead space you flagged.)
- [ ] Run → PASS. Checkpoint.

### Task 3 — Rubric config + Analysis scorer
**Files:** `rubric.py`, `analysis.py`, `tests/test_analysis.py`.
- [ ] Encode `rubric.py` from spec §6.1/§6.2 (which are from DNA §C/§E): each row `{id, polarity, detect, weight or HARD_FAIL, capability_flag, applies_to}`. Mark VIS rows `detect="VIS"`.
- [ ] **Failing tests:** `score(facts, refs, rubric)` for a synthetic case-study facts dict → returns a `PageScore` where: a missing required photo latches a hard-fail (cannot be out-earned); `dead_space_fraction > threshold` fires N08; a QR present with `qr_enabled=false` fires N06; reward is clamped `[0, max]` and normalized to the §6.3 scale; VIS rows are reported as `skipped:needs_vision` (not silently passed); defects are returned ranked, each with a `knob_class` ∈ {renderer, preprocessor, asset_gen}.
- [ ] Run → FAIL → implement DET scoring + hard-fail latches + anti-reward-hacking caps (§6.3). VIS rows return `skipped` with a flag.
- [ ] Run → PASS. Checkpoint.

### Task 4 — Conductor (bridge + fix routing)
**Files:** `conductor.py`, `tests/test_conductor.py`.
- [ ] **Failing test:** given a `PageScore` with a ranked defect, `conductor.propose_fix(score)` returns one `Fix{knob_class, target, proposal}` for the top *fixable* defect; `route(fix)` dispatches a `renderer`-class fix to the renderer-knob applier and returns a `FLAGGED` result (no code change) for `asset_gen`/`preprocessor` classes.
- [ ] Implement a small **renderer-knob applier**: a constrained, brand-agnostic set the loop may toggle on a page to fix DET defects without manual CSS — start with: `density` (compact↔balanced), `case_study_layout_variant` (e.g. `sidebar` ↔ `inline-dense` to kill dead space), `panel_tone`. (These knobs are renderer capabilities; the loop selects among them — that is the system doing what I was doing by hand.) Applying a knob = setting a value the renderer reads at render time (via the package axes / a per-page hint), then re-rendering.
- [ ] Run → PASS. Checkpoint.

### Task 5 — Brain (per-page convergence loop + the 3 guards)
**Files:** `brain.py`, `tests/test_brain.py`.
- [ ] **Failing tests** (§5.2 guards): the loop (a) stops at the iteration cap (~3) and ships the **best-scored** version + a flag; (b) never accepts a remake that scored worse (monotone); (c) detects an oscillating defect set and switches strategy instead of re-applying the failed fix.
- [ ] Implement `converge_page(page_id) -> PageResult`: loop {render → perceive → score → if cleared(reward≥threshold ∧ no hard-fail) stop; else conductor.propose_fix → route → record best} under the guards; on cap → ship best + collect flags (capability gaps + un-fixable hard-fails).
- [ ] Run → PASS. Checkpoint.

### Task 6 — PROVE on the Apex ST-07A case study
**Files:** `run_one_page.py`; `tests/test_one_page_proof.py`.
- [ ] Wire `run_one_page.py` to converge the Apex case-study page through the loop and print: the per-iteration reward trajectory, each fix applied (+ knob), the final score, and the **flags** (e.g. "N01 client photo missing — case-study-1; N11 device_mockup absent — asset_gen; both routed to asset-gen/human, not fixable in-renderer").
- [ ] **Acceptance test:** the loop runs end-to-end on the real page; it detects the dead-space defect and improves the reward by switching the layout knob (monotone); it correctly **flags** the missing client photo + missing mockup as `asset_gen` (not silently passing them); final page either clears or ships-best-with-flags; full renderer suite still green (the loop is additive, edits no existing contract).
- [ ] Checkpoint: `python -m pytest research/quality_loop/tests/ -q` + `cd research/v7-renderer && source .venv/bin/activate && python -m pytest tests/ -q` (still green).

---

## Deferred (Phase-B continuation — flagged, not in this plan)
- VIS vision-model rows (cheap Gemini via OpenRouter, temp 0) — wired as `detect="VIS"` but stubbed here; turn on next.
- Supabase persistence of `runs`/`page_scores` + the reference library in Supabase (§9) — local JSON for the proof.
- The whole-deck Brain (all 20 pages) + the document-coherence pass (§5.4).
- Renderer-capability gaps the loop surfaces (device mockups, texture-behind-content, more layout variants) → fed back as Phase-A/Phase-C work, prioritized by what the loop flags most.

## Self-review
- **Spec coverage:** Brain (T5), Conductor (T4), Interceptor = Perception (T2) + Analysis (T3), reference-grounding (T1), per-page loop + 3 guards (T5), reward/hard-fail (T3) — all present, all cite the spec §.
- **Uses existing analysis:** rubric = DNA §C/§E (T3); reference tagging = the agent page-IDs + DNA §B axes (T1). No re-derivation.
- **Brand-agnostic:** rubric rows score devices/relationships, never client values; references scored on composition; the renderer-knobs are semantic. Guards extended to the new package.
- **Honest:** VIS rows are *flagged skipped*, not faked; capability gaps are *flagged*, not silently passed; the loop ships-best-with-flags on cap (never stalls).
