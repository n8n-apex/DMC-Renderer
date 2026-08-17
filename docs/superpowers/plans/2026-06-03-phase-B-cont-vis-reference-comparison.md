# Phase B-continuation — Live VIS reference comparison (the visual-appeal engine), proven on ONE page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`. **NO GIT** (checkpoint = full quality_loop suite + renderer suite green). Activate the renderer venv for any WeasyPrint/PyMuPDF call (`source research/v7-renderer/.venv/bin/activate`). The vision client reads `OPENROUTER_API_KEY` + `OPENROUTER_VISION_MODEL` from `research/preprocessor/.env`.

**Goal:** Turn on the *actual cross-referencing* the system has only had plumbing for: compare our rendered page against Richard's validated reference pages (matched by st_type + axes) using a cheap vision model, and let that reference-grounded judgment drive the rubric's VIS rows — so visual appeal is scored against Richard's real decks, not just against absolute DET thresholds. Proven on ONE page (Apex ST-07A), kept local (no Supabase yet, per decision).

**Why this is the right next build (verified state):** `analysis.score()` today only *records* `matched_ref_count` — it does NOT compare against references (the comparison was reserved for the VIS rows, all of which are `skipped:needs_vision`). The reference library holds only 1 of 6 decks (Niklas), local. So the live reference comparison + a multi-deck library is exactly the missing visual-appeal engine.

**Grounded in (already designed — do NOT re-derive):**
- `docs/superpowers/specs/2026-06-03-self-correcting-quality-architecture-design.md` — §4 reference-grounding, §6 the rubric (VIS rows + DET-gates-VIS + anti-reward-hacking §6.3), §7 perception stack (Gemini Flash via OpenRouter, temp 0, pinned snapshot, log raw outputs), §11 determinism/risks.
- `docs/superpowers/specs/2026-05-30-richard-design-dna.md` — §B per-deck axes (encoded in Task A), §C the universal grammar the VIS prompt asks about (founder-as-hero, framed client photo, dark authority panel, social-proof apparatus, dead whitespace, generic-stock), §2 brand-agnostic safeguard (references ground COMPOSITION not brand values).
- The 6 reference PDFs at repo root: `APEX - KI DMC Report v1 (1).pdf`, `Buchagentur DMC-Report (1).pdf`, `DMC-Report Alexander Boss doppelt (1).pdf`, `DMC-Report Mein_Werkzeugkoffer.pdf`, `Niklas Niemeyer DMC-Report Druckfertig (1).pdf`, `aerztepartner_v0.2 (1).pdf`.

**Hard constraints (preserve):** Brand-agnostic — the VIS prompt judges composition/structure/devices ONLY and is explicitly told to IGNORE brand colors, language, and identity; references are "examples of the compositional grammar," never brand templates. NEVER derive schema from one client's PDF — that's why the library must span multiple decks and retrieval picks by st_type+axes. No client name / hex / font literal in logic. Real API calls cost money + flake — unit tests use an INJECTED FAKE client; exactly ONE real call lives in the proof (or a single env-gated integration test). Cache VIS results by (page-image hash + reference-image hashes + rubric version + prompt version) so re-runs are free + reproducible.

---

## File structure (additions to `research/quality_loop/`)
- `references/build_index.py` (MODIFY) — generalize from Niklas-only to all 6 decks: rasterize each repo-root PDF, tag axes from DNA §B per deck, write rows for every page. st_type initially null; populated by the classifier (Task C).
- `references/decks.py` (NEW) — the per-deck registry: `{deck_id, pdf_filename, axes{...}}` for all 6 decks, axes encoded verbatim from DNA §B. Pure data, brand-agnostic axes (categorical labels, not brand values).
- `vis_client.py` (NEW) — the swappable vision client: `VisionClient` (real OpenRouter, temp 0, pinned model from env, retry, on-disk cache) + `FakeVisionClient` (scripted, for tests) sharing a `VisionClient` protocol. `score_page(page_png, reference_pngs, questions) -> dict[row_id -> {score:int 0..3, rationale:str}]`.
- `vis_prompt.py` (NEW) — the brand-agnostic prompt builder: turns the VIS rubric rows + the matched references into the structured instruction. Contains the explicit "ignore brand colors/identity, judge composition only" guardrail + the per-row questions derived from DNA §C.
- `references/classify.py` (NEW) — `classify_st_type(page_png, vis_client) -> st_type` (one-shot page-type classification using the same client); a `build_st_type_index(vis_client)` pass that populates st_type in index.json. Logged + spot-checkable.
- `analysis.py` (MODIFY) — `score(facts, matched_refs, rubric, vis_results=None)`: when `vis_results` provided, VIS rows are adjudicated from it (no longer skipped); DET-gates-VIS on P01/P05/P07/P11; anti-reward-hacking caps (§6.3). When `vis_results=None`, behavior is UNCHANGED (rows skipped) so all existing tests stay green.
- `conductor.py` / `brain.py` (MODIFY, minimal) — thread an optional `vis_client` through `converge_page` → perceive/score so the loop can request VIS results per iteration (cached). Default None = today's behavior.
- `run_one_page.py` (MODIFY) — the proof: run the loop on Apex ST-07A WITH a real `vis_client`, print the reference-grounded VIS scores + rationales + which reference pages anchored the judgment.
- `tests/` — TDD per module, all using the FakeVisionClient (no network).

