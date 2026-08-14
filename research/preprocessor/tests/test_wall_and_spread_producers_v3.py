"""Every declared element kind must have a producer that can fire."""

from __future__ import annotations

import inspect

from stages import materialize_render_contract_v3 as materializer
from contracts_v3.render_contract import Element
from typing import get_args


def _kinds_with_producers() -> set[str]:
    source = inspect.getsource(materializer)
    kinds: set[str] = set()
    for member in get_args(get_args(Element)[0]):
        if f"{member.__name__}(" in source:
            kinds.add(member.model_fields["kind"].default)
    return kinds


def test_no_element_kind_is_declared_without_a_producer() -> None:
    """A kind nothing constructs can never appear, however well it renders.

    evidence_gallery, distribution and composition_breakdown were each fully
    declared and drawn, and no code path ever built one.
    """
    declared = {
        member.model_fields["kind"].default
        for member in get_args(get_args(Element)[0])
    }
    # `group` and `divider` are structural and intentionally unproduced.
    structural = {"group", "divider"}
    missing = declared - _kinds_with_producers() - structural

    assert not missing, f"element kinds with no producer: {sorted(missing)}"


def test_percent_parts_over_one_hundred_are_not_one_whole() -> None:
    """Two shares that already exceed 100 are not parts of one thing."""

    class _Claim:
        def __init__(self, value: str) -> None:
            self.normalized_value = value

    assert materializer._within_one_whole([_Claim("30"), _Claim("50")])
    assert not materializer._within_one_whole([_Claim("70"), _Claim("60")])
    assert not materializer._within_one_whole([_Claim("keine Zahl")])
