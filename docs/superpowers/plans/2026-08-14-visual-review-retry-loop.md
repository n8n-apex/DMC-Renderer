# Visual-Review Retry Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Never ship a deck without a valid visual-review decision; never block without a retry path. Per page: 3 review attempts with 3 exponential-backoff transient retries each, then 1 whole-deck retry pass, then `review_required` with no delivery PDF.

**Architecture:** A `VisualReviewLoopV3` orchestrator composes the existing v3 builder, the conductor's `propose`/`apply`/`apply_type`, the vision client, and the artifact store. It produces an immutable attempt record per build and decides the release state. `ReleaseState.REVIEW_REQUIRED` is added; `ShipGateV3` transitions updated; `/render-v3` returns 202 JSON (no PDF) for `review_required`.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, FastAPI, httpx (vision client), the existing `research/quality_loop/` + `research/preprocessor/contracts_v3/` modules.

---

## File structure

- `research/preprocessor/contracts_v3/release.py` — add `REVIEW_REQUIRED` state + `ReviewAttemptRecord` model (Modify)
- `research/quality_loop/ship_gate_v3.py` — legal transitions for the new state (Modify)
- `research/quality_loop/visual_review_loop_v3.py` — the orchestrator (Create)
- `research/quality_loop/tests/test_visual_review_loop_v3.py` — unit tests (Create)
- `dmc-renderer/build_v3.py` — wire the loop into `build_and_render_v3` (Modify)
- `dmc-renderer/service.py` — `/render-v3` handles `review_required` (Modify)
- `dmc-renderer/tests/test_v3_release_flow.py` — HTTP/loop integration (Modify)
- `research/artifacts/store.py` — retention class for `review_required` (Modify)

---

### Task 1: Add REVIEW_REQUIRED state + attempt-record model

**Files:**
- Modify: `research/preprocessor/contracts_v3/release.py`
- Test: `research/preprocessor/tests/test_release_states.py`

- [ ] **Step 1: Write the failing test**

```python
# research/preprocessor/tests/test_release_states.py
"""REVIEW_REQUIRED is a distinct, non-shippable release state."""
from contracts_v3.release import ReleaseState, ReviewAttemptRecord, ReviewVerdict


def test_review_required_is_a_distinct_state():
    assert ReleaseState.REVIEW_REQUIRED == "review_required"
    assert ReleaseState.REVIEW_REQUIRED != ReleaseState.REVIEW_CANDIDATE
    assert ReleaseState.REVIEW_REQUIRED != ReleaseState.SHIP_READY


def test_review_attempt_record_holds_the_full_trail():
    record = ReviewAttemptRecord(
        attempt_index=1,
        contract_sha256="a" * 64,
        render_sha256="b" * 64,
        page_scores={"face.01": {"score": 3, "rationale": "ok"}},
        conductor_summary="1 applied, 0 flagged",
        verdict=ReviewVerdict.PASSED,
    )
    assert record.verdict.value == "passed"
    assert record.contract_sha256 == "a" * 64
```

- [ ] **Step 2: Run — expect FAIL** (`ReviewAttemptRecord` undefined)

Run: `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python -m pytest tests/test_release_states.py -q`
Expected: ImportError / FAIL.

- [ ] **Step 3: Implement in `release.py`**

```python
class ReleaseState(str, Enum):
    REJECTED = "rejected"
    DRAFT = "draft"
    REVIEW_CANDIDATE = "review_candidate"
    REVIEW_REQUIRED = "review_required"
    SHIP_READY = "ship_ready"


class ReviewVerdict(str, Enum):
    PASSED = "passed"
    REJECTED = "rejected"
    UNREVIEWABLE = "unreviewable"


class ReviewAttemptRecord(BaseModel):
    """One immutable build+review attempt in the retry trail."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt_index: int = Field(ge=1)
    contract_sha256: str = Field(min_length=64, max_length=64)
    render_sha256: str = Field(min_length=64, max_length=64)
    page_scores: dict[str, dict] = Field(default_factory=dict)
    conductor_summary: str = ""
    verdict: ReviewVerdict
```

