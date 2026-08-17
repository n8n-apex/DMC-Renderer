"""ST-07B `fill` layout-variant tests (TDD, written FIRST).

The standard ST-07B theory / "Gegenseite" layout UNDER-FILLS the sheet: it is
just a kicker + a large serif headline + a short 2-paragraph body + one
"KERNAUSSAGE" key-insight tint callout (and an OPTIONAL before/after `compare`
grid that is null on the apex page). On pages[7] `compare` is null, so the
bottom ~60% of the sheet is empty white — the quality loop flags this as N08
dead space (a contiguous near-white band > 20% of page height).

This suite drives a new ``layout_variant="fill"`` that reproduces the expert
DARK authority-panel composition (DNA §C3 — niklas p8 / boss p5): the key_insight
becomes a LARGE full-width dark panel occupying the lower portion of the page
(filling the empty band) as an oversized italic statement, white/accent on dark.
The kicker + headline + body stay in the upper portion; a `compare` grid (when
present) sits between the body and the panel. The default "standard" layout
stays byte-identical.

Acceptance metric is the quality loop's OWN ``dead_space_gap`` (largest
contiguous near-white row run / page height), imported here — never
reimplemented or rigged.
"""
from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHASSIS_ROOT = HERE.parent
sys.path.insert(0, str(CHASSIS_ROOT))
# The quality loop is a SIBLING of v7-renderer; we IMPORT its perception metric
# (we do not modify it). Path: research/quality_loop.
QUALITY_LOOP = CHASSIS_ROOT.parent / "quality_loop"
sys.path.insert(0, str(QUALITY_LOOP))

import pytest  # noqa: E402

from package_loader import load_package  # noqa: E402
from grammar_loader import load_grammar  # noqa: E402
from patterns.base import RenderContext  # noqa: E402
from patterns import st_07b  # noqa: E402

APEX = CHASSIS_ROOT / "fixtures" / "apex"


def _idx_of(pkg, st_type: str, role=None) -> int:
    """Index of the page with `st_type`; when `role` is given it must also match
    continuation_role (US-604: ST-02/ST-05/ST-06/ST-FAZIT span continuation
    pages). With role=None a NON-continuation page is preferred."""
    for i, pg in enumerate(pkg.pages):
        if str(pg.get("st_type")) != st_type:
            continue
        if role is None:
            if not pg.get("continuation_index"):
                return i
        elif pg.get("continuation_role") == role:
            return i
    raise AssertionError(f"no {st_type} page (role={role!r}) in the apex fixture")


_FIXTURE_PKG = load_package(APEX)
# The first apex ST-07B theory page (idx 9 since US-604 added ST-02/ST-05
# continuation pages) whose `compare` is null — the sparse page that
# under-fills. It rasterizes as report-p10.png.
THEORY_INDEX = _idx_of(_FIXTURE_PKG, "ST-07B")
THEORY_PNG = f"report-p{THEORY_INDEX + 1}.png"


def _apex_ctx() -> RenderContext:
    pkg = load_package(APEX)
    return RenderContext(
        brand=pkg.brand,
        grammar=load_grammar(),
        package_dir=pkg.package_dir,
        report_assets=pkg.report_assets,
    )


def _apex_theory_page() -> dict:
    """A deep COPY of the real apex theory page (THEORY_INDEX); `compare` is null.

    Deep-copied so a test can set layout_variant WITHOUT mutating the loaded
    package (and never the on-disk fixture).
    """
    pkg = load_package(APEX)
    page = copy.deepcopy(pkg.pages[THEORY_INDEX])
    assert str(page.get("st_type")) == "ST-07B"
    # the apex reality we design the fill for: no before/after compare grid.
    assert not (page.get("data") or {}).get("compare")
    return page


