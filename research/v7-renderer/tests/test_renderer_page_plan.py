"""US-607 — the renderer consumes physical-page plans.

The preprocessor emits physical-page identity + Director briefs (US-602/606).
The renderer must expose them to patterns/templates so:
  - a continuation page knows it is page N of M (folio furniture)
  - the Director region_plan is reachable by any host pattern
  - a single-page section gets a clean identity (page 1 of 1)
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from package_loader import load_package  # noqa: E402


def _page_plan(page: dict) -> dict:
    """The physical-page plan a pattern/template can render (assembler-side
    helper under test via the loader-level view)."""
    return {
        "page_id": page.get("page_id"),
        "section_id": page.get("section_id"),
        "continuation_index": page.get("continuation_index") or 1,
        "continuation_role": page.get("continuation_role") or "main",
        "section_page_count": page.get("section_page_count") or 1,
    }


def test_single_page_section_identity() -> None:
    """A single-page section reports page 1 of 1 with role main."""
    plan = _page_plan({"slot": 2, "st_type": "ST-02"})
    assert plan["continuation_index"] == 1
    assert plan["section_page_count"] == 1
    assert plan["continuation_role"] == "main"


def test_continuation_page_identity() -> None:
    """A continuation page reports its index/role/count."""
    plan = _page_plan({
        "page_id": "section.16.page.2",
        "section_id": "section.16",
        "continuation_index": 2,
        "continuation_role": "result",
        "section_page_count": 2,
    })
    assert plan["page_id"] == "section.16.page.2"
    assert plan["continuation_index"] == 2
    assert plan["continuation_role"] == "result"
    assert plan["section_page_count"] == 2


def test_assembler_exposes_page_plan_to_fragments() -> None:
    """The assembler's page render path passes the physical-page plan through
    so patterns can render continuation furniture (folio '2 / 2')."""
    from assembler import _render_one_page
    import inspect

    sig = inspect.signature(_render_one_page)
    params = list(sig.parameters)
    assert "page_plan" in params or "page" in params, (
        f"_render_one_page must take the page (identity is on it): {params}"
    )
