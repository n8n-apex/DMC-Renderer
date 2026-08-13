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

    Each attempt is a fresh build via build_fn (a rebuild after a conductor
    fix). A transient reviewer failure is retried; a page the reviewer cannot
    score at all is "unreviewable" (honest, never a silent pass). A page that
    never reaches the threshold after max_attempts is "rejected".

    Returns {"passed": bool, "verdict": str, "attempts": int, "scores": [...]}.
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
            return {
                "passed": False,
                "verdict": "unreviewable",
                "attempts": attempt,
                "scores": best_scores,
            }
        best_scores.append(scores)
        face_scores = [s.get("score", 0) for s in scores.values()]
        if face_scores and min(face_scores) >= threshold:
            return {
                "passed": True,
                "verdict": "passed",
                "attempts": attempt,
                "scores": best_scores,
            }
        if conductor is not None:
            plan = conductor(build)
            if not plan.get("changed"):
                break
    return {
        "passed": False,
        "verdict": "rejected",
        "attempts": max_attempts,
        "scores": best_scores,
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
) -> dict:
    """Build -> review every page -> one whole-deck retry -> decide.

    Per-page attempts first; a failing page is re-reviewed once more in the
    whole-deck pass (which re-reviews ONLY the failed pages). The result is
    either review_candidate (all pages pass) or review_required (some page
    is rejected or unreviewable). NEVER produces a delivery PDF here;
    ship_ready stays owned by the calibrated human gate.

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