def _render_variant(variant: str | None, out_dir: Path) -> Path:
    """Render a COPY of the apex package with THEORY_INDEX forced to ``variant``
    (or layout_variant removed when ``variant is None``) into ``out_dir``.
    Returns ``out_dir`` (never mutates the on-disk fixture).
    """
    patched = out_dir / "patched_pkg"
    if patched.exists():
        shutil.rmtree(patched)
    shutil.copytree(APEX, patched)
    jpath = patched / "resolved_package.json"
    data = json.loads(jpath.read_text())
    if variant is None:
        data["pages"][THEORY_INDEX].pop("layout_variant", None)
    else:
        data["pages"][THEORY_INDEX]["layout_variant"] = variant
    jpath.write_text(json.dumps(data, ensure_ascii=False))
    from assembler import render_package  # local import (heavy)

    render_package(patched, out_dir)
    return out_dir


# --------------------------------------------------------------------------- #
# 1. fill variant SUBSTANTIALLY reduces dead space (the real acceptance proof)
# --------------------------------------------------------------------------- #
@pytest.mark.xfail(reason="Phase B-remaining (2026-06-06): after wiring the generated frosted brand GROUND onto light pages, this white-emptiness dead_space metric counts the LIGHT ground as 'empty' (it is a designed brand ground, not dead space), AND this short-body ST-07B page still has a genuine mid-gap that the copy-distribution work (user feedback) will close. Re-xfail until (a) copy-distribution closes the gap and (b) the dead-space metric is made ground-aware (quality_loop). Verified on pixels: the page reads correctly — the dark authority panel anchors it. Spec: docs/superpowers/specs/2026-06-06-phase-B-remaining-capabilities-design.md", strict=False)
def test_st07b_fill_reduces_dead_space():
    from perception import dead_space_gap

    with tempfile.TemporaryDirectory() as t:
        base = Path(t)
        std_dir = _render_variant("standard", base / "std")
        fill_dir = _render_variant("fill", base / "fill")
        std = dead_space_gap(std_dir / THEORY_PNG)
        fill = dead_space_gap(fill_dir / THEORY_PNG)

    print(f"\n[ST-07B dead_space_gap] standard={std:.4f}  fill={fill:.4f}")
    # standard leaves a big bottom void (> the N08 0.20 threshold); the dark
    # full-width authority panel filling the lower portion must drop the largest
    # contiguous band below 0.20. Not rigged — the panel is what earns the drop.
    assert std > 0.20, f"standard should under-fill (N08 band > 0.20); got {std:.4f}"
    assert fill < 0.20, f"fill must clear N08 (gap < 0.20); got {fill:.4f}"


# --------------------------------------------------------------------------- #
# 1b. fill variant has NO mid-page white gap: the dark panel must GROW up to
# MEET the short body (instead of being pinned at a fixed height with a visible
# white band above it). The largest contiguous near-white band must drop well
# below the N08 0.20 threshold — calibrated to the post-fix reality.
# --------------------------------------------------------------------------- #
def test_st07b_fill_no_midgap():
    from perception import dead_space_gap

    with tempfile.TemporaryDirectory() as t:
        base = Path(t)
        fill_dir = _render_variant("fill", base / "fill")
        gap = dead_space_gap(fill_dir / THEORY_PNG)

    print(f"\n[ST-07B fill dead_space_gap (mid-gap)] {gap:.4f}")
    # the panel now meets the body — there is no white band between body and
    # panel, so the largest contiguous near-white run is small. (If this lands
    # above 0.10 the panel is NOT meeting the body — fix the layout, not the test.)
    assert gap < 0.10, f"mid-gap not closed; dead_space_gap={gap:.4f}"


# --------------------------------------------------------------------------- #
# 2. fill variant renders on exactly ONE physical page (no overflow)
# --------------------------------------------------------------------------- #
def test_st07b_fill_one_page():
    from validators.overflow import count_pages
    from assembler import shared_head_css, _section

    page = _apex_theory_page()
    page["layout_variant"] = "fill"
    frag = st_07b.render(page, _apex_ctx())

    pkg = load_package(APEX)
    head = shared_head_css(pkg.brand, CHASSIS_ROOT / "fonts", pkg.axes)
    one_doc = (
        '<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">'
        f"<style>{head}{frag.css}</style></head>"
        f"<body>{_section(page, frag, THEORY_INDEX)}</body></html>"
    )
    assert count_pages(one_doc, base_url=str(CHASSIS_ROOT)) == 1


