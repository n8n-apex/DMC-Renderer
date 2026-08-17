# Fix stat clipping + close the perception gap + run the loop on all 20 pages — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`. **NO GIT** (checkpoint = full suites green). Activate the renderer venv for any WeasyPrint/PyMuPDF call.

**Goal:** Kill the case-study stat-clipping defect at its root, give the quality loop an *eye* for it (so it can't recur silently), and run the loop across the whole deck so every page is adjudicated by the system (not hand-sprayed knobs).

**Root cause (verified, systematic-debugging Phase 1-3):** the case-study fill panel renders each `ergebnis_metrics[].value` as an oversized numeral (`--type-display-xl`, 40pt). On p7 the values are crisp numerals ("> 200.000 €", "4") and fit. On p12 the values are *prose sentences* ("von bis zu 24 Stunden auf Minuten", "tausende WhatsApp-Chats automatisiert") — at 40pt these overflow the ~64mm panel and **clip** at the right edge. Two faults meet: (a) the renderer never fits/wraps long values → it clips; (b) the upstream content put prose where the design grammar expects a numeral. The loop did NOT catch it because perception has no intra-box overflow/clipping detector, and these pages were never run through the loop (a manual knob-spray preview).

**Grounded in:** `2026-05-30-richard-design-dna.md` §C3 (stat callouts = oversized NUMERALS, e.g. 15/750/129.000) ; `2026-06-03-self-correcting-quality-architecture-design.md` §6 (rubric), §5 (per-page loop) ; the existing `research/quality_loop/` (perception/rubric/analysis/conductor/brain) + `research/v7-renderer/` (st_07a fill variant).

**Scope discipline:** the DEEP content fix (preprocessor emitting crisp numerals instead of prose for stat callouts) lives in content generation (upstream of `structure_content.py`, which only READS metrics) — it is a content-quality effort, NOT a deterministic parser change, so this plan FLAGS it (the loop routes it to `preprocessor`) rather than hacking the fixture. This plan delivers: renderer clip-proofing, the perception detector + rubric flag, and the whole-deck loop run.

---

### Task 1 — Renderer: make case-study stat values clip-proof
**Files:** `research/v7-renderer/styles/st_07a.css` (+ maybe `templates/st_07a.html.jinja`, `patterns/st_07a.py`), `research/v7-renderer/tests/test_st07a_fill_variant.py`.
- [ ] **Failing test:** render the REAL apex case study with PROSE stat values (use `fixtures/apex` pages[11] = the p12 case study, set `layout_variant="fill"`), rasterize the page, and assert NO clipping: the dark panel's content stays within the panel's right boundary. Practical metric: crop the rightmost ~2mm column of the panel region in the PNG and assert it is uniform panel-dark (no glyph ink cut at the edge) — i.e. no ink touches the panel's right edge. ALSO assert the page is still exactly 1 physical page. Confirm this FAILS today (clipping present).
- [ ] Implement: the stat value must FIT — never clip. Approach: (a) ensure the panel/cell does NOT visually clip (no `overflow:hidden` cutting text; allow wrapping with `overflow-wrap:anywhere`/`word-break`), AND (b) for long values, step the font down. Add a "long value" treatment: when a value string is long (e.g. > ~12 chars or contains a space → it is a phrase, not a numeral), render it at a smaller size (e.g. `--type-display` or `--type-h2`) so it wraps cleanly inside the panel instead of overflowing at 40pt. The crisp-numeral case (p7) must be UNCHANGED (still big at `--type-display-xl`). Decide the size class in `patterns/st_07a.py` (compute an `is_numeral`/`length` hint per stat) or via a CSS class toggled on long values; document the threshold.
- [ ] Run → both p12 (no clip, wrapped/smaller) and p7 (unchanged big numerals) pass. Checkpoint: renderer suite green.

### Task 2 — Perception + rubric: detect prose-as-stat (close the eye gap)
**Files:** `research/quality_loop/perception.py`, `research/quality_loop/rubric.py`, `research/quality_loop/analysis.py`, `tests/test_perception.py`, `tests/test_analysis.py`.
- [ ] **Failing tests:** `perceive(...)` returns a new fact `non_numeral_stat_values: list[str]` = the page's `ergebnis_metrics` (read from `page_data["data"]["ergebnis_metrics"]`) whose `value` is NOT a crisp numeral callout (heuristic: a value is "numeral-like" if, after stripping currency/%/→/punctuation/whitespace, it is dominated by digits and short — e.g. matches a small regex like `^[<>~]?\s*[\d.,]+\s*(€|%|x|h|Std\.?|Min\.?|→.*)?$` OR is ≤ ~10 chars with a digit; otherwise it is prose). On apex pages[6] (p7) → `[]` (all numeral-like); on pages[11] (p12) → the 3 prose values. Then `score(...)` fires a new NEGATIVE rubric row (e.g. **N15 "stat callout is prose, not a numeral"**, knob_class `preprocessor`, weight −5) when `non_numeral_stat_values` is non-empty, and the defect routes to `preprocessor` (content gap — NOT renderer-fixable).
- [ ] Implement the DET fact (pure helper + regex), add the rubric row (DET, fact_key="non_numeral_stat_values", knob_class="preprocessor", applies_to ST-07A), wire the negative branch in `analysis.score` (mirror N08/N14 firing). Keep `vis_results=None` and no-stat pages behaving unchanged.
- [ ] Run → PASS. Checkpoint: quality_loop fast suite green.

### Task 3 — Whole-deck loop: converge all pages + a deck report
**Files:** `research/quality_loop/brain.py` (add `converge_deck`), `research/quality_loop/run_deck.py` (new), `tests/test_brain.py`, `tests/test_deck_proof.py` (new).
- [ ] **Failing test (fakes, fast):** `converge_deck(package_dir, out_root, *, max_iterations=4, vis_client=None, ...)` runs `converge_page` for each content page (skip pure-cover/back if desired, or all 20) and returns a `DeckResult` with `.pages: list[PageResult]` (one per page) and `.deck_flags` (aggregated, de-duplicated flags across pages, each tagged with its page index). Use injected fakes so the test is deterministic (monkeypatch `converge_page` to return scripted PageResults) — assert it iterates all pages and aggregates flags.
- [ ] Implement `converge_deck` (loop over `pkg["pages"]`, call `converge_page(package_dir, i, ...)`, collect). Implement `run_deck.py`: a CLI that runs the real deck convergence and prints a per-page table (page | st_type | cleared | best_reward | dead_space | fixes | top flags) + a deck-level flag summary grouped by knob_class (renderer / preprocessor / asset_gen). Support `--vis`.
- [ ] **Real integration test** (env-gated for --vis; a no-vis variant always runs but is slow → mark slow): `converge_deck` on the real apex package, no vis, asserts it produces a PageResult per page and the deck_flags include the prose-stat flag (N15, preprocessor) for the p12 case study and the missing-photo flag (N01, asset_gen) for the case studies. Print the deck report.
- [ ] Run the real `python run_deck.py` (no --vis first; then --vis once) and capture the per-page report. Checkpoint: quality_loop suite green; renderer suite still green.

### Task 4 — (FLAGGED, not built here) Preprocessor stat-numeral content quality
The loop now flags prose-stats → `preprocessor`. The actual fix (content generation emits crisp numerals for stat callouts, prose to the body) lives upstream of `structure_content.py` (likely the LLM content/brief stage). Captured as a flagged follow-up: it needs the content-generation stage + its own spec/tests, and cannot be done as a fixture edit. Note it in `context.md` as the top preprocessor/content task surfaced by the loop.

---

## Self-review
- **Root cause addressed:** renderer can no longer clip (T1); the system can now SEE prose-stats (T2) and routes them to the right owner (preprocessor); the whole deck is adjudicated by the loop (T3), replacing manual knob-spray.
- **Honest:** the deep content fix is flagged, not faked (T4). The loop's new eye (T2) is deterministic + cheap (regex on data), not a brittle pixel hack.
- **Brand-agnostic:** the numeral heuristic is about FORMAT (digits vs prose), not brand values; no client literals. Renderer fix is tokens-only.
- **Regression-safe:** p7 (crisp numerals) unchanged; `vis_results=None` path unchanged; renderer suite + quality_loop suite kept green at each checkpoint.