- [ ] **Step 4: Run the test — expect PASS**
Run: `cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python -m pytest tests/test_release_states.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**
```bash
cd /Users/utkarsh/Projects/richard
git add research/preprocessor/contracts_v3/release.py research/preprocessor/tests/test_release_states.py
git -c user.name="utkarsh" -c user.email="utkarsh@localhost" commit -m "feat: add REVIEW_REQUIRED release state + attempt record"
```

---

### Task 2: ShipGate transitions for REVIEW_REQUIRED

**Files:**
- Modify: `research/quality_loop/ship_gate_v3.py`
- Test: `research/quality_loop/tests/test_ship_gate_v3.py`

- [ ] **Step 1: Write the failing test**

```python
# research/quality_loop/tests/test_ship_gate_v3.py (append)
from contracts_v3.release import ReleaseState
from ship_gate_v3 import can_transition


def test_review_required_is_a_dead_end_without_human_review():
    assert can_transition(ReleaseState.REVIEW_REQUIRED, ReleaseState.REVIEW_CANDIDATE)
    assert can_transition(ReleaseState.REVIEW_REQUIRED, ReleaseState.REJECTED)
    assert can_transition(ReleaseState.REVIEW_REQUIRED, ReleaseState.DRAFT)
    assert not can_transition(ReleaseState.REVIEW_REQUIRED, ReleaseState.SHIP_READY)
    # every other state may land on REVIEW_REQUIRED
    for current in ReleaseState:
        if current is not ReleaseState.REVIEW_REQUIRED:
            assert can_transition(current, ReleaseState.REVIEW_REQUIRED), current
```

- [ ] **Step 2: Run — expect FAIL** (`can_transition` returns False for the new state since it is not in the table).

- [ ] **Step 3: Implement in `ship_gate_v3.py`**

```python
_LEGAL_TRANSITIONS = {
    ReleaseState.REJECTED: {ReleaseState.REJECTED, ReleaseState.DRAFT},
    ReleaseState.DRAFT: {
        ReleaseState.REJECTED, ReleaseState.DRAFT, ReleaseState.REVIEW_CANDIDATE,
    },
    ReleaseState.REVIEW_CANDIDATE: {
        ReleaseState.REJECTED, ReleaseState.DRAFT, ReleaseState.REVIEW_CANDIDATE,
        ReleaseState.REVIEW_REQUIRED, ReleaseState.SHIP_READY,
    },
    ReleaseState.REVIEW_REQUIRED: {
        ReleaseState.REJECTED, ReleaseState.DRAFT, ReleaseState.REVIEW_CANDIDATE,
    },
    ReleaseState.SHIP_READY: {
        ReleaseState.REJECTED, ReleaseState.DRAFT, ReleaseState.REVIEW_CANDIDATE,
        ReleaseState.REVIEW_REQUIRED, ReleaseState.SHIP_READY,
    },
}
```

- [ ] **Step 4: Run — expect PASS**
Run: `cd /Users/utkarsh/Projects/richard/research/quality_loop && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../v7-renderer/.venv/bin/python -m pytest tests/test_ship_gate_v3.py -q`
Expected: all pass (existing + new).

- [ ] **Step 5: Commit**
```bash
cd /Users/utkarsh/Projects/richard
git add research/quality_loop/ship_gate_v3.py research/quality_loop/tests/test_ship_gate_v3.py
git -c user.name="utkarsh" -c user.email="utkarsh@localhost" commit -m "feat: ShipGate transitions for REVIEW_REQUIRED"
```

---

### Task 3: Transient-failure retry with exponential backoff

**Files:**
- Create: `research/quality_loop/visual_review_loop_v3.py`
- Test: `research/quality_loop/tests/test_visual_review_loop_v3.py`

- [ ] **Step 1: Write the failing test for the retry helper**

```python
# research/quality_loop/tests/test_visual_review_loop_v3.py
"""Transient reviewer failures retry with backoff; exhaustion is honest."""
from visual_review_loop_v3 import retry_transient


