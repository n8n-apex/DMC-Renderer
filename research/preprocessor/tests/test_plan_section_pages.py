"""US-603 — section pagination planner (semantic split).

A section whose copy exceeds its per-ST capacity is split at SEMANTIC
boundaries into multiple physical-page plans, each carrying US-602 identity
(section_id / page_id / continuation_index / continuation_role /
section_page_count). Guarantees:
  - short section -> exactly ONE planned page (no identity, back-compat)
  - heavy section -> 2+ planned pages at semantic boundaries
  - every source block appears EXACTLY ONCE across the pages
  - continuations are contiguous (never interleaved with another section)
  - no fabrication: the split only RE-DISTRIBUTES the section's own fields
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research" / "preprocessor"))

from stages.plan_layout import PlannedPage  # noqa: E402
from stages.plan_section_pages import split_section  # noqa: E402


def _page(st_type: str, data: dict) -> PlannedPage:
    return PlannedPage(
        slot=16, st_type=st_type, css_template="mechanism",
        components=[], has_cta=False, data=data,
    )


def _st06_data(steps: list[dict], ergebnis: str = "Ergebnis text", body: str = "Intro text") -> dict:
    return {"title": "Framework", "body": body, "steps": steps, "ergebnis": ergebnis}


def _n_steps(n: int, words: int = 60) -> list[dict]:
    """n steps, each `words` words long — big enough to exceed the budget."""
    return [{"title": f"Schritt {i}", "body": f"Body {i} " * words} for i in range(1, n + 1)]


# --------------------------------------------------------------------------- #
# 1. short section -> one page, no identity
# --------------------------------------------------------------------------- #
def test_short_section_stays_single_page() -> None:
    pages = split_section(_page("ST-06", _st06_data(_n_steps(2))))
    assert len(pages) == 1
    assert pages[0].section_id is None
    assert pages[0].continuation_index is None


# --------------------------------------------------------------------------- #
# 2. heavy section -> 2+ pages with identity + roles
# --------------------------------------------------------------------------- #
def test_heavy_section_splits_with_identity() -> None:
    # 6 steps at 30 words each >> the ST-06 1400-char budget
    pages = split_section(_page("ST-06", _st06_data(_n_steps(6))))
    assert len(pages) >= 2, f"expected a split; got {len(pages)}"
    for i, p in enumerate(pages, start=1):
        assert p.section_id == "section.16", p.section_id
        assert p.page_id == f"section.16.page.{i}", p.page_id
        assert p.continuation_index == i
        assert p.continuation_role in ("intro", "mechanism", "result", "proof", "close")
        assert p.section_page_count == len(pages)


# --------------------------------------------------------------------------- #
# 3. every source block appears exactly once (no duplication, no loss)
# --------------------------------------------------------------------------- #
def test_split_preserves_all_source_blocks_exactly_once() -> None:
    data = _st06_data(_n_steps(6))
    pages = split_section(_page("ST-06", data))

    all_titles = [t for p in pages for t in p.data.get("steps", [])]
    all_bodies = [s.get("body", "") for s in all_titles]
    assert len(all_bodies) == 6, f"lost/duplicated steps: {len(all_bodies)}"
    for step in data["steps"]:
        assert step["body"] in all_bodies, f"missing step body: {step['body'][:20]}"
    assert len(set(all_bodies)) == 6, "duplicated step body across pages"


# --------------------------------------------------------------------------- #
# 4. continuations are contiguous (same section, adjacent)
# --------------------------------------------------------------------------- #
def test_split_continuations_are_contiguous() -> None:
    pages = split_section(_page("ST-06", _st06_data(_n_steps(6))))
    assert len(pages) >= 2
    for i, p in enumerate(pages):
        assert p.section_id == "section.16"
        if i > 0:
            assert pages[i - 1].section_id == p.section_id


# --------------------------------------------------------------------------- #
# 5. unknown ST / no split rule -> single page (honest, no forced split)
# --------------------------------------------------------------------------- #
def test_unsupported_st_type_stays_single() -> None:
    pages = split_section(_page("ST-01", {"title": "Cover", "subtitle": "x" * 2000}))
    assert len(pages) == 1


# --------------------------------------------------------------------------- #
# 6. split boundaries are SEMANTIC (first page has intro/mechanism, not a
#    mid-sentence slice)
# --------------------------------------------------------------------------- #
def test_split_boundaries_semantic() -> None:
    data = _st06_data(_n_steps(6))
    pages = split_section(_page("ST-06", data))
    assert len(pages) >= 2
    # every page's steps keep whole title/body pairs
    for p in pages:
        for s in p.data.get("steps", []):
            assert s["title"] and s["body"]


# --------------------------------------------------------------------------- #
# 7. case study (ST-07A) semantic split: narrative blocks stay whole
# --------------------------------------------------------------------------- #
def test_case_study_split_keeps_blocks_whole() -> None:
    data = {
        "fallstudie_number": 1,
        "kurzportraet": "Portrait text " * 40,
        "ausgangsproblem": "Problem text " * 40,
        "loesung": "Loesung text " * 40,
        "ergebnis_text": "Ergebnis text " * 40,
        "ergebnis_metrics": [{"value": "30 min -> 2 min", "label": "Onboarding"}],
        "pullquote": {"text": "Quote text", "attribution": "Client"},
        "kunde": {"name": "Client"},
        "viz": [],
    }
    pages = split_section(_page("ST-07A", data))
    assert len(pages) >= 2
    # each narrative block that EXISTS in the source appears on exactly one page
    from stages.plan_section_pages import _COPY_FIELDS_BY_ST

    for field in _COPY_FIELDS_BY_ST["ST-07A"]:
        if not data.get(field):
            continue  # absent from the source -> nothing to preserve
        owners = [p for p in pages if p.data.get(field)]
        assert len(owners) == 1, (
            f"field {field} must appear on exactly one page; got {len(owners)}"
        )


# --------------------------------------------------------------------------- #
# 8. plan_layout wiring: a heavy section expands in the plan
# --------------------------------------------------------------------------- #
def test_plan_layout_expands_heavy_section() -> None:
    from stages.plan_layout import plan_layout

    heavy = {
        "slot": 16, "type": "ST-06",
        "data": {
            "title": "Framework",
            "body": "Intro " * 50,
            "steps": [{"title": f"S{i}", "body": f"B{i} " * 80} for i in range(6)],
            "ergebnis": "Result " * 50,
        },
    }
    plan = plan_layout([heavy], components={}, page_count_target=1)
    assert plan.page_count >= 2, f"expected expansion; got {plan.page_count}"
    ids = {p.section_id for p in plan.pages}
    assert ids == {"section.16"}
    assert [p.continuation_index for p in plan.pages] == [1, 2]
    assert [p.continuation_role for p in plan.pages] == ["intro", "result"]
