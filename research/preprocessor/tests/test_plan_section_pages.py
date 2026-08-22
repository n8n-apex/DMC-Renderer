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


def _page(st_type: str, data: dict, *, components: list[str] | None = None) -> PlannedPage:
    return PlannedPage(
        slot=16, st_type=st_type, css_template="mechanism",
        components=list(components or []), has_cta=False, data=data,
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
# 7. case study (ST-07A): NOT split — one page by design
# --------------------------------------------------------------------------- #
def test_case_study_never_splits() -> None:
    """US-2026-08-19 (B3): a case study (ST-07A) is ONE page by design —
    whether it renders as an A3 Doppelseite or (now, after the mixed-size
    fix) an A4 single page. Splitting it would fabricate a second case page;
    the case study's own fill layout absorbs the copy. Regression: the old
    `page_format == "a3"` guard let the A4 single-page case studies fall
    through to _split_st07a (5 -> 7 pages in the apex deck)."""
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
    assert len(pages) == 1, f"a case study must stay ONE page; got {len(pages)}"


# --------------------------------------------------------------------------- #
# 8. plan_layout wiring: a heavy section expands in the plan
# --------------------------------------------------------------------------- #
def test_st05_splits_identity_and_proof() -> None:
    """US-609: the About's identity+proof exceed one sheet; the split keeps
    every block whole and exactly once."""
    from stages.plan_layout import plan_layout

    heavy = {
        "slot": 3, "type": "ST-05",
        "data": {
            "title": "Über APEX",
            "body": "B " * 500,
            "stats": [{"value": "100+", "label": "AI-Projekte"}],
            "partners": ["Frese", "Conesso"],
            "testimonials": [{"value": "x"}],
            "credibility_points": ["p1", "p2"],
        },
    }
    plan = plan_layout([heavy], components={}, page_count_target=1)
    assert plan.page_count == 2, f"expected 2 pages; got {plan.page_count}"
    roles = [p.continuation_role for p in plan.pages]
    assert roles == ["identity", "proof"], roles
    # every block appears exactly once across the two pages
    all_fields = [f for p in plan.pages for f in p.data]
    assert all_fields.count("body") == 1
    assert all_fields.count("testimonials") == 1


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


def test_st06_with_mechanism_component_gets_three_pages() -> None:
    """US-2026-08-22 (the user's p20 report): when the ST-06 section carries a
    generated mechanism diagram (an SVG component), the planner must emit a
    dedicated MECHANISM continuation page — the diagram gets its OWN page as
    the showcase, per the user's rule ("a device that can't be shown properly
    on the layout gets its own page"). Intro + mechanism + result = 3 pages,
    the SVG rides ONLY the mechanism page."""
    pages = split_section(_page(
        "ST-06", _st06_data(_n_steps(6)),
        components=['<svg viewBox="0 0 960 240" xmlns="http://www.w3.org/2000/svg"></svg>'],
    ))
    assert len(pages) == 3, f"expected intro/mechanism/result; got {len(pages)}"
    assert [p.continuation_role for p in pages] == ["intro", "mechanism", "result"]
    assert [p.continuation_index for p in pages] == [1, 2, 3]
    mech = pages[1]
    assert mech.components and "<svg" in mech.components[0], \
        "the mechanism diagram must ride its own page"
    assert all(not p.components for p in (pages[0], pages[2])), \
        "no other ST-06 page may carry the diagram (it would re-crowd that page)"


def test_st06_without_component_splits_two_pages() -> None:
    """An ST-06 heavy section with NO generated SVG stays at intro + result
    (no mechanism page — it would be an empty waste page)."""
    pages = split_section(_page("ST-06", _st06_data(_n_steps(6))))
    assert len(pages) == 2, f"expected intro/result; got {len(pages)}"
    assert [p.continuation_role for p in pages] == ["intro", "result"]
    assert [p.continuation_index for p in pages] == [1, 2]