def test_retries_transient_failures_with_backoff():
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient 503")
        return "ok"

    result = retry_transient(flaky, attempts=3, base_delay_s=0.0)
    assert result == "ok"
    assert calls["n"] == 3


def test_exhausted_returns_none_not_raise():
    def always_fails(*args, **kwargs):
        raise RuntimeError("still down")

    assert retry_transient(always_fails, attempts=3, base_delay_s=0.0) is None
```

- [ ] **Step 2: Run — expect FAIL** (`visual_review_loop_v3` undefined).

- [ ] **Step 3: Implement the module skeleton with the retry helper**

```python
"""VisualReviewLoopV3: build -> review -> repair -> re-review, fail-closed."""
from __future__ import annotations

import time
from typing import Any, Callable

TRANSIENT_EXC = (RuntimeError, TimeoutError, ConnectionError)


def retry_transient(
    fn: Callable[..., Any],
    *,
    attempts: int,
    base_delay_s: float = 1.0,
    exc_types: tuple[type, ...] = TRANSIENT_EXC,
) -> Any | None:
    """Call fn up to `attempts` times; exponential backoff between attempts.

    Returns the first successful result, or None after the last failure.
    Non-transient exceptions propagate (a design defect is not retryable).
    """
    for attempt in range(attempts):
        try:
            return fn()
        except exc_types:
            if attempt == attempts - 1:
                return None
            time.sleep(base_delay_s * (2 ** attempt))
    return None
```

- [ ] **Step 4: Run — expect PASS**
Run: `cd /Users/utkarsh/Projects/richard/research/quality_loop && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../v7-renderer/.venv/bin/python -m pytest tests/test_visual_review_loop_v3.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**
```bash
cd /Users/utkarsh/Projects/richard
git add research/quality_loop/visual_review_loop_v3.py research/quality_loop/tests/test_visual_review_loop_v3.py
git -c user.name="utkarsh" -c user.email="utkarsh@localhost" commit -m "feat: transient retry with backoff for visual review"
```

---

### Task 4: Per-page review+repair loop (3 attempts)

**Files:**
- Modify: `research/quality_loop/visual_review_loop_v3.py`
- Test: `research/quality_loop/tests/test_visual_review_loop_v3.py`

- [ ] **Step 1: Write the failing test for the page loop**

```python
from visual_review_loop_v3 import review_page


class FakeBuilder:
    """Returns a deterministic build; call count tracks rebuilds."""
    def __init__(self, pass_after: int):
        self.calls = 0
        self.pass_after = pass_after

    def build(self, *args, **kwargs):
        self.calls += 1
        if self.calls >= self.pass_after:
            return {"failures": [], "contract_sha256": "c" * 64}
        return {"failures": [{"code": "dead_space_region", "face_ids": ("face.01",)}],
                "contract_sha256": "d" * 64}


class FakeReviewer:
    def score_page(self, page_png: str, reference_pngs, row_ids):
        return {"face.01": {"score": 4, "rationale": "ok"}}


def test_page_repairs_up_to_three_attempts_then_passes():
    builder = FakeBuilder(pass_after=2)
    result = review_page(
        builder.build, FakeReviewer(), page_png="x.png", refs=[], row_ids=["r"],
        max_attempts=3, threshold=3,
    )
    assert result["passed"] is True
    assert builder.calls == 2


def test_page_that_never_passes_is_unreviewable():
    builder = FakeBuilder(pass_after=99)
    result = review_page(
        builder.build, FakeReviewer(), page_png="x.png", refs=[], row_ids=["r"],
        max_attempts=3, threshold=3,
    )
    assert result["passed"] is False
    assert result["verdict"] == "rejected"
```

- [ ] **Step 2: Run — expect FAIL** (`review_page` undefined).

- [ ] **Step 3: Implement `review_page`**

