"""Render pipeline runner — a thin sequential orchestrator mirroring
stages/onboard/pipeline.py. Each stage is a small object with a `name`
and an async `run(ctx)`; the runner times each (mirroring the onboard
`_mark`) and applies one error policy, so stages stay pure and wiring
stays declarative. graphlib validates the §4 dependency graph once.

Built as the backbone Phases 2-4 plug into; not wired into /render until
the full graph exists (Phase 4 / PRD Unit 8). No client literal here.
"""
from __future__ import annotations

import graphlib
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional, Protocol


@dataclass
class PipelineContext:
    """Mutable carrier passed through stages. Heavy in-memory objects live
    here (dataclasses, never serialized); only assemble_package serializes.
    """

    data: dict[str, Any] = field(default_factory=dict)
    timings_ms: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class Stage(Protocol):
    name: str

    async def run(self, ctx: PipelineContext) -> None: ...


@dataclass
class FuncStage:
    """Adapt a plain async function into a Stage."""

    name: str
    fn: Callable[[PipelineContext], Awaitable[None]]

    async def run(self, ctx: PipelineContext) -> None:
        await self.fn(ctx)


async def run_render_pipeline(
    stages,
    ctx: Optional[PipelineContext] = None,
    *,
    logger=None,
    fail_fast: bool = True,
) -> PipelineContext:
    """Run stages in order, recording per-stage wall time. On a stage
    error: record it (and log if a logger is given); re-raise when
    fail_fast, else continue to the next stage.
    """
    if ctx is None:
        ctx = PipelineContext()
    for stage in stages:
        t = time.perf_counter()
        try:
            await stage.run(ctx)
        except Exception as exc:
            ctx.errors.append(f"{stage.name}: {exc!s}")
            if logger is not None:
                logger.error("stage_failed", stage=stage.name, error=str(exc))
            if fail_fast:
                ctx.timings_ms[stage.name] = int((time.perf_counter() - t) * 1000)
                raise
        ctx.timings_ms[stage.name] = int((time.perf_counter() - t) * 1000)
    return ctx


def validate_stage_order(deps: dict[str, set[str]]) -> list[str]:
    """Return one valid topological order for a {node: {prereqs}} graph;
    raise graphlib.CycleError on a cycle. Validates the §4 graph at startup.
    """
    return list(graphlib.TopologicalSorter(deps).static_order())
