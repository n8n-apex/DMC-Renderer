"""US-602 — logical-section and physical-page identity.

A report section must be able to own MULTIPLE physical pages (user directive:
"use as many pages as it requires"). Today the package is a flat pages[] list
where one source slot == one sheet — that is the root cause of the p18->p19
contamination (a section has no continuation identity, so its overflow bleeds
into the next section's page).

This story adds the identity SEAM (back-compatible, optional fields):
  - PlannedPage gains section_id / page_id / continuation_index /
    continuation_role / section_page_count
  - the package page dict carries them when set
  - ResolvedPageV2 accepts them
  - default behaviour is unchanged (None -> fields omitted -> exactly today's
    flat one-slot-one-page package)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research" / "preprocessor"))

from stages.plan_layout import LayoutPlan, PlannedPage, plan_layout  # noqa: E402


def _page(slot: int, st_type: str, **extra) -> dict:
    p = {"slot": slot, "type": st_type, "data": {"title": f"slot {slot}"}}
    p.update(extra)
    return p


def _plan(pages) -> LayoutPlan:
    return plan_layout(pages, components={}, page_count_target=len(pages))


# --------------------------------------------------------------------------- #
# 1. PlannedPage identity fields exist and default to None (back-compat)
# --------------------------------------------------------------------------- #
def test_planned_page_identity_fields_default_none() -> None:
    pp = PlannedPage(slot=1, st_type="ST-01", css_template="st_01",
                     components=[], has_cta=False, data={})
    assert pp.section_id is None
    assert pp.page_id is None
    assert pp.continuation_index is None
    assert pp.continuation_role is None
    assert pp.section_page_count is None


def test_planned_page_identity_fields_constructible() -> None:
    pp = PlannedPage(
        slot=16, st_type="ST-06", css_template="st_06", components=[],
        has_cta=False, data={},
        section_id="section.16",
        page_id="section.16.page.2",
        continuation_index=2,
        continuation_role="result",
        section_page_count=2,
    )
    assert pp.section_id == "section.16"
    assert pp.page_id == "section.16.page.2"
    assert pp.continuation_index == 2
    assert pp.continuation_role == "result"
    assert pp.section_page_count == 2


# --------------------------------------------------------------------------- #
# 2. A single-page section (default) has NO identity written (back-compat)
# --------------------------------------------------------------------------- #
def test_plan_layout_omits_identity_by_default() -> None:
    plan = _plan([_page(1, "ST-01"), _page(2, "ST-02"), _page(3, "ST-03")])
    for pp in plan.pages:
        assert pp.section_id is None
        assert pp.page_id is None


# --------------------------------------------------------------------------- #
# 3. Package serialisation carries identity when present
# --------------------------------------------------------------------------- #
def test_assemble_package_writes_identity_fields() -> None:
    """The package page dict must carry the identity fields when the plan
    sets them (this is the renderer's contract input)."""
    from stages.assemble_package import _write_page_identity

    pp = PlannedPage(
        slot=16, st_type="ST-06", css_template="st_06", components=[],
        has_cta=False, data={"title": "x"},
        section_id="section.16",
        page_id="section.16.page.2",
        continuation_index=2,
        continuation_role="result",
        section_page_count=2,
    )
    page_dict: dict = {"slot": 16, "st_type": "ST-06"}
    _write_page_identity(page_dict, pp)
    assert page_dict["section_id"] == "section.16"
    assert page_dict["page_id"] == "section.16.page.2"
    assert page_dict["continuation_index"] == 2
    assert page_dict["continuation_role"] == "result"
    assert page_dict["section_page_count"] == 2


def test_write_page_identity_omits_when_none() -> None:
    """A single-page section writes NO identity keys (back-compat)."""
    from stages.assemble_package import _write_page_identity

    pp = PlannedPage(slot=16, st_type="ST-06", css_template="st_06",
                     components=[], has_cta=False, data={})
    page_dict: dict = {"slot": 16, "st_type": "ST-06"}
    _write_page_identity(page_dict, pp)
    for key in ("section_id", "page_id", "continuation_index",
                "continuation_role", "section_page_count"):
        assert key not in page_dict


# --------------------------------------------------------------------------- #
# 4. ResolvedPageV2 accepts the identity fields
# --------------------------------------------------------------------------- #
def test_resolved_page_v2_accepts_identity_fields() -> None:
    from models_package import ResolvedPageV2

    rp = ResolvedPageV2(
        slot=16, st_type="ST-06",
        section_id="section.16",
        page_id="section.16.page.2",
        continuation_index=2,
        continuation_role="result",
        section_page_count=2,
    )
    assert rp.section_id == "section.16"
    assert rp.continuation_role == "result"


# --------------------------------------------------------------------------- #
# 5. Package identity keys appear ONLY on expanded sections
# --------------------------------------------------------------------------- #
def test_default_package_pages_have_no_identity_keys() -> None:
    """Only genuinely expanded sections (ST-06 is over capacity) carry identity;
    every OTHER page has none (back-compat with the flat package)."""
    pkg = json.loads(
        (Path(__file__).resolve().parent.parent.parent
         / "v7-renderer" / "fixtures" / "apex" / "resolved_package.json")
        .read_text(encoding="utf-8")
    )
    identity_slots = set()
    for page in pkg.get("pages", []):
        if any(k in page for k in ("section_id", "page_id",
                                   "continuation_index",
                                   "continuation_role", "section_page_count")):
            identity_slots.add(page.get("slot"))
            assert page.get("continuation_index") is not None
    # exactly the ST-06 section (slot 16) is expanded in the apex fixture
    assert identity_slots == {16}, (
        f"expected only slot 16 (ST-06) expanded; got {identity_slots}"
    )