```python
def review_page(
    build_fn: Callable[..., dict],
    reviewer: Any,
    *,
    page_png: str,
    refs: list[str],
    row_ids: list[str],
    max_attempts: int,
    threshold: int,
    conductor: Callable[..., Any] | None = None,
) -> dict:
    """Review one page: build -> score -> conductor repair -> rebuild.

    Returns {"passed": bool, "verdict": str, "attempts": int, "scores": [...]}.
    Each attempt is a fresh build via build_fn. A page that cannot reach the
    threshold after max_attempts is "rejected"; a page the reviewer cannot
    score (unreviewable) is returned as such.
    """
    best_scores: list[dict] = []
    for attempt in range(1, max_attempts + 1):
        build = build_fn()
        scores = retry_transient(
            lambda: reviewer.score_page(page_png, refs, row_ids),
            attempts=3,
            base_delay_s=0.0,
        )
        if scores is None:
            return {"passed": False, "verdict": "unreviewable",
                    "attempts": attempt, "scores": best_scores}
        best_scores.append(scores)
        face_scores = [s.get("score", 0) for s in scores.values()]
        if face_scores and min(face_scores) >= threshold:
            return {"passed": True, "verdict": "passed",
                    "attempts": attempt, "scores": best_scores}
        if conductor is not None:
            plan = conductor(build)
            if not plan.get("changed"):
                break
    return {"passed": False, "verdict": "rejected",
            "attempts": max_attempts, "scores": best_scores}
```

- [ ] **Step 4: Run — expect PASS** (2 new tests + the 2 retry tests).

- [ ] **Step 5: Commit**
```bash
cd /Users/utkarsh/Projects/richard
git add research/quality_loop/visual_review_loop_v3.py research/quality_loop/tests/test_visual_review_loop_v3.py
git -c user.name="utkarsh" -c user.email="utkarsh@localhost" commit -m "feat: per-page review+repair loop"
```

---

### Task 5: Whole-deck retry pass + REVIEW_REQUIRED decision

**Files:**
- Modify: `research/quality_loop/visual_review_loop_v3.py`
- Test: `research/quality_loop/tests/test_visual_review_loop_v3.py`

- [ ] **Step 1: Write the failing test**

```python
from visual_review_loop_v3 import run_visual_review_loop


class DeckBuilder:
    def __init__(self, page_results: list[dict]):
        self.page_results = page_results
        self.calls = 0

    def build(self, *args, **kwargs):
        self.calls += 1
        return {"failures": [], "contract_sha256": "e" * 64,
                "page_results": self.page_results}


class DeckReviewer:
    def score_page(self, page_png, refs, row_ids):
        return {row_ids[0]: {"score": 5, "rationale": "ok"}}


def test_whole_deck_pass_runs_once_then_decides():
    builder = DeckBuilder([{"passed": False, "verdict": "rejected"}])
    result = run_visual_review_loop(
        builder.build, DeckReviewer(),
        page_pngs=["p.png"], refs=[], row_ids=["r"],
        max_page_attempts=3, threshold=3, whole_deck_pass=True,
    )
    assert result["release_state"] == "review_required"
    assert result["delivery_pdf_bytes"] is None
    assert result["whole_deck_passes"] == 1


def test_all_pages_pass_reaches_review_candidate():
    builder = DeckBuilder([{"passed": True, "verdict": "passed"}])
    result = run_visual_review_loop(
        builder.build, DeckReviewer(),
        page_pngs=["p.png"], refs=[], row_ids=["r"],
        max_page_attempts=3, threshold=3, whole_deck_pass=True,
    )
    assert result["release_state"] == "review_candidate"
```

- [ ] **Step 2: Run — expect FAIL** (`run_visual_review_loop` undefined).

- [ ] **Step 3: Implement the orchestrator**

