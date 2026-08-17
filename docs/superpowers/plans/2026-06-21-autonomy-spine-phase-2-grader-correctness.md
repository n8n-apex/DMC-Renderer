# Autonomy Spine, Phase 2: Grader Correctness, Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make the quality loop's per-page gate REACHABLE and MEANINGFUL: a page can actually "clear" when it meets the criteria the system can currently verify, without making "cleared" trivially true (anti-reward-hacking preserved).

**Architecture:** The reward is normalized against the EARNABLE positive maximum (the positives that are actually scorable for this page given its facts, any vision results, its DET gates, and its st_type) rather than the global theoretical sum of all 16 positive weights (=92). This is the parent design's §5.5 "rubric clamped to capability": rows the system cannot currently satisfy/measure are excluded from the denominator and surfaced as backlog, not silently dragging reward to an unreachable floor. Hard-fail dominance and all penalties are unchanged (they live in `raw_points`, not the denominator).

**Tech Stack:** Python 3.11, pytest, run in the **v7-renderer venv** (it has `fitz`/PyMuPDF that the quality_loop perception needs): `cd research/quality_loop && /Users/utkarsh/Projects/richard/research/v7-renderer/.venv/bin/python -m pytest <test> -q`. The preprocessor venv lacks `fitz`. Back up every file before editing (not a git repo).

**Source spec:** `docs/superpowers/specs/2026-06-20-autonomy-spine-design.md` §3.5 + addition C; infection #17. Parent: `2026-06-03-self-correcting-quality-architecture-design.md` §5.5 (capability clamp), §6.3 (per-page gate).

**Baseline (v7 venv):** `test_analysis.py` + `test_references.py` = 25 passed (green, runnable). 13 other quality_loop tests fail pre-existing with `OSError` (real-render/asset tests needing rendered PDFs/fonts absent in this checkout) — NOT in scope, do not touch.

---

## Scope

**In scope (Phase 2, this plan):** the earnable/per-st_type positive-max normalization so the per-page gate is reachable. Fully TDD-able against `test_analysis.py`.

