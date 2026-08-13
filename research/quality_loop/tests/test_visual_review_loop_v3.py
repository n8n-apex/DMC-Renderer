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


class RepairableBuilder:
    """Builds change their rendered page when overrides arrive; the reviewer
    passes only once the rebuild (variant swap) happened."""

    def __init__(self, page_key: str, pass_after_rebuilds: int = 1):
        self.page_key = page_key
        self.calls = 0
        self.rebuilds = 0
        self.received_overrides: list[tuple] = []
        self.pass_after_rebuilds = pass_after_rebuilds

    def build(self, plan_override=None, facts_override=None):
        self.calls += 1
        if plan_override is not None or facts_override is not None:
            self.rebuilds += 1
        self.received_overrides.append((plan_override, facts_override))
        return {
            "failures": [],
            "contract_sha256": "f" * 64,
            "page_pngs": {self.page_key: f"render-{self.calls}.png"},
        }


class RepairAwareReviewer:
    def __init__(self, threshold: int = 3, pass_on_png: str = "render-2.png"):
        self.threshold = threshold
        self.pass_on_png = pass_on_png
        self.scored_pngs: list[str] = []

    def score_page(self, page_png, reference_pngs, row_ids):
        self.scored_pngs.append(page_png)
        score = self.threshold if page_png == self.pass_on_png else 1
        return {row_ids[0]: {"score": score, "rationale": "ok"}}


class OneShotConductor:
    """Proposes one variant swap (changed=True once), then stalls."""

    def __init__(self):
        self.calls = 0

    def __call__(self, build):
        self.calls += 1
        if self.calls == 1:
            return {
                "changed": True,
                "plan_override": {"face.01": {"variant_id": "v2"}},
                "facts_override": {"face.01": {"font_size_pt": 9.5}},
            }
        return {"changed": False}


class StalledConductor:
    def __call__(self, build):
        return {"changed": False}


def test_conductor_repair_rebuilds_and_scores_the_fresh_render() -> None:
    """A rejected page is repaired: the conductor proposes a plan change, the
    builder rebuilds WITH the overrides, and the review scores the NEW render."""
    from visual_review_loop_v3 import review_page

    builder = RepairableBuilder(page_key="r")
    reviewer = RepairAwareReviewer(pass_on_png="render-2.png")
    result = review_page(
        builder.build, reviewer,
        page_png="render-1.png", refs=[], row_ids=["r"],
        max_attempts=3, threshold=3,
        conductor=OneShotConductor(),
    )
    assert result["passed"] is True
    assert builder.rebuilds == 1
    assert builder.received_overrides[1] == (
        {"face.01": {"variant_id": "v2"}},
        {"face.01": {"font_size_pt": 9.5}},
    )
    assert reviewer.scored_pngs == ["render-1.png", "render-2.png"]


def test_stalled_repair_stops_the_ladder_early_and_rejects() -> None:
    """A conductor that cannot propose a change must not burn the remaining
    attempts re-scoring an identical render."""
    from visual_review_loop_v3 import review_page

    builder = RepairableBuilder(page_key="r")
    result = review_page(
        builder.build, RepairAwareReviewer(), page_png="render-1.png",
        refs=[], row_ids=["r"], max_attempts=3, threshold=3,
        conductor=StalledConductor(),
    )
    assert result["passed"] is False
    assert result["verdict"] == "rejected"
    assert builder.calls == 1  # no pointless rebuilds after a stall


def test_run_loop_forwards_conductor_and_records_rebuild_evidence() -> None:
    """The deck-level loop accepts a conductor, repairs a failing page, and
    lands on review_candidate with the rebuild trail recorded."""
    from visual_review_loop_v3 import run_visual_review_loop

    builder = RepairableBuilder(page_key="r")
    result = run_visual_review_loop(
        builder.build, RepairAwareReviewer(),
        page_pngs=["render-1.png"], refs=[], row_ids=["r"],
        max_page_attempts=3, threshold=3,
        conductor=OneShotConductor(),
    )
    assert result["release_state"] == "review_candidate"
    assert builder.rebuilds == 1
    assert any("repair" in rec or "rebuilds" in rec for rec in result["attempt_records"])
    assert result["page_outcomes"][0]["passed"] is True