```python
def run_visual_review_loop(
    build_fn: Callable[..., dict],
    reviewer: Any,
    *,
    page_pngs: list[str],
    refs: list[str],
    row_ids: list[str],
    max_page_attempts: int,
    threshold: int,
    whole_deck_pass: bool = True,
) -> dict:
    """Build -> review every page -> one whole-deck retry -> decide.

    Returns {"release_state": str, "delivery_pdf_bytes": None,
             "attempt_records": [...], "whole_deck_passes": int}.
    ship_ready is NOT produced here: it additionally requires calibrated
    human threshold evidence, which the existing gate owns.
    """
    attempt_records: list[dict] = []
    whole_deck_passes = 0
    pending = list(range(len(page_pngs)))
    # Per-page review (first pass)
    page_outcomes: dict[int, dict] = {}
    for idx in pending:
        page_outcomes[idx] = review_page(
            build_fn, reviewer,
            page_png=page_pngs[idx], refs=refs, row_ids=[row_ids[idx]],
            max_attempts=max_page_attempts, threshold=threshold,
        )
        attempt_records.append({"page": idx, **page_outcomes[idx]})

    # One whole-deck retry: re-review only the failed pages
    if whole_deck_pass and any(not o["passed"] for o in page_outcomes.values()):
        whole_deck_passes += 1
        for idx, outcome in list(page_outcomes.items()):
            if outcome["passed"]:
                continue
            retried = review_page(
                build_fn, reviewer,
                page_png=page_pngs[idx], refs=refs, row_ids=[row_ids[idx]],
                max_attempts=max_page_attempts, threshold=threshold,
            )
            page_outcomes[idx] = retried
            attempt_records.append({"page": idx, "whole_deck": True, **retried})

    if all(o["passed"] for o in page_outcomes.values()):
        release_state = "review_candidate"
    else:
        unreviewable = any(o["verdict"] == "unreviewable" for o in page_outcomes.values())
        release_state = "review_required"
        if unreviewable:
            release_state = "review_required"  # honest: reviewer could not run

    return {
        "release_state": release_state,
        "delivery_pdf_bytes": None,
        "attempt_records": attempt_records,
        "whole_deck_passes": whole_deck_passes,
        "page_outcomes": page_outcomes,
    }
```

- [ ] **Step 4: Run — expect PASS** (2 new tests + previous).

- [ ] **Step 5: Commit**
```bash
cd /Users/utkarsh/Projects/richard
git add research/quality_loop/visual_review_loop_v3.py research/quality_loop/tests/test_visual_review_loop_v3.py
git -c user.name="utkarsh" -c user.email="utkarsh@localhost" commit -m "feat: whole-deck retry pass + REVIEW_REQUIRED decision"
```

---

### Task 6: Wire the loop into build_and_render_v3

**Files:**
- Modify: `dmc-renderer/build_v3.py`
- Test: `dmc-renderer/tests/test_v3_release_flow.py`

- [ ] **Step 1: Write the failing test**

```python
# dmc-renderer/tests/test_v3_release_flow.py (append)
import pytest

from build_v3 import build_and_render_v3
from quality_loop.visual_review_loop_v3 import run_visual_review_loop


def test_visual_review_exhausted_returns_review_required_without_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deck whose pages can never pass visual review must NOT ship a PDF."""
    from test_build_v3 import valid_envelope
    from contracts_v3.release import ReleaseState
    import tempfile
    from pathlib import Path

    monkeypatch.setattr(
        "quality_loop.visual_review_loop_v3.run_visual_review_loop",
        lambda *args, **kwargs: {
            "release_state": "review_required",
            "delivery_pdf_bytes": None,
            "attempt_records": [],
            "whole_deck_passes": 1,
        },
    )
    envelope = valid_envelope(Path(tempfile.mkdtemp()) / "assets")
    with pytest.raises(Exception) as caught:
        build_and_render_v3(envelope, output_dir=Path(tempfile.mkdtemp()) / "b", cleanup=False)
    assert "review_required" in str(caught.value)
```

- [ ] **Step 2: Run — expect FAIL** (build_v3 does not consult the loop yet).

- [ ] **Step 3: Implement the wiring**

In `build_v3.py`, after the deterministic gate result is computed (`gate_result = _evaluate_release(failures, context)` at ~line 660), consult the visual-review loop before deciding delivery:

```python
# Visual-review retry loop (fail-closed): never ship an ungraded deck.
# The loop reuses the conductor's fix proposals per page; a page that
# cannot pass after its attempts, or a reviewer that cannot run, yields
# REVIEW_REQUIRED with NO delivery PDF.
from quality_loop.visual_review_loop_v3 import run_visual_review_loop  # noqa: PLC0415

loop_result = run_visual_review_loop(
    lambda: build_and_render_v3_inner,
    ...,
)
```

(Implementation detail: extract the current single-build body into
`_build_once` so the loop can call it per attempt, then have
`build_and_render_v3` call `_build_once` and run the loop. A page whose
deterministic failures include a HARD severity keeps `REJECTED` (unchanged);
only pages that pass deterministic gates enter the visual loop. The
`visual_review_evidence_v3` path is unchanged for `ship_ready`.)

- [ ] **Step 4: Run — expect PASS**
Run: `cd /Users/utkarsh/Projects/richard/dmc-renderer && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python -m pytest tests/test_v3_release_flow.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**
```bash
cd /Users/utkarsh/Projects/richard
git add dmc-renderer/build_v3.py dmc-renderer/tests/test_v3_release_flow.py
git -c user.name="utkarsh" -c user.email="utkarsh@localhost" commit -m "feat: wire visual-review retry loop into v3 build"
```

---

### Task 7: /render-v3 returns review_required (202 JSON, no PDF)

**Files:**
- Modify: `dmc-renderer/service.py`
- Test: `dmc-renderer/tests/test_service_v3.py`

- [ ] **Step 1: Write the failing test**

```python
# dmc-renderer/tests/test_service_v3.py (append)
def test_render_v3_review_required_returns_202_json_no_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        service, "build_and_render_v3",
        lambda body, **_kwargs: {
            "release_state": "review_required",
            "delivery_pdf_bytes": None,
            "failures": [{"code": "visual_review_rejected"}],
            "hashes": {"raw_pdf_sha256": "a" * 64},
            "face_count": 20,
            "fragment_count": 19,
            "physical_pages": 19,
        },
    )
    response = service.render_v3_endpoint(envelope())
    assert response.status_code == 202
    assert response.headers["content-type"].startswith("application/json")
    assert b"%PDF" not in response.body
```

- [ ] **Step 2: Run — expect FAIL** (endpoint raises on unknown state or returns a PDF).

- [ ] **Step 3: Implement in `service.py`**

After the `release_state` validation block (line ~686), add:

```python
if release_state == "review_required":
    from fastapi.responses import JSONResponse as _JSONResponse

    return _JSONResponse(
        status_code=202,
        content={
            "release_state": "review_required",
            "detail": "visual review did not pass after all retries; a human must review",
            "failures": [f.get("code") for f in result.get("failures", [])],
            "attempt_records": result.get("attempt_records", []),
            "artifact_manifest": result.get("artifact_manifest"),
        },
        headers={
            "X-DMC-Release-State": "review_required",
            "X-DMC-Artifact-Manifest-SHA256": str(
                (result.get("artifact_manifest") or {}).get("manifest_sha256", "")
            ),
        },
    )
```

- [ ] **Step 4: Run — expect PASS**
Run: `cd /Users/utkarsh/Projects/richard/dmc-renderer && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python -m pytest tests/test_service_v3.py tests/test_service_auth.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**
```bash
cd /Users/utkarsh/Projects/richard
git add dmc-renderer/service.py dmc-renderer/tests/test_service_v3.py
git -c user.name="utkarsh" -c user.email="utkarsh@localhost" commit -m "feat: /render-v3 returns 202 review_required JSON, no PDF"
```

---

### Task 8: Artifact retention for review_required

**Files:**
- Modify: `research/artifacts/store.py`
- Test: `dmc-renderer/tests/test_v3_artifact_persistence.py`

- [ ] **Step 1: Write the failing test**