**Deferred to Phase 2b (next plan):** A3/treatment grading — un-gate Stage 9 from `--treatments` (`render.py:131-132`) and make reference retrieval format-aware so A3/treatment pages compare against A3 references. Deferred because it depends on the render path + the reference library (whose `index.json` axes are drifted, infection #8), which are not cleanly unit-testable in this venv; it belongs with the orchestrator/render wiring. Recorded here so it is not forgotten.

**Deferred to Phase 4 (orchestrator):** engine pinned to chromium in the orchestrator call (addition A) and fail-loud on the `axes`/`brand_axes` contract fork (addition B) — both are properties of how `render_package`/`load_package` are invoked, which the orchestrator owns.

---

## File structure

| File | Responsibility | Change |
|---|---|---|
| `research/quality_loop/analysis.py` | the scorer | add `_earnable_positive_max(...)`; use it as `pmax` in `score()` |
| `research/quality_loop/tests/test_analysis.py` | scorer tests | update the one reward-normalization test; add reachability + still-gated tests |

`rubric.py`'s global `positive_max()` is KEPT (back-compat for other callers/imports); the earnable helper lives in `analysis.py` because it needs `_det_gate` (already there).

---

## Task 1: earnable positive-max normalization (cleared becomes reachable)

**Files:**
- Modify: `research/quality_loop/analysis.py` (add helper near `_det_gate` ~line 183; use it at `score()` ~line 330)
- Test: `research/quality_loop/tests/test_analysis.py`

- [ ] **Step 1: back up**

Run: `mkdir -p /tmp/p2_backup && cp research/quality_loop/analysis.py /tmp/p2_backup/ && cp research/quality_loop/tests/test_analysis.py /tmp/p2_backup/`

- [ ] **Step 2: write the failing reachability test** (append to `test_analysis.py`)

```python
def test_cleared_is_reachable_det_only():
    """#17 fix: a clean page must be able to CLEAR. Reward is normalized against
    the EARNABLE positives (here P08+P09 = 8, both earned), not the global 92."""
    s = score(make_facts(), [], RUBRIC)
    assert s.reward == pytest.approx(1_000_000)
    assert s.hard_fail is False
    assert cleared(s) is True


def test_penalty_keeps_page_below_clear():
    """A penalty must still drop reward below the bar (penalties untouched)."""
    s = score(make_facts(empty_gap=0.40), [], RUBRIC)  # N08 -6 on earnable base 8
    assert s.reward < 950_000
    assert cleared(s) is False


def test_earnable_max_grows_with_vision_and_stays_gated():
    """With vision, more positives become earnable (P12 pure-VIS, P05 DET-gated);
    earning them clears. A hard-fail still blocks clear regardless of reward."""
    facts = make_facts()  # no missing slots -> P05 DET gate passes
    vis = {"P12": {"score": 3, "rationale": "dense"},
           "P05": {"score": 3, "rationale": "framed portrait"}}
    s = score(facts, [], RUBRIC, vis_results=vis)
    assert cleared(s) is True
    # hard-fail dominance unchanged:
    hf = score(make_facts(required_slots_missing=["case-study-1"]), [], RUBRIC, vis_results=vis)
    assert cleared(hf) is False
```

- [ ] **Step 3: run, expect FAIL**

Run: `cd /Users/utkarsh/Projects/richard/research/quality_loop && /Users/utkarsh/Projects/richard/research/v7-renderer/.venv/bin/python -m pytest tests/test_analysis.py::test_cleared_is_reachable_det_only -q`
Expected: FAIL — current reward is 1e6*8/92 ≈ 86,957, so `cleared` is False.

- [ ] **Step 4: implement** `_earnable_positive_max` in `analysis.py` (after `_det_gate`, ~line 183)

```python
def _earnable_positive_max(facts, vis_results, rubric, st_type: str = "all") -> int:
    """Sum of positive weights that are ACTUALLY earnable for this page (the
    capability-clamped denominator, parent design §5.5). A positive counts iff:
      * it applies to this st_type (applies_to == 'all' or includes st_type), AND
      * pure-DET row: it has a computed fact (fact_key is not None); OR
      * VIS / DET∧VIS row: a vision verdict exists for it AND (for DET∧VIS) its
        DET gate is PROVABLE (_det_gate proven) — an unprovable gate can never be
        earned, so it is a backlog item, not part of the denominator.
    Rows the system cannot currently score are excluded (surfaced as skipped),
    so reward is measured against the achievable bar, not the theoretical 92.
    """
    vis_results = vis_results or {}
    total = 0
    for row in rubric:
        if row.polarity != "positive":
            continue
        if row.applies_to != "all" and st_type not in row.applies_to:
            continue
        if "VIS" in row.detect:
            if row.id not in vis_results:
                continue
            if row.detect == "DET∧VIS":
                _, gate_proven = _det_gate(row.id, facts)
                if not gate_proven:
                    continue
            total += row.weight
        else:  # pure DET positive
            if row.fact_key is None:
                continue
            total += row.weight
    return total
```

- [ ] **Step 5: use it in `score()`** — replace the normalization block (~lines 329-333)

Replace:
```python
    # Normalize to the author's scale, clamped to [0, positive_max]. ----------
    pmax = positive_max()
    clamped = max(0, min(raw_points, pmax))
    raw_pct = clamped / pmax if pmax else 0.0
    reward = 1_000_000 * raw_pct
```
with:
```python
    # Normalize to the author's scale against the EARNABLE positive max (the
    # capability-clamped denominator, §5.5), so the gate is reachable + honest.
    pmax = _earnable_positive_max(
        facts, vis_results, rubric, getattr(facts, "st_type", "all")
    )
    clamped = max(0, min(raw_points, pmax))
    raw_pct = clamped / pmax if pmax else 0.0
    reward = 1_000_000 * raw_pct
```

- [ ] **Step 6: run the reachability tests, expect PASS**

Run: `cd /Users/utkarsh/Projects/richard/research/quality_loop && /Users/utkarsh/Projects/richard/research/v7-renderer/.venv/bin/python -m pytest tests/test_analysis.py -k "reachable or below_clear or grows_with_vision" -q`
Expected: PASS.

- [ ] **Step 7: update the one stale test** `test_reward_clamped_and_normalized`

Its first assertion encodes the OLD global-92 normalization. Update it to the new earnable base (DET-only clean: earnable = P08+P09 = 8, earned = 8 -> reward 1e6). Replace its body's first block:
```python
    clean = score(make_facts(), [], RUBRIC)
    # Earnable positives in DET-only mode are P08 (+4) + P09 (+4) = 8, both
    # earned, so the clean page reaches the full reward (capability-clamped).
    assert clean.reward == pytest.approx(1_000_000)
    assert 0.0 <= clean.reward <= 1_000_000
```
(The "drowning -> 0.0" second half is unchanged and still holds: raw_points clamps to 0.)

- [ ] **Step 8: full target-file run, expect all green**

Run: `cd /Users/utkarsh/Projects/richard/research/quality_loop && /Users/utkarsh/Projects/richard/research/v7-renderer/.venv/bin/python -m pytest tests/test_analysis.py tests/test_references.py -q`
Expected: all pass (the 25 baseline + the 3 new, with the 1 updated).

- [ ] **Step 9: confirm no NEW breakage in the broader suite**

Run: `cd /Users/utkarsh/Projects/richard/research/quality_loop && /Users/utkarsh/Projects/richard/research/v7-renderer/.venv/bin/python -m pytest tests/ -m "not slow" -q 2>&1 | tail -3`
Expected: the SAME 13 pre-existing `OSError` failures as baseline, no new ones (84 -> 87 passed as the 3 new tests land).

---

## Self-review

- **Spec coverage:** infection #17 (cleared unreachable) -> Task 1 (earnable denominator). Addition C "per-st_type maximum" -> the `applies_to`/st_type filter is in the helper (a no-op today since all positives are `applies_to='all'`, but the hook is live for when positives get per-type scoping). A3/treatment grading (addition C second half) -> explicitly deferred to Phase 2b with reason. Engine-pin (A) + contract fail-loud (B) -> deferred to Phase 4 with reason.
- **Anti-reward-hacking preserved:** hard-fail dominance untouched (`cleared` still `and not hard_fail`); penalties untouched (they reduce `raw_points`, not the denominator); the denominator only ever shrinks to the achievable set, never inflates earned. New test `test_earnable_max_grows_with_vision_and_stays_gated` asserts a hard-fail still blocks clear.
- **No false-green beyond the documented capability clamp:** a DET-only clean page clearing reflects "meets all currently-verifiable criteria"; the unverifiable richness stays in `skipped_vis`/`skipped_fact` (backlog), and the deck-level lever-coverage gate (Phase 4) enforces the full richness across the deck.
- **No em dashes; brand-agnostic; backups taken.**
