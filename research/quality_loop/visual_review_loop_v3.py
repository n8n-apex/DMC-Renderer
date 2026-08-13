"""VisualReviewLoopV3: build -> review -> repair -> re-review, fail-closed.

The v3 pipeline used to ship a deck even when the visual reviewer could not
run (an OpenRouter failure became an "other" flag and the PDF was still
returned). This orchestrator makes that impossible: a page is reviewed, a
transient reviewer failure is retried with backoff, a rejected page is
repaired by the conductor and rebuilt, and a deck that still cannot pass
after the whole retry ladder returns REVIEW_REQUIRED with no delivery PDF.

Components reused, not rebuilt: the v3 builder, the conductor's propose/apply
(renderer-fixable knobs), the vision client, and the artifact store. The loop
only decides the visual half of the release state; deterministic hard
failures still keep REJECTED, and ship_ready still requires calibrated human
threshold evidence owned by the existing gate.
"""
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
            time.sleep(base_delay_s * (2**attempt))
    return None


def _current_png(build: dict, page_png: str, row_ids: list[str]) -> str:
    """The FRESH render for this page when the build provides per-row PNGs;
    the caller's static path is the fallback (legacy builders)."""
    by_row = build.get("page_pngs")
    if isinstance(by_row, dict) and row_ids:
        fresh = by_row.get(row_ids[0])
        if fresh:
            return fresh
    return page_png


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
    """Review one page: build -> score -> conductor repair -> REBUILD -> re-score.

    Each attempt consumes the builder's LATEST render (build["page_pngs"][row]
    when the build provides one). On a below-threshold score the conductor is
    asked for a plan change; a changed plan (with overrides) is fed back into
    build_fn(plan_override=..., facts_override=...) so the next attempt scores
    a genuinely rebuilt page. A stalled conductor (no change) stops the ladder
    early — re-scoring an identical render is pointless. A transient reviewer
    failure is retried; a page the reviewer cannot score at all is
    "unreviewable" (honest, never a silent pass).

    Returns {"passed": bool, "verdict": str, "attempts": int, "scores": [...],
             "rebuilds": int}.
    """
    best_scores: list[dict] = []
    rebuilds = 0
    pending_plan: Any = None
    pending_facts: Any = None
    for attempt in range(1, max_attempts + 1):
        build = build_fn(plan_override=pending_plan, facts_override=pending_facts)
        pending_plan = pending_facts = None
        png = _current_png(build, page_png, row_ids)
        scores = retry_transient(
            lambda: reviewer.score_page(png, refs, row_ids),
            attempts=3,
            base_delay_s=0.0,
        )
        if scores is None:
            return {
                "passed": False,
                "verdict": "unreviewable",
                "attempts": attempt,
                "scores": best_scores,
                "rebuilds": rebuilds,
            }
        best_scores.append(scores)
        face_scores = [s.get("score", 0) for s in scores.values()]
        if face_scores and min(face_scores) >= threshold:
            return {
                "passed": True,
                "verdict": "passed",
                "attempts": attempt,
                "scores": best_scores,
                "rebuilds": rebuilds,
            }
        if attempt == max_attempts:
            break
        if conductor is not None:
            plan = conductor(build, row_id=row_ids[0], scores=scores)
            pending_plan = plan.get("plan_override") if isinstance(plan, dict) else None
            pending_facts = plan.get("facts_override") if isinstance(plan, dict) else None
            if not (plan or {}).get("changed") or (pending_plan is None and pending_facts is None):
                break
            rebuilds += 1
    return {
        "passed": False,
        "verdict": "rejected",
        "attempts": max_attempts,
        "scores": best_scores,
        "rebuilds": rebuilds,
    }


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
    conductor: Callable[..., Any] | None = None,
) -> dict:
    """Build -> review every page -> one whole-deck retry -> decide.

    Per-page attempts first; a failing page is re-reviewed once more in the
    whole-deck pass (which re-reviews ONLY the failed pages). A conductor may
    be supplied so a rejected page is repaired via rebuild between attempts.
    The result is either review_candidate (all pages pass) or
    review_required (some page is rejected or unreviewable). NEVER produces a
    delivery PDF here; ship_ready stays owned by the calibrated human gate.

    Returns {"release_state": str, "delivery_pdf_bytes": None,
             "attempt_records": list[dict], "whole_deck_passes": int,
             "page_outcomes": dict[int, dict]}.
    """
    attempt_records: list[dict] = []
    whole_deck_passes = 0
    page_outcomes: dict[int, dict] = {}

    for idx in range(len(page_pngs)):
        outcome = review_page(
            build_fn, reviewer,
            page_png=page_pngs[idx], refs=refs, row_ids=[row_ids[idx]],
            max_attempts=max_page_attempts, threshold=threshold,
            conductor=conductor,
        )
        page_outcomes[idx] = outcome
        attempt_records.append({"page": idx, **outcome})

    if whole_deck_pass and any(not o["passed"] for o in page_outcomes.values()):
        whole_deck_passes += 1
        for idx, outcome in list(page_outcomes.items()):
            if outcome["passed"]:
                continue
            retried = review_page(
                build_fn, reviewer,
                page_png=page_pngs[idx], refs=refs, row_ids=[row_ids[idx]],
                max_attempts=max_page_attempts, threshold=threshold,
                conductor=conductor,
            )
            page_outcomes[idx] = retried
            attempt_records.append({"page": idx, "whole_deck": True, **retried})

    if all(o["passed"] for o in page_outcomes.values()):
        release_state = "review_candidate"
    else:
        release_state = "review_required"

    return {
        "release_state": release_state,
        "delivery_pdf_bytes": None,
        "attempt_records": attempt_records,
        "whole_deck_passes": whole_deck_passes,
        "page_outcomes": page_outcomes,
    }
