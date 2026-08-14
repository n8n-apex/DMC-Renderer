"""The v3 convergence loop: build, gate, decide, rebuild.

Until now the v3 gates were read-only. They named a defect and stopped, so
every repair was made by a person reading a failure list and editing a plan.
That is why the system only improved when someone told it to.

This closes the loop:

    build -> gate -> conductor decides -> patch a COPY of the plan -> rebuild

It stops for one of three honest reasons, never because it ran out of ideas
quietly:

  * converged  - no renderer-fixable defect remains
  * exhausted  - every remaining defect is at the end of its knob's ladder
  * stalled    - a pass changed the plan and the failure count did not improve

A pass that makes things worse is rolled back. The loop keeps the best build
it saw, not the last one, because a loop that can regress is worse than no
loop at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from quality_loop.conductor_v3 import ConductorReport, apply, apply_type, propose


@dataclass
class Pass:
    """One time round the loop, kept so the decision trail is inspectable."""

    index: int
    failure_count: int
    codes: dict[str, int]
    report: ConductorReport | None = None
    accepted: bool = True
    note: str = ""


@dataclass
class ConvergenceResult:
    """The best build the loop found, and how it got there."""

    result: dict[str, Any]
    passes: list[Pass] = field(default_factory=list)
    stop_reason: str = "converged"

    @property
    def improved_by(self) -> int:
        if not self.passes:
            return 0
        return self.passes[0].failure_count - min(p.failure_count for p in self.passes)

    def trail(self) -> str:
        lines = [f"stopped: {self.stop_reason}, improved by {self.improved_by}"]
        for item in self.passes:
            mark = "" if item.accepted else "  (rolled back)"
            lines.append(
                f"  pass {item.index}: {item.failure_count} failures"
                + (f" -- {item.report.summary()}" if item.report else "")
                + mark
                + (f" [{item.note}]" if item.note else "")
            )
        return "\n".join(lines)


def _codes(failures) -> dict[str, int]:
    counts: dict[str, int] = {}
    for failure in failures:
        code = getattr(failure, "code", None) or failure.get("code", "")
        counts[code] = counts.get(code, 0) + 1
    return counts


def converge_v3(
    envelope: dict,
    *,
    builder: Callable[..., dict],
    output_dir: Path,
    max_passes: int = 3,
) -> ConvergenceResult:
    """Build the report, then let the conductor improve it until it cannot.

    `max_passes` is small on purpose. Each pass is a full render, and the
    knob ladders are short: a face that has not improved in three steps is
    telling you the defect is not renderer-fixable.
    """
    best: dict[str, Any] | None = None
    best_count = None
    passes: list[Pass] = []
    plan_override = None
    facts_override = None
    stop_reason = "converged"

    for index in range(1, max_passes + 1):
        result = builder(
            envelope,
            output_dir=output_dir / f"pass-{index}",
            cleanup=False,
            composition_plan_override=plan_override,
            facts_override=facts_override,
        )
        failures = tuple(result.get("failures", ()))
        record = Pass(index=index, failure_count=len(failures), codes=_codes(failures))

        if best_count is None or len(failures) < best_count:
            best, best_count = result, len(failures)
        elif plan_override is not None:
            # This pass came from a conductor change and did not help.
            record.accepted = False
            record.note = "no improvement; keeping the previous build"
            passes.append(record)
            stop_reason = "stalled"
            break

        report = propose(
            failures,
            result["composition_plan"],
            result["registry"],
            facts_by_face=result.get("facts_by_face"),
        )
        record.report = report
        passes.append(record)

        if not report.changed:
            stop_reason = "exhausted" if report.exhausted else "converged"
            break
        plan_override = apply(result["composition_plan"], report)
        facts_override = apply_type(result.get("facts_by_face") or {}, report)

    else:
        stop_reason = "max_passes"

    return ConvergenceResult(
        result=best or {}, passes=passes, stop_reason=stop_reason
    )