---

### Task A — Multi-deck reference library (all 6 decks, axes from DNA §B)
**Files:** `references/decks.py` (new), `references/build_index.py` (modify), `tests/test_references.py` (extend).
- [ ] **Failing test:** `test_index_covers_all_six_decks` — after building, `index.json` contains rows for all 6 deck_ids; each row has the correct axes for its deck (assert a couple, e.g. Werkzeugkoffer.headline_type=="all_sans", Niklas.qr_enabled==True); every `png_path` exists on disk.
- [ ] Run → FAIL.
- [ ] Create `references/decks.py` with the 6-deck registry. Encode axes per DNA §B table EXACTLY (categorical labels): headline_type {serif, serif_sans_caps_accent, all_sans}, palette, accent_mechanic {tonal, contrasting}, texture, density, qr_enabled, tone. (APEX: serif/mono/tonal/smooth/airy/qr=false; Niklas: serif_sans_caps_accent/royal_blue_charcoal/contrasting/darkened_photo/punchy_5050/qr=true; Buchagentur: serif/teal_petrol/contrasting/paper_grain/dense/qr=true; Boss: serif/navy_azure/contrasting/flat/navy_panels/qr=false; Werkzeugkoffer: all_sans/midblue_navy/tonal/darkened_photo/navy_panels/qr=true; Ärztepartner: serif/navy_gold/contrasting/parchment_marble/airy/qr=false.)
- [ ] Generalize `build_index.py`: loop over the registry; rasterize each PDF (PyMuPDF 150dpi) to `references/pages/<deck_id>/pN.png`; write index rows `{deck, page_no, st_type:null, axes, png_path}`.
- [ ] Run the build; Run → PASS. Checkpoint: `python -m pytest research/quality_loop/tests/test_references.py -q`.

### Task B — Vision client + brand-agnostic prompt
**Files:** `vis_client.py` (new), `vis_prompt.py` (new), `tests/test_vis_client.py` (new).
- [ ] **Failing tests (FakeVisionClient + prompt, NO network):**
  - `test_prompt_is_brand_agnostic`: the built prompt string contains the explicit guardrail ("ignore brand colours / colors", "judge composition/structure/devices", "do NOT reward or penalise based on brand identity/language") and asks the per-row composition questions (founder-as-hero, framed named client photo, dark authority panel, social-proof apparatus, dead whitespace, generic-vs-specific imagery). It must NOT contain any client name / hex.
  - `test_fake_client_returns_per_row_scores`: `FakeVisionClient(scripted).score_page(png, refs, questions)` returns `{row_id: {"score":int 0..3, "rationale":str}}` for exactly the requested rows.
  - `test_cache_key_is_deterministic`: the cache key for identical (page hash, ref hashes, rubric+prompt version) is identical, and differs when the page image bytes differ. (Use a hash of the file bytes.)
- [ ] Run → FAIL.
- [ ] Implement `vis_prompt.build_prompt(rows, n_refs)` (pure, returns the instruction text + the JSON schema spec). Implement `VisionClient` (reads key+model from `research/preprocessor/.env` via the existing settings pattern; posts page+ref images to OpenRouter chat/completions with `response_format` json + `temperature:0`; on-disk cache under `references/.vis_cache/`; stamina-style retry) and `FakeVisionClient`. Both satisfy a `VisionClientProtocol`.
- [ ] Run → PASS. Checkpoint. (Real network NOT exercised here.)