```python
# dmc-renderer/tests/test_v3_artifact_persistence.py (append)
def test_review_required_retains_attempt_records_and_no_delivery(
    tmp_path: Path,
) -> None:
    """REVIEW_REQUIRED retains the review attempt trail, never a delivery PDF."""
    from research.artifacts.store import FilesystemArtifactStore
    store = FilesystemArtifactStore(tmp_path / "store")
    record = store.persist(
        build_record={
            "release_state": "review_required",
            "attempt_records": [{"page": 0, "verdict": "rejected"}],
        },
        retention_class="review_required",
        files={
            "raw_pdf": tmp_path / "raw.pdf",
            "attempt_records": tmp_path / "attempts.json",
        },
    )
    assert record["retention_class"] == "review_required"
    # a review_required build never carries a delivery PDF
    assert "delivery_pdf" not in record.get("files", {})
```

- [ ] **Step 2: Run — expect FAIL** (`review_required` retention class unknown).

- [ ] **Step 3: Implement in `store.py`** — add `"review_required"` to the retention-class table (retains the ledger, HTML, raw PDF, attempt records; no delivery files), mirroring the existing `review` class.

- [ ] **Step 4: Run — expect PASS**
Run: `cd /Users/utkarsh/Projects/richard/dmc-renderer && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python -m pytest tests/test_v3_artifact_persistence.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**
```bash
cd /Users/utkarsh/Projects/richard
git add research/artifacts/store.py dmc-renderer/tests/test_v3_artifact_persistence.py
git -c user.name="utkarsh" -c user.email="utkarsh@localhost" commit -m "feat: review_required artifact retention"
```

---

### Task 9: Full-suite verification + harness update

**Files:**
- Modify: `research/quality_loop/closed_gaps_registry.json` (add the new gap entry)
- Modify: `docs/phase-zero/BASELINE-LEDGER-2026-08-14.md` (new ledger entry)

- [ ] **Step 1: Run all suites**

```bash
cd /Users/utkarsh/Projects/richard/research/preprocessor && .venv/bin/python -m pytest tests -q
cd /Users/utkarsh/Projects/richard/research/quality_loop && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../v7-renderer/.venv/bin/python -m pytest tests/test_visual_review_loop_v3.py tests/test_ship_gate_v3.py tests/test_assess_closed_gaps.py -q
cd /Users/utkarsh/Projects/richard/dmc-renderer && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ../research/v7-renderer/.venv/bin/python -m pytest tests/ -q
```
Expected: preprocessor 734+2; quality_loop new tests pass; dmc-renderer 128+ passes, 0 failures.

- [ ] **Step 2: Add the new gap to the assessment registry**

```json
{
  "id": "G25",
  "description": "visual review never ships an ungraded deck (retry loop + review_required)",
  "check_type": "test",
  "check": "research/quality_loop/tests/test_visual_review_loop_v3.py",
  "owner": "quality_loop"
}
```

- [ ] **Step 3: Run the harness**

```bash
cd /Users/utkarsh/Projects/richard
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib research/v7-renderer/.venv/bin/python research/quality_loop/assess_closed_gaps.py --fast
```
Expected: exit 0, new G25 CLOSED.

- [ ] **Step 4: Update the baseline ledger** with the new counts + the G25 entry.

- [ ] **Step 5: Commit**
```bash
cd /Users/utkarsh/Projects/richard
git add research/quality_loop/closed_gaps_registry.json docs/phase-zero/BASELINE-LEDGER-2026-08-14.md
git -c user.name="utkarsh" -c user.email="utkarsh@localhost" commit -m "feat: add G25 visual-review gate to assessment + ledger"
```

---

## Definition of done

- A deck whose pages cannot pass visual review after 3 page attempts + 1
  whole-deck pass returns `review_required` with no PDF (202 JSON).
- Transient reviewer failures retry 3× with exponential backoff; exhaustion
  is honest (`unreviewable`), never a silent pass.
- `ShipGateV3` treats `review_required` as a human-gated state.
- Attempt records are retained immutably; no delivery PDF for that class.
- All suites green; the standing assessment harness reports G25 CLOSED.
