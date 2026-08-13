"""Transient reviewer failures retry with backoff; exhaustion is honest."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from visual_review_loop_v3 import retry_transient  # noqa: E402


def test_retries_transient_failures_with_backoff() -> None:
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient 503")
        return "ok"

    result = retry_transient(flaky, attempts=3, base_delay_s=0.0)
    assert result == "ok"
    assert calls["n"] == 3


def test_exhausted_returns_none_not_raise() -> None:
    def always_fails(*args, **kwargs):
        raise RuntimeError("still down")

    assert retry_transient(always_fails, attempts=3, base_delay_s=0.0) is None


def test_non_transient_exception_propagates() -> None:
    class DesignDefect(ValueError):
        pass

    def bad(*args, **kwargs):
        raise DesignDefect("not a transient failure")

    try:
        retry_transient(bad, attempts=3, base_delay_s=0.0)
    except DesignDefect:
        return
    raise AssertionError("a non-transient exception must propagate, not retry")


class FakeBuilder:
    """Returns a deterministic build; call count tracks rebuilds.

    The build itself carries NO failures - the review loop judges by the
    REVIEWER's score, not the build's failure list. The repair signal is the
    conductor swapping a variant, which changes the rendered page; the fake
    reviewer below simulates that by improving its score after rebuilds.
    """

    def __init__(self, pass_after: int):
        self.calls = 0
        self.pass_after = pass_after

    def build(self, *args, **kwargs):
        self.calls += 1
        return {"failures": [], "contract_sha256": ("c" if self.calls >= self.pass_after else "d") * 64}


class FakeReviewer:
    """Scores below threshold until the builder has rebuilt `pass_at_calls`
    times (simulating a conductor fix improving the rendered page)."""

    def __init__(self, pass_at_calls: int, threshold: int = 3):
        self.pass_at_calls = pass_at_calls
        self.threshold = threshold
        self.calls = 0

    def score_page(self, page_png, reference_pngs, row_ids):
        self.calls += 1
        score = self.threshold if self.calls >= self.pass_at_calls else 1
        return {row_ids[0]: {"score": score, "rationale": "ok"}}


class FailingReviewer:
    def score_page(self, page_png, reference_pngs, row_ids):
        raise RuntimeError("reviewer API down")


def test_page_repairs_up_to_three_attempts_then_passes() -> None:
    from visual_review_loop_v3 import review_page

    builder = FakeBuilder(pass_after=2)
    result = review_page(
        builder.build, FakeReviewer(pass_at_calls=2), page_png="x.png",
        refs=[], row_ids=["r"], max_attempts=3, threshold=3,
    )
    assert result["passed"] is True
    assert builder.calls == 2


def test_page_that_never_passes_is_rejected() -> None:
    from visual_review_loop_v3 import review_page

    builder = FakeBuilder(pass_after=99)
    result = review_page(
        builder.build, FakeReviewer(pass_at_calls=99), page_png="x.png",
        refs=[], row_ids=["r"], max_attempts=3, threshold=3,
    )
    assert result["passed"] is False
    assert result["verdict"] == "rejected"
    assert result["attempts"] == 3


def test_unreviewable_page_is_honest() -> None:
    from visual_review_loop_v3 import review_page

    result = review_page(
        FakeBuilder(pass_after=1).build, FailingReviewer(), page_png="x.png",
        refs=[], row_ids=["r"], max_attempts=3, threshold=3,
    )
    assert result["passed"] is False
    assert result["verdict"] == "unreviewable"


class DeckBuilder:
    def __init__(self, page_outcome: dict):
        self.page_outcome = page_outcome
        self.calls = 0

    def build(self, *args, **kwargs):
        self.calls += 1
        return {"failures": [], "contract_sha256": "e" * 64}


class DeckReviewer:
    def score_page(self, page_png, refs, row_ids):
        return {row_ids[0]: {"score": 5, "rationale": "ok"}}


def test_whole_deck_pass_runs_once_then_decides() -> None:
    from visual_review_loop_v3 import run_visual_review_loop

    result = run_visual_review_loop(
        DeckBuilder({}).build, DeckReviewer(),
        page_pngs=["p.png"], refs=[], row_ids=["r"],
        max_page_attempts=1, threshold=6, whole_deck_pass=True,
    )
    assert result["release_state"] == "review_required"
    assert result["delivery_pdf_bytes"] is None
    assert result["whole_deck_passes"] == 1


def test_all_pages_pass_reaches_review_candidate() -> None:
    from visual_review_loop_v3 import run_visual_review_loop

    result = run_visual_review_loop(
        DeckBuilder({}).build, DeckReviewer(),
        page_pngs=["p.png"], refs=[], row_ids=["r"],
        max_page_attempts=1, threshold=3, whole_deck_pass=True,
    )
    assert result["release_state"] == "review_candidate"
    assert result["delivery_pdf_bytes"] is None
    assert result["whole_deck_passes"] == 0