### Task C — st_type classification (populate the library) + DET-gates-VIS scoring
**Files:** `references/classify.py` (new), `analysis.py` (modify), `tests/test_classify.py` (new), `tests/test_analysis.py` (extend).
- [ ] **Failing tests:**
  - `test_classify_uses_client_and_writes_st_type`: `build_st_type_index(FakeVisionClient(scripted_types))` populates `index.json` rows' `st_type` from the client's classification; `retrieve_references("ST-07A", axes)` then returns case-study rows from MULTIPLE decks (not just one).
  - `test_score_with_vis_awards_gated_positive`: `score(facts, refs, RUBRIC, vis_results={...})` where a VIS row scores 3 AND its DET gate passes → the positive is EARNED; where the VIS score is 3 but the DET gate FAILS (e.g. P05 client-photo VIS high but `required_slots_missing` non-empty) → NOT earned (DET-gates-VIS). 
  - `test_score_without_vis_unchanged`: `score(facts, refs, RUBRIC)` (no vis_results) behaves EXACTLY as before — VIS rows still `skipped:needs_vision` (regression guard so all existing tests pass).
  - `test_vis_caps_anti_reward_hacking`: repeating/maxing a VIS device cannot exceed its row cap; hard-fails still dominate (a VIS-rich page with a hard-fail still cannot clear).
- [ ] Run → FAIL.
- [ ] Implement `classify.py` (one-shot per page; log each classification; cache via the client). Implement the `vis_results` branch in `analysis.score()`: VIS / DET∧VIS rows are adjudicated from `vis_results` (positive earned iff VIS score ≥ threshold AND, for DET∧VIS rows, the DET fact also passes); negative VIS rows (N07 generic-stock, N10 untreated bleed, N08 VIS half) fire from the VIS score; caps per §6.3.
- [ ] Run → PASS. Checkpoint: full quality_loop suite green.

### Task D — Thread the VIS client through the loop
**Files:** `brain.py` (modify), `conductor.py` (modify if needed), `tests/test_brain.py` (extend).
- [ ] **Failing test:** `test_converge_passes_vis_results_to_score` — `converge_page(..., vis_client=FakeVisionClient(scripted))` causes the per-iteration `score()` to receive non-None `vis_results` (assert via a spy/fake `score_fn`), and the resulting PageResult's best score reflects the VIS-awarded rows. With `vis_client=None` (default) behavior is unchanged (regression).
- [ ] Run → FAIL → implement: in the loop, after `perceive`, if `vis_client` is set, retrieve matched refs, call `vis_client.score_page(our_png, [ref pngs], questions)` (cached), pass `vis_results` into `score_fn`. Keep refs retrieval already present.
- [ ] Run → PASS. Checkpoint.

### Task E — PROVE on Apex ST-07A with live VIS (one real API call)
**Files:** `run_one_page.py` (modify), `tests/test_one_page_proof.py` (extend with an env-gated real test).
- [ ] Modify `run_one_page.py`: build a REAL `VisionClient`, run `converge_page` on Apex ST-07A with it, and print — in addition to the existing report — the **reference-grounded VIS section**: for each VIS row, the score + rationale, and WHICH reference pages (deck + page_no) anchored the judgment.
- [ ] **Env-gated integration test** `test_vis_proof_real_call` (skip if `OPENROUTER_API_KEY` absent): runs the real proof once; asserts the VIS rows are no longer all skipped (at least the case-study-relevant rows return a score+rationale), the matched references are real case-study pages from OTHER decks, and the run still ships-best-with-flags (the missing-photo hard-fail still latches — VIS cannot buy back a hard-fail). Print the full reference-grounded report.
- [ ] Run the proof live once; PASTE its output. Checkpoint: `python -m pytest research/quality_loop/tests/ -q` (fakes; fast) + `cd research/v7-renderer && source .venv/bin/activate && python -m pytest tests/ -q` (renderer still green, additive).

---

## Deferred (flagged, not in this plan)
- Supabase persistence of references + runs/page_scores (decision: keep local, prove VIS first).
- Renderer capability builds the loop flags (fill-the-sheet case-study layout etc.) — separate Phase-A work, prioritized by what VIS+DET flag most.
- Whole-deck (20-page) Brain + the document-coherence pass (§5.4).
- N07 "generic stock" routed to a stronger model if Flash proves noisy (§7).

## Self-review
- **Spec coverage:** §4 reference-grounding (Task A multi-deck + Task C retrieval across decks), §6 VIS rows + DET-gates-VIS + §6.3 caps (Task C), §7 vision stack via OpenRouter temp 0 + cache + logged raw (Task B), proof on one page (Task E). 
- **Uses existing analysis:** axes from DNA §B (Task A), VIS questions from DNA §C grammar (Task B prompt). No re-derivation.
- **Brand-agnostic:** prompt guardrail + multi-deck library + composition-only questions; tested (`test_prompt_is_brand_agnostic`). DET-gates-VIS prevents VIS over-credit; hard-fails still dominate.
- **Honest + cheap:** unit tests use FakeVisionClient (no network/cost); one real call in the proof; cache makes re-runs free + reproducible; `vis_results=None` regression guard keeps all 36 existing tests green.
