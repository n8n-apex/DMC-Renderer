"""US-604 — ST-06 two-page pilot: continuation pages are DELIBERATE compositions.

The ST-06 section now spans two physical pages (US-603): page 1 = intro +
early steps, page 2 = late steps + result. Each page must render as a FULL
composition — no half-empty step grid, no dead bottom band. The pattern and
template must be continuation-role-aware:
  - intro page: steps as a full-width row + an explicit "Fortsetzung" cue
  - result page: steps + the stat diagram + the recap, filling the sheet
  - the section's folio/identity is carried on both pages
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from package_loader import load_package  # noqa: E402
from patterns import st_06  # noqa: E402
from templating import get_env  # noqa: E402

APEX = ROOT / "fixtures" / "apex"


def _apex_ctx():
    from patterns.base import RenderContext
    from grammar_loader import load_grammar

    pkg = load_package(APEX)
    return RenderContext(
        brand=pkg.brand,
        grammar=load_grammar(),
        package_dir=pkg.package_dir,
        report_assets=pkg.report_assets,
    )


def _cont_page(role: str, steps: int = 3) -> dict:
    """A ST-06 continuation page like the planner produces."""
    return {
        "slot": 16,
        "st_type": "ST-06",
        "page_id": f"section.16.page.{1 if role == 'intro' else 2}",
        "section_id": "section.16",
        "continuation_index": 1 if role == "intro" else 2,
        "continuation_role": role,
        "section_page_count": 2,
        "data": {
            "title": "Das Framework" if role == "intro" else None,
            "body": ("Intro body text. " * 40) if role == "intro" else None,
            "steps": [
                {"title": f"Schritt {i}", "body": f"Body {i} " * 60}
                for i in range(1, steps + 1)
            ],
            "diagram": {"kind": "stat_callout", "figure": "30-50%",
                        "label": "im Schnitt"} if role == "result" else None,
            "ergebnis": (
                "Executives berichten, dass gezielt eingesetzte Automatisierung "
                "30-50% operativer Effizienzgewinne liefert." if role == "result"
                else None
            ),
        },
    }


def _render(page: dict) -> str:
    frag = st_06.render(page, _apex_ctx())
    return frag.html


def test_intro_page_renders_continuation_cue() -> None:
    html = _render(_cont_page("intro"))
    assert "mx-cont-cue" in html, (
        "intro continuation page must carry an explicit 'Fortsetzung' cue"
    )
    assert "Fortsetzung" in html or "Weiter" in html


def test_result_page_renders_recap_and_diagram() -> None:
    html = _render(_cont_page("result"))
    assert "mx-recap" in html, "result page must carry the recap panel"
    assert "stat_callout" in html or "30-50%" in html


def test_continuation_pages_are_full_width_step_rows() -> None:
    """3 steps on a continuation page must NOT use the half-empty 2-col grid."""
    html = _render(_cont_page("intro"))
    assert "mx-steps mx-steps--cont" in html or "mx-steps--cont" in html, (
        "continuation pages must use the continuation step-row layout"
    )


def _page_of(pkg, st_type: str, role=None) -> dict:
    """The page with `st_type`; when `role` is given it must also match
    continuation_role (US-604: ST-02/ST-05/ST-06/ST-FAZIT span continuation
    pages). With role=None a NON-continuation page is preferred, then the
    first page of that type."""
    for pg in pkg.pages:
        if str(pg.get("st_type")) != st_type:
            continue
        if role is None:
            if not pg.get("continuation_index"):
                return pg
        elif pg.get("continuation_role") == role:
            return pg
    for pg in pkg.pages:
        if str(pg.get("st_type")) == st_type:
            return pg
    raise AssertionError(f"no {st_type} page (role={role!r}) in the apex fixture")


def test_single_page_st06_unchanged() -> None:
    """A non-continuation ST-06 page keeps the exact legacy markup."""
    pkg = load_package(APEX)
    page = copy.deepcopy(_page_of(pkg, "ST-06", role="intro"))
    assert str(page.get("st_type")) == "ST-06"
    # strip identity — a single-page ST-06 has none
    for k in ("page_id", "section_id", "continuation_index",
              "continuation_role", "section_page_count"):
        page.pop(k, None)
    html = st_06.render(page, _apex_ctx()).html
    assert "mx-cont-cue" not in html
    assert "mx-steps--cont" not in html


def test_continuation_cue_css_exists() -> None:
    """The cue + continuation step-row styles are defined in st_06.css."""
    css = (ROOT / "styles" / "st_06.css").read_text(encoding="utf-8")
    assert ".st-06 .mx-cont-cue" in css
    assert ".st-06 .mx-steps--cont" in css