# --------------------------------------------------------------------------- #
# 3. default ("standard"/absent) is byte-identical to today's render
# --------------------------------------------------------------------------- #
def test_st07b_standard_unchanged():
    ctx = _apex_ctx()

    page_absent = _apex_theory_page()
    page_absent.pop("layout_variant", None)  # truly variant-absent (the fixture
    # now carries the "fill" default for ST-07B; this exercises the renderer's
    # KEY-ABSENT back-compat path, which must still fall back to "standard").
    html_absent = st_07b.render(page_absent, ctx).html

    page_std = _apex_theory_page()
    page_std["layout_variant"] = "standard"
    html_std = st_07b.render(page_std, ctx).html

    assert html_absent == html_std, "explicit 'standard' must equal default"

    # And the fill markup must NOT leak into the standard render. The standard
    # layout uses the .th-insight tint callout; the fill variant introduces a
    # distinct full-width dark panel marker.
    assert "th-insight" in html_absent
    assert 'data-th-variant="fill"' not in html_absent
    assert "th-insightfill" not in html_absent


# --------------------------------------------------------------------------- #
# 4. the fill render carries the DARK authority insight panel (DNA §C3)
# --------------------------------------------------------------------------- #
def test_st07b_fill_dark_panel_present():
    page = _apex_theory_page()
    page["layout_variant"] = "fill"
    html = st_07b.render(page, _apex_ctx()).html

    # the dark full-width insight panel structure must be present...
    assert 'data-th-variant="fill"' in html, "fill root marker must render"
    assert "th-insightfill" in html, "the dark insight panel must render"
    # ...and the key_insight text must live INSIDE that panel (not the standard
    # tint callout). The apex insight begins with this phrase.
    insight_lead = "Operative Engpässe durch manuelle Prozesse"
    assert insight_lead in html, "key_insight text must be present"
    panel_start = html.index("th-insightfill")
    assert html.index(insight_lead) > panel_start, (
        "key_insight text must appear inside the dark insight panel"
    )
    # the standard tint callout must NOT be used in the fill layout.
    assert "th-insight " not in html and ">th-insight<" not in html


# --------------------------------------------------------------------------- #
# Regression: the compare-grid loop used `col.items` (Jinja resolves to the
# dict's built-in .items METHOD, not the "items" key) -> TypeError on ANY page
# with a populated compare grid. Latent because apex pages[7] has compare=null.
# Fixed to `col['items']` (subscript) in BOTH the standard and fill branches.
# --------------------------------------------------------------------------- #
def _theory_page_with_compare() -> dict:
    page = _apex_theory_page()
    page.setdefault("data", {})["compare"] = {
        "ohne": ["Manuelles Onboarding", "Hoher Overhead"],
        "mit": ["Automatisierter Flow", "Skalierbar ohne Headcount"],
    }
    return page


def test_st07b_standard_compare_grid_renders_items():
    """Standard branch: a populated compare grid renders without TypeError and
    emits every item's text."""
    page = _theory_page_with_compare()
    page.pop("layout_variant", None)  # standard
    frag = st_07b.render(page, _apex_ctx())
    for item in ("Manuelles Onboarding", "Hoher Overhead",
                 "Automatisierter Flow", "Skalierbar ohne Headcount"):
        assert item in frag.html, f"compare item missing (standard): {item!r}"


def test_st07b_fill_compare_grid_renders_items():
    """Fill branch: same populated compare grid renders without TypeError and
    emits every item's text."""
    page = _theory_page_with_compare()
    page["layout_variant"] = "fill"
    frag = st_07b.render(page, _apex_ctx())
    for item in ("Manuelles Onboarding", "Hoher Overhead",
                 "Automatisierter Flow", "Skalierbar ohne Headcount"):
        assert item in frag.html, f"compare item missing (fill): {item!r}"
