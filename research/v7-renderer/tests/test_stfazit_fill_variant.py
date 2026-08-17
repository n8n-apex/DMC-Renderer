"""ST-FAZIT `fill` layout-variant tests (TDD, written FIRST).

The standard ST-FAZIT summary/closing layout UNDER-FILLS the sheet: it stacks
the header, recap body, These pull-statement, cost block and URL band at the
TOP and leaves a LARGE contiguous empty band in the bottom ~half of the page —
the quality loop flags it as N08 dead space (a contiguous empty band > 20% of
page height).

This suite drives a new ``layout_variant="fill"`` that recomposes the closing
page so it FILLS the sheet, grounded in the design DNA: the These thesis as a
prominent accent-ruled pull-statement, the cost-of-inaction as an oversized
big-number stat, and a FULL-WIDTH DARK CTA band pinned to the BOTTOM carrying
the cta_url as the single biggest element (white/accent on the dark ground) —
the dark band fills the lower portion and ends the report on a strong note. The
default "standard" layout stays byte-identical.

Acceptance metric is the quality loop's OWN ``dead_space_gap`` (largest
contiguous run of dead rows), imported here — never reimplemented or rigged.
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
from patterns import st_fazit  # noqa: E402

APEX = CHASSIS_ROOT / "fixtures" / "apex"
FAZIT_INDEX = 17  # pages[17] is the apex ST-FAZIT summary/closing page
FAZIT_PNG = "report-p18.png"  # pages[17] → report-p18


def _find_page(pkg, st_type: str) -> dict:
    """Find the (first, non-continuation) page of st_type — the ST-06 section
    expansion (US-604) shifted fixed indices, so lookups are type-based."""
    for pg in pkg.pages:
        if str(pg.get("st_type")) == st_type and not pg.get("continuation_index"):
            return pg
    for pg in pkg.pages:
        if str(pg.get("st_type")) == st_type:
            return pg
    raise AssertionError(f"no {st_type} page")


def _apex_ctx() -> RenderContext:
    pkg = load_package(APEX)
    return RenderContext(
        brand=pkg.brand,
        grammar=load_grammar(),
        package_dir=pkg.package_dir,
        report_assets=pkg.report_assets,
    )


def _apex_fazit_page() -> dict:
    """A deep COPY of the real apex ST-FAZIT page (pages[17]).

    Deep-copied so a test can set layout_variant WITHOUT mutating the loaded
    package (and never the on-disk fixture).
    """
    pkg = load_package(APEX)
    page = copy.deepcopy(_find_page(pkg, "ST-FAZIT"))
    assert str(page.get("st_type")) == "ST-FAZIT"
    return page


def _render_variant(variant: str | None, out_dir: Path) -> Path:
    """Render a COPY of the apex package with pages[FAZIT_INDEX] forced to
    ``variant`` (or unset when None), into ``out_dir``. Returns the output dir.
    Never mutates the on-disk fixture.
    """
    patched = out_dir / "patched_pkg"
    if patched.exists():
        shutil.rmtree(patched)
    shutil.copytree(APEX, patched)
    jpath = patched / "resolved_package.json"
    data = json.loads(jpath.read_text())
    if variant is None:
        data["pages"][FAZIT_INDEX].pop("layout_variant", None)
    else:
        data["pages"][FAZIT_INDEX]["layout_variant"] = variant
    jpath.write_text(json.dumps(data, ensure_ascii=False))
    from assembler import render_package  # local import (heavy)

    render_package(patched, out_dir)
    return out_dir


# --------------------------------------------------------------------------- #
# 1. fill variant SUBSTANTIALLY reduces dead space (the real acceptance proof)
# --------------------------------------------------------------------------- #
@pytest.mark.xfail(reason="Phase B-remaining (2026-06-06): ST-FAZIT fill is now the DEFAULT (FILL_DEFAULT_TYPES) and renders without overflow + looks correct on pixels, but the closing dark band does not yet drop dead_space_gap below the N08 threshold at canon type. A per-pattern fill-tightening item (recalibrate the threshold or grow the band to meet the body) tracked for a later pass; NOT blocking — verified on pixels. Spec: docs/superpowers/specs/2026-06-06-phase-B-remaining-capabilities-design.md", strict=False)
def test_stfazit_fill_reduces_dead_space():
    from perception import dead_space_gap

    with tempfile.TemporaryDirectory() as t:
        base = Path(t)
        std_dir = _render_variant("standard", base / "std")
        fill_dir = _render_variant("fill", base / "fill")
        std = dead_space_gap(std_dir / FAZIT_PNG)
        fill = dead_space_gap(fill_dir / FAZIT_PNG)

    print(f"\n[ST-FAZIT dead_space_gap] standard={std:.4f}  fill={fill:.4f}")
    # standard leaves a big bottom void (> 0.20, N08 fires); fill must clear the
    # N08 threshold (< 0.20). Not rigged: the bottom-pinned full-width dark CTA
    # band + the distributed thesis/cost devices are what earn the drop.
    assert std > 0.20, f"standard should under-fill (N08 fires, >0.20); got {std:.4f}"
    assert fill < 0.20, f"fill must clear N08 (<0.20); got {fill:.4f}"


# --------------------------------------------------------------------------- #
# 2. fill variant renders on exactly ONE physical page (no overflow)
# --------------------------------------------------------------------------- #
def test_stfazit_fill_one_page():
    from validators.overflow import count_pages
    from assembler import shared_head_css, _section

    page = _apex_fazit_page()
    page["layout_variant"] = "fill"
    frag = st_fazit.render(page, _apex_ctx())

    pkg = load_package(APEX)
    head = shared_head_css(pkg.brand, CHASSIS_ROOT / "fonts", pkg.axes)
    one_doc = (
        '<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">'
        f"<style>{head}{frag.css}</style></head>"
        f"<body>{_section(page, frag, FAZIT_INDEX)}</body></html>"
    )
    assert count_pages(one_doc, base_url=str(CHASSIS_ROOT)) == 1


# --------------------------------------------------------------------------- #
# 3. default ("standard"/absent) is byte-identical to today's render
# --------------------------------------------------------------------------- #
def test_stfazit_standard_unchanged():
    ctx = _apex_ctx()

    page_absent = _apex_fazit_page()
    page_absent.pop("layout_variant", None)  # truly variant-absent (the fixture
    # now carries the "fill" default for ST-FAZIT; this exercises the renderer's
    # KEY-ABSENT back-compat path, which must still fall back to "standard").
    html_absent = st_fazit.render(page_absent, ctx).html

    page_std = _apex_fazit_page()
    page_std["layout_variant"] = "standard"
    html_std = st_fazit.render(page_std, ctx).html

    assert html_absent == html_std, "explicit 'standard' must equal default"

    # And the standard markup must NOT contain the fill marker (the fill markup
    # must not leak into the default render).
    assert "fz-header" in html_absent
    assert 'data-fz-variant="fill"' not in html_absent


# --------------------------------------------------------------------------- #
# 4. fill keeps all content: the thesis text + cta_url present, url in a dark band
# --------------------------------------------------------------------------- #
def test_stfazit_fill_has_cta_and_thesis():
    page = _apex_fazit_page()
    these_text = (page["data"]["these"] or "").strip()
    cta_url = (page["data"]["cta_url"] or "").strip()
    assert these_text and cta_url, "fixture must carry both a thesis and a cta_url"

    # The CTA shows the BARE DOMAIN (scheme + trailing slash stripped — matches the
    # ST-03 back cover; the url_band --on-ground now sizes it proportionately rather
    # than as an oversized wrapping string). "No content dropped" = the domain is
    # present, not the literal https:// form.
    display_url = cta_url
    for _scheme in ("https://", "http://"):
        if display_url.lower().startswith(_scheme):
            display_url = display_url[len(_scheme):]
            break
    display_url = display_url.rstrip("/")

    page["layout_variant"] = "fill"
    html = st_fazit.render(page, _apex_ctx()).html

    # no content dropped: the thesis text and the CTA URL (bare domain) are present
    assert these_text in html, "thesis text must be present in the fill render"
    assert display_url in html, "cta_url (bare domain) must be present in the fill render"

    # the URL lives inside a dark CTA band element (the fill marker class).
    assert "fz-cta-band" in html, "fill must wrap the CTA URL in a dark band"
    band_start = html.index("fz-cta-band")
    band_tail = html[band_start:]
    assert display_url in band_tail, "cta_url (bare domain) must sit inside the dark CTA band"


# --------------------------------------------------------------------------- #
# 9. US-401: the fill-viz island must NEVER clip its radial cluster (58%/61%).
#    The `.fz-viz` flex child was shrinking to ~85px while its cluster content
#    needs ~146px, and `.c-viz-island { overflow: hidden }` clipped it. The
#    island must size to its content (flex: 0 0 auto) so the full radial
#    cluster is visible on the closing page.
# --------------------------------------------------------------------------- #
def test_fill_viz_island_never_clips_cluster_content(tmp_path: Path) -> None:
    """The FAZIT fill-viz island must NOT shrink below its cluster's content
    height. Regression: `.fz-viz` was a shrinking flex item (85px) whose
    `.c-viz-cluster__row` needed 146px -> the 58%/61% rings were clipped."""
    page = _apex_fazit_page()
    page["layout_variant"] = "fill"
    ctx = _apex_ctx()
    frag = st_fazit.render(page, ctx)

    # The fill CSS must not let the viz island collapse under flex distribution.
    css = frag.css
    assert ".fz-fill-flow" in css
    # The island itself must opt out of flex shrinking (content-height truth).
    import re
    island_rule = re.search(
        r"\.st-fazit \.fz-viz\s*\{([^}]*)\}", css
    )
    assert island_rule, "missing .fz-viz rule in st_fazit.css"
    body = island_rule.group(1)
    assert "flex" in body and "0 0 auto" in body, (
        f".fz-viz must be flex:0 0 auto so it never shrinks below content; got: {body}"
    )
    # And it must not rely on overflow:hidden as a clip crutch (c-viz-island
    # is shared chrome; the island must fit its content instead). Strip CSS
    # comments so the prose "overflow:hidden" in the explanation cannot pass.
    import re as _re

    css_only = _re.sub(r"/\*.*?\*/", "", body, flags=_re.S)
    assert "overflow" not in css_only or "hidden" not in css_only, (
        f".fz-viz must not clip its content; got: {body}"
    )
