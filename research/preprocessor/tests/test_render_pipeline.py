"""Tests for the render pipeline runner + graphlib order validation."""
from __future__ import annotations

import graphlib

import pytest

from stages.pipeline import (
    FuncStage,
    PipelineContext,
    run_render_pipeline,
    validate_stage_order,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_runs_stages_in_order_and_times_them() -> None:
    order: list[str] = []

    async def a(ctx: PipelineContext) -> None:
        order.append("a")
        ctx.data["a"] = 1

    async def b(ctx: PipelineContext) -> None:
        order.append("b")
        ctx.data["b"] = ctx.data["a"] + 1

    ctx = await run_render_pipeline([FuncStage("a", a), FuncStage("b", b)])
    assert order == ["a", "b"]
    assert ctx.data == {"a": 1, "b": 2}
    assert set(ctx.timings_ms) == {"a", "b"}


@pytest.mark.anyio
async def test_fail_fast_records_and_raises() -> None:
    async def boom(ctx: PipelineContext) -> None:
        raise ValueError("kaboom")

    ctx = PipelineContext()
    with pytest.raises(ValueError):
        await run_render_pipeline([FuncStage("boom", boom)], ctx, fail_fast=True)
    assert any("boom: kaboom" in e for e in ctx.errors)
    assert "boom" in ctx.timings_ms


@pytest.mark.anyio
async def test_no_fail_fast_continues() -> None:
    async def boom(ctx: PipelineContext) -> None:
        raise ValueError("x")

    async def ok(ctx: PipelineContext) -> None:
        ctx.data["ok"] = True

    ctx = await run_render_pipeline(
        [FuncStage("boom", boom), FuncStage("ok", ok)], fail_fast=False
    )
    assert ctx.data.get("ok") is True
    assert ctx.errors


def test_validate_stage_order_topo() -> None:
    order = validate_stage_order({"b": {"a"}, "c": {"b"}, "a": set()})
    assert order.index("a") < order.index("b") < order.index("c")


def test_validate_stage_order_cycle_raises() -> None:
    with pytest.raises(graphlib.CycleError):
        validate_stage_order({"a": {"b"}, "b": {"a"}})
