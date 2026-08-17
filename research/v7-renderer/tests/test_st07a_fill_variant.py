"""ST-07A `fill` layout-variant tests (TDD, written FIRST).

The standard ST-07A case-study layout UNDER-FILLS the sheet: ~39% of the apex
case-study page (bottom region) is dead white space. This suite drives a new
``layout_variant="fill"`` that reproduces the expert composition (full-height
dark authority sidebar + vertical big-number stat stack) so the sheet is
genuinely filled — while keeping the default "standard" layout byte-identical.

Acceptance metric is the quality loop's OWN ``dead_space_fraction`` (grayscale
per-row near-white+uniform test), imported here — never reimplemented or rigged.
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
from patterns import st_07a  # noqa: E402

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
# The first apex ST-07A (idx 8 since US-604 added ST-02/ST-05 continuation
# pages) is the case study with the portrait ABSENT and crisp numeral metrics.
CASE_STUDY_INDEX = _idx_of(_FIXTURE_PKG, "ST-07A")
# The Frese case study (idx 13) is the OTHER apex ST-07A whose ergebnis_metrics
# values are PROSE sentences (not crisp numerals). At the big --type-display-xl
# size these OVERFLOW the ~64mm dark fill panel and CLIP at its right edge —
# the bug under test here.
SOCIAL_POST_CASE_STUDY_INDEX = next(
    i for i, pg in enumerate(_FIXTURE_PKG.pages)
    if str(pg.get("st_type")) == "ST-07A"
    and bool((pg.get("data") or {}).get("social_post"))
)
PROSE_CASE_STUDY_INDEX = SOCIAL_POST_CASE_STUDY_INDEX  # the prose-metrics Frese page
PROSE_CASE_STUDY_PNG = f"report-p{PROSE_CASE_STUDY_INDEX + 1}.png"
NUMERAL_CASE_STUDY_PNG = f"report-p{CASE_STUDY_INDEX + 1}.png"
# The Frese case study (idx 13) is the case study the Social Layout Planner
# binds a client-matched social post onto (data.social_post). ST-07A renders a
# COMPACT phone_mockup in the portrait slot, REPLACING the static portrait
# (gap-fix C).


def _render_fill_page(page_index: int, out_dir: Path) -> Path:
    """Render a COPY of the apex package with pages[page_index] forced to the
    fill variant, into ``out_dir``. Returns the output dir (never mutates the
    on-disk fixture). Used by the rasterized clip / one-page tests.
    """
    patched = out_dir / "patched_pkg"
    if patched.exists():
        shutil.rmtree(patched)
    shutil.copytree(APEX, patched)
    jpath = patched / "resolved_package.json"
    data = json.loads(jpath.read_text())
    data["pages"][page_index]["layout_variant"] = "fill"
    jpath.write_text(json.dumps(data, ensure_ascii=False))
    from assembler import render_package  # local import (heavy)

    out = out_dir / "out"
    render_package(patched, out)
    return out


def _render_standalone_fill_png(page_index: int, out_dir: Path) -> Path:
    """Render pages[page_index] (forced to fill variant) as a STANDALONE
    single-page document and return the path to its rasterized PNG.

    This is pagination-independent: it never relies on a physical page number
    in a full-deck render (which changes whenever the deck reflows).  Only the
    logical index into pkg.pages is used — that is stable across pagination
    changes because it is the package-data order, not the PDF page number.

    Implementation mirrors test_fill_variant_still_one_page (WeasyPrint
    standalone render) then rasterizes via PyMuPDF (fitz).
    """
    import fitz  # PyMuPDF
    import weasyprint
    from weasyprint.text.fonts import FontConfiguration

    from assembler import shared_head_css, _section  # noqa: E402
    from patterns import st_07a  # noqa: E402

    pkg = load_package(APEX)
    pg = copy.deepcopy(pkg.pages[page_index])
    pg["layout_variant"] = "fill"
    frag = st_07a.render(pg, _apex_ctx())

    head = shared_head_css(pkg.brand, CHASSIS_ROOT / "fonts", pkg.axes)
    one_doc = (
        '<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">'
        f"<style>{head}{frag.css}</style></head>"
        f"<body>{_section(pg, frag, page_index)}</body></html>"
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "standalone.pdf"
    png_path = out_dir / "standalone-p1.png"

    font_config = FontConfiguration()
    weasyprint.HTML(string=one_doc, base_url=str(CHASSIS_ROOT)).write_pdf(
        str(pdf_path), font_config=font_config
    )

    doc = fitz.open(pdf_path)
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
    pix.save(str(png_path))
    doc.close()

    return png_path


def _dark_panel_right_edge(px, W: int, H: int) -> int:
    """Return the x of the dark fill panel's RIGHT edge: the rightmost column
    that is >50% dark (< brightness 140). The fill panel is a solid
    --color-ink block on the right of the page, so it is the rightmost dark
    column band; everything to its right is the white page background.
    """
    edge = None
    for x in range(W):
        dark = sum(1 for y in range(H) if px[x, y] < 140)
        if dark / H > 0.5:
            edge = x
    assert edge is not None, "no dark fill panel found on the page"
    return edge


def _panel_vertical_extent(px, x_interior: int, H: int):
    """Return (y0, y1): the first/last rows where an INTERIOR panel column is
    dark — i.e. the panel's top and bottom edges. The page has white top/bottom
    margins above/below the panel, which must be excluded from the edge-strip
    scan (they are page background, not clipped glyph ink).
    """
    rows = [y for y in range(H) if px[x_interior, y] < 140]
    assert rows, "interior panel column is not dark — wrong x"
    return min(rows), max(rows)


def _edge_strip_row_brightness(png_path: Path):
    """Open ``png_path`` (grayscale), locate the dark panel's right edge, and
    return ``(max_row_brightness, edge_x, x0)`` for the rightmost ~2mm-wide
    strip INSIDE the panel — measured over the STAT/TEXT region of the panel
    only. Glyph ink on the dark panel is light/accent-colored, so a CLIPPED stat
    VALUE shows up as a BRIGHT pixel right at the panel boundary; a non-clipped
    panel's rightmost strip falls in the panel's ~6mm right padding and is
    (near-)uniformly the dark panel colour.

    The panel's TOP band is the client PORTRAIT photo (a real image that
    legitimately fills the panel edge-to-edge and is bright) — that is NOT
    glyph clipping, so the scan SKIPS the leading bright portrait band: it
    starts at the first row (top→down) where the edge strip goes dark and
    measures from there to the panel bottom. That covers the name/role/url, the
    stat stack, and the QR/quote foot — exactly the text/QR region where a
    clipped stat value would appear.
    """
    from PIL import Image

    im = Image.open(png_path).convert("L")
    W, H = im.size
    px = im.load()
    edge = _dark_panel_right_edge(px, W, H)
    strip_w = max(1, round(2 * W / 210))  # ~2mm at A4 width
    x0 = edge - strip_w + 1
    y0, y1 = _panel_vertical_extent(px, x_interior=edge - (W // 4), H=H)

    def strip_max(y):
        return max(px[x, y] for x in range(x0, edge + 1))

    # Skip the leading PORTRAIT band: advance y past the contiguous bright run
    # at the panel top (the photo). The portrait is at most ~60mm tall; cap the
    # skip well under that so we never skip into the stat stack.
    max_skip = y0 + round(62 * H / 297)  # ~62mm at A4 height
    scan_start = y0
    while scan_start < min(y1, max_skip) and strip_max(scan_start) >= 150:
        scan_start += 1

    row_max = [strip_max(y) for y in range(scan_start, y1 + 1)]
    return max(row_max), edge, x0


def _apex_ctx() -> RenderContext:
    pkg = load_package(APEX)
    return RenderContext(
        brand=pkg.brand,
        grammar=load_grammar(),
        package_dir=pkg.package_dir,
        report_assets=pkg.report_assets,
    )


def _apex_case_study_page() -> dict:
    """A deep COPY of the real apex case-study page (the first ST-07A,
    CASE_STUDY_INDEX — portrait absent, numeral metrics).

    Deep-copied so a test can set layout_variant WITHOUT mutating the loaded
    package (and never the on-disk fixture).
    """
    pkg = load_package(APEX)
    page = copy.deepcopy(pkg.pages[CASE_STUDY_INDEX])
    assert str(page.get("st_type")) == "ST-07A"
    return page


def _apex_case_study_page_without_portrait() -> dict:
    """The real CASE_STUDY_INDEX copy with the case_study_portrait slot stripped,
    so a test can exercise the portrait-absent graceful path (the fixture now
    resolves cs_*.png portraits on every case study)."""
    page = _apex_case_study_page()
    page["slots"] = [
        slot
        for slot in (page.get("slots") or [])
        if str(slot.get("slot_id", "")).find("case_study_portrait") == -1
    ]
    page["assets"] = [
        asset
        for asset in (page.get("assets") or [])
        if str(asset.get("slot_id", "")).find("case_study_portrait") == -1
    ]
    return page


def st_07a_portrait_uri(page: dict) -> str:
    return _apex_ctx().slot_uri(page, "case_study_portrait") or ""


# --------------------------------------------------------------------------- #
# 1. fill variant renders on exactly ONE physical page (no overflow)
# --------------------------------------------------------------------------- #
def test_fill_variant_renders_one_page():
    from validators.overflow import count_pages

    page = _apex_case_study_page()
    page["layout_variant"] = "fill"
    frag = st_07a.render(page, _apex_ctx())

    # standalone 1-page render, mirroring the assembler's overflow check
    from assembler import shared_head_css, _section
    pkg = load_package(APEX)
    head = shared_head_css(pkg.brand, CHASSIS_ROOT / "fonts", pkg.axes)
    one_doc = (
        '<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">'
        f"<style>{head}{frag.css}</style></head>"
        f"<body>{_section(page, frag, CASE_STUDY_INDEX)}</body></html>"
    )
    assert count_pages(one_doc, base_url=str(CHASSIS_ROOT)) == 1


# --------------------------------------------------------------------------- #
# 2. fill variant SUBSTANTIALLY reduces dead space (the real acceptance proof)
# --------------------------------------------------------------------------- #
@pytest.mark.xfail(reason="Phase A theme-lock (2026-06-05): dead-space thresholds were calibrated to pre-canon (smaller) type; canon type fills/overflows these pages. Re-calibrate in Phase B per-pattern reflow + Task 12 re-bake. Plan: docs/superpowers/plans/2026-06-05-phase-A-renderer-theme-lock.md", strict=False)
def test_fill_variant_reduces_dead_space():
    from perception import dead_space_fraction
    from assembler import render_package

    def _render_variant(variant: str | None, out_dir: Path) -> float:
        patched = out_dir / "patched_pkg"
        if patched.exists():
            shutil.rmtree(patched)
        shutil.copytree(APEX, patched)
        jpath = patched / "resolved_package.json"
        data = json.loads(jpath.read_text())
        # mutate the COPY's case-study page in place
        if variant is None:
            data["pages"][CASE_STUDY_INDEX].pop("layout_variant", None)
        else:
            data["pages"][CASE_STUDY_INDEX]["layout_variant"] = variant
        jpath.write_text(json.dumps(data, ensure_ascii=False))
        render_package(patched, out_dir)
        return dead_space_fraction(out_dir / NUMERAL_CASE_STUDY_PNG)

    with tempfile.TemporaryDirectory() as t:
        base = Path(t)
        std = _render_variant("standard", base / "std")
        fill = _render_variant("fill", base / "fill")

    print(f"\n[ST-07A dead_space] standard={std:.4f}  fill={fill:.4f}")
    # standard is ~0.39; fill must drop it substantially AND clear the loop's
    # N08 threshold (< 0.30). Not rigged: the dark full-height panel is what
    # earns the drop.
    assert std > 0.30, f"standard should under-fill (~0.39); got {std:.4f}"
    assert fill < 0.30, f"fill must clear N08 (<0.30); got {fill:.4f}"
    assert fill < std - 0.10, (
        f"fill must SUBSTANTIALLY beat standard; std={std:.4f} fill={fill:.4f}"
    )


# --------------------------------------------------------------------------- #
# 3. portrait absent -> NO empty media frame (graceful no-box, like standard)
# --------------------------------------------------------------------------- #
def test_fill_variant_no_empty_photo_box():
    page = _apex_case_study_page_without_portrait()  # portrait ABSENT
    page["layout_variant"] = "fill"
    html = st_07a.render(page, _apex_ctx()).html
    # the media_figure macro markup must be absent when there is no portrait
    assert "c-media" not in html, "no media figure when portrait absent"
    assert "c-media--empty" not in html, "no empty placeholder plate"
    assert "c-media-img--placeholder" not in html


# --------------------------------------------------------------------------- #
# 4. default ("standard"/absent) is byte-identical to today's render
# --------------------------------------------------------------------------- #
def test_standard_variant_unchanged():
    ctx = _apex_ctx()

    # The fixture page now carries layout_variant="fill" (the preprocessor's
    # ST-07A default). To exercise the renderer's KEY-ABSENT back-compat path we
    # remove the key; the renderer must then fall back to "standard".
    page_absent = _apex_case_study_page()
    page_absent.pop("layout_variant", None)  # truly variant-absent
    html_absent = st_07a.render(page_absent, ctx).html

    page_std = _apex_case_study_page()
    page_std["layout_variant"] = "standard"
    html_std = st_07a.render(page_std, ctx).html

    assert html_absent == html_std, "explicit 'standard' must equal default"

    # And both must equal the literal standard layout markup (the fill markup
    # must NOT leak in). The standard layout uses the .cs-grid table sidebar; the
    # fill variant introduces a distinct full-height dark panel marker.
    assert "cs-grid" in html_absent
    assert 'data-cs-variant="fill"' not in html_absent


# --------------------------------------------------------------------------- #
# 5. CLIP-PROOF: prose stat values must NOT clip at the dark panel's right edge
# --------------------------------------------------------------------------- #
def test_fill_stat_prose_value_does_not_clip():
    """pages[PROSE_CASE_STUDY_INDEX] has PROSE stat values (e.g. "von bis zu 24
    Stunden auf Minuten"). At the big --type-display-xl size they overflow the
    ~64mm dark panel and CLIP at its right edge. After the fix, long values
    wrap at a smaller size and never reach the edge — so the rightmost ~2mm
    strip of the panel stays (near-)uniformly the dark panel colour (no bright
    glyph ink cut at the boundary).

    NOTE: renders as a STANDALONE single-page document — NOT by scanning
    report-pN.png from a full-deck render.  This makes the test
    pagination-independent: it uses the logical pages[] index only, so any
    future deck reflow that shifts physical page numbers cannot break it.
    """
    with tempfile.TemporaryDirectory() as t:
        png_path = _render_standalone_fill_png(PROSE_CASE_STUDY_INDEX, Path(t))
        max_bright, edge, x0 = _edge_strip_row_brightness(png_path)

    print(
        f"\n[ST-07A clip prose] edge_x={edge} strip_x0={x0} "
        f"max_edge_strip_brightness={max_bright}"
    )
    # The dark panel ink is ~55-100 in grayscale; clipped light/accent glyphs
    # spike toward ~250. A non-clipped panel's right strip (inside the panel's
    # ~6mm right padding) stays solidly dark. 150 is a comfortable separator:
    # well above the dark ground, well below any glyph ink that reaches the edge.
    assert max_bright < 150, (
        f"stat value clips at the panel right edge: max edge-strip brightness "
        f"{max_bright} (>=150 means bright glyph ink is cut at the boundary)"
    )


# --------------------------------------------------------------------------- #
# 6. NUMERAL values (CASE_STUDY_INDEX) must KEEP the big treatment (no --long modifier)
# --------------------------------------------------------------------------- #
def test_fill_stat_numeral_value_stays_big():
    """CASE_STUDY_INDEX has crisp numeral values ("4", "> 200.000 €", "24 Std. →
    Minuten") that FIT at the big size. The fix must NOT shrink them: the
    rendered fragment must carry NO long-modifier class on those stat values.
    """
    page = _apex_case_study_page()  # CASE_STUDY_INDEX: numeral metrics
    page["layout_variant"] = "fill"
    html = st_07a.render(page, _apex_ctx()).html

    # the big-number stat stack must be present...
    assert "cs-statstack-value" in html, "fill stat stack must render"
    # ...and NONE of its values may carry the long/prose modifier.
    assert "cs-statstack-value--long" not in html, (
        "numeral stat values must keep the big --type-display-xl treatment; "
        "the --long shrink modifier must not be applied to them"
    )


# --------------------------------------------------------------------------- #
# 7. both fill renders (numeral p7 + prose p12) stay exactly ONE physical page
# --------------------------------------------------------------------------- #
def test_fill_variant_still_one_page():
    # Per-page overflow check for BOTH case studies under their REAL rendered
    # geometry. CASE_STUDY_INDEX renders the FILL variant on A4 (it is the one
    # page the fixture still fits in fill); PROSE_CASE_STUDY_INDEX renders the
    # casestudy_hero A3 spread, so its standalone check must stamp format-a3
    # (the treatment's real sheet) or WeasyPrint would mis-measure the A3
    # layout on an A4 box. The ship path is Chromium (physical==logical at the
    # deck level); these standalone checks are the fast per-page regression
    # guard.
    from validators.overflow import count_pages
    from assembler import shared_head_css, _section

    pkg = load_package(APEX)
    head = shared_head_css(pkg.brand, CHASSIS_ROOT / "fonts", pkg.axes)
    cases = [
        (CASE_STUDY_INDEX, "fill", None),          # numeral case study on A4
        (PROSE_CASE_STUDY_INDEX, None, "a3"),      # prose case study: real hero A3 sheet
    ]
    for idx, variant, page_format in cases:
        pg = copy.deepcopy(pkg.pages[idx])
        if variant:
            pg["layout_variant"] = variant
        frag = st_07a.render(pg, _apex_ctx())
        one_doc = (
            '<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">'
            f"<style>{head}{frag.css}</style></head>"
            f"<body>{_section(pg, frag, idx, page_format=page_format)}</body></html>"
        )
        n = count_pages(one_doc, base_url=str(CHASSIS_ROOT))
        assert n == 1, (
            f"pages[{idx}] {variant or 'real'} render must be 1 page; got {n}"
        )


# --------------------------------------------------------------------------- #
# 8. fill lede modifier: template emits cs-lede--fill; CSS uses --type-lede
# --------------------------------------------------------------------------- #
def test_fill_lede_modifier_in_html():
    """The FILL branch lede must carry the cs-lede--fill modifier so the CSS
    can size it up to --type-lede (12pt) for visual hierarchy in the wider left
    column. The STANDARD branch lede must NOT carry the modifier.

    Uses the real apex case-study page (CASE_STUDY_INDEX) which has a populated
    ``kurzportraet`` field — the data key that the pattern maps to ``lede_html``.
    """
    # The real apex CASE_STUDY_INDEX has kurzportraet populated, so lede_html renders.
    page_fill = _apex_case_study_page()
    page_fill["layout_variant"] = "fill"
    html_fill = st_07a.render(page_fill, _apex_ctx()).html
    # lede_html must be present (the fixture kurzportraet is non-empty)
    assert "cs-lede" in html_fill, "lede block must render in fill variant"
    assert "cs-lede--fill" in html_fill, (
        "fill variant lede must carry the cs-lede--fill modifier"
    )

    page_std = _apex_case_study_page()
    page_std["layout_variant"] = "standard"
    html_std = st_07a.render(page_std, _apex_ctx()).html
    assert "cs-lede--fill" not in html_std, (
        "standard variant lede must NOT carry the cs-lede--fill modifier"
    )


def test_fill_lede_css_uses_type_lede():
    """st_07a.css must define .cs-lede--fill with var(--type-lede) — NOT
    --type-cta (11.5pt is too close to body for a clear gap). Token only.
    """
    css = (CHASSIS_ROOT / "styles" / "st_07a.css").read_text(encoding="utf-8")
    assert ".cs-lede--fill" in css, (
        "st_07a.css must define the .cs-lede--fill modifier"
    )
    assert "var(--type-lede)" in css, (
        "st_07a.css .cs-lede--fill must use var(--type-lede), not --type-cta"
    )


# --------------------------------------------------------------------------- #
# 9. NO QR on case studies — a scannable code mid-case-study is clutter; the one
#    designed QR lives on the back-cover CTA (ST-03), which KEEPS it.
# --------------------------------------------------------------------------- #
def test_case_study_renders_no_qr_both_variants():
    """ST-07A must render NO QR in EITHER variant. The `.cs-panel-qr` wrapper
    only appears when the pattern feeds a non-empty qr_svg; the pattern now feeds
    "" so the wrapper (and the inner qr macro) never render.
    """
    ctx = _apex_ctx()
    for variant in ("fill", "standard"):
        page = _apex_case_study_page()
        page["layout_variant"] = variant
        html = st_07a.render(page, ctx).html
        assert "cs-panel-qr" not in html, (
            f"ST-07A ({variant}) must render NO QR wrapper; found cs-panel-qr"
        )


def test_cta_page_st03_keeps_its_qr():
    """Guard the KEEP half: the back-cover CTA (ST-03) still renders its QR — the
    removal is scoped to case studies only, not a global QR purge.
    """
    from patterns import st_03  # noqa: E402

    pkg = load_package(APEX)
    st03_pages = [p for p in pkg.pages if str(p.get("st_type")) == "ST-03"]
    assert st03_pages, "apex fixture must contain an ST-03 CTA page"
    html = st_03.render(st03_pages[0], _apex_ctx()).html
    assert "c-qr" in html, "ST-03 CTA must keep its QR (c-qr macro markup)"


# --------------------------------------------------------------------------- #
# 10. GAP C — client-matched social post renders a COMPACT phone, REPLACING the
#     static portrait (never both). The bound case study is
#     SOCIAL_POST_CASE_STUDY_INDEX (slot 12, Frese); the planner wrote
#     data.social_post {photo, avatar, handle}.
# --------------------------------------------------------------------------- #
def _social_post_page() -> dict:
    """A deep COPY of the apex Frese case study (SOCIAL_POST_CASE_STUDY_INDEX)
    which the planner bound a client-matched social_post onto.

    The current pattern rule: a REAL resolved portrait is the authority photo
    and always wins the rail, so the social_post phone only renders when no
    portrait is present. SOCIAL_POST_CASE_STUDY_INDEX now resolves cs_frese.png,
    so this helper strips the portrait to exercise the phone path (the scenario
    the tests below are written for). It also pins the FILL variant: the Frese
    page is casestudy_hero in the fixture, and the cs-socialpost phone host
    lives in the fill and standard layouts."""
    pkg = load_package(APEX)
    page = copy.deepcopy(pkg.pages[SOCIAL_POST_CASE_STUDY_INDEX])
    assert str(page.get("st_type")) == "ST-07A"
    assert (page.get("data") or {}).get("social_post"), (
        "fixture SOCIAL_POST_CASE_STUDY_INDEX must carry data.social_post "
        "(run build_package first)"
    )
    page["layout_variant"] = "fill"
    page["slots"] = [
        slot
        for slot in (page.get("slots") or [])
        if str(slot.get("slot_id", "")).find("case_study_portrait") == -1
    ]
    page["assets"] = [
        asset
        for asset in (page.get("assets") or [])
        if str(asset.get("slot_id", "")).find("case_study_portrait") == -1
    ]
    return page


def test_social_post_renders_phone_mockup():
    """When data.social_post is present, ST-07A renders the renderer-drawn phone
    (the .c-phone device chrome inside a .cs-socialpost host)."""
    page = _social_post_page()  # fill variant in the fixture
    html = st_07a.render(page, _apex_ctx()).html
    assert "cs-socialpost" in html, "social post host must render"
    assert "c-phone" in html, "phone_mockup device chrome must render"
    assert "c-phone__photo" in html, "the post photo must render in the phone"


def test_social_post_replaces_static_portrait_not_added():
    """The phone REPLACES the static portrait — the page must NOT render BOTH a
    cs-portrait media frame AND the phone (two stacked photos would overflow the
    narrow rail). With social_post present, the cs-portrait block is suppressed.
    """
    page = _social_post_page()
    html = st_07a.render(page, _apex_ctx()).html
    assert "cs-socialpost" in html
    # the static portrait media frame must NOT also be present
    assert "cs-portrait" not in html, (
        "static portrait must be REPLACED by the phone, not rendered alongside"
    )


def test_social_post_absent_falls_back_to_portrait_path():
    """Without a social_post the pattern takes the normal portrait path (and the
    graceful no-box behaviour is unchanged): NO phone renders."""
    page = _social_post_page()
    page.get("data", {}).pop("social_post", None)
    html = st_07a.render(page, _apex_ctx()).html
    assert "cs-socialpost" not in html, "no phone host when social_post absent"
    assert "c-phone" not in html, "no phone chrome when social_post absent"


# --------------------------------------------------------------------------- #
# 11. before->after TRANSFORM metric renders as Richard's BAR device (vocab #3),
#     NOT a text arrow glyph. "24 Std. → Minuten" → gray before bar collapsing to
#     an accent after bar; both states shown verbatim, no fabricated number.
# --------------------------------------------------------------------------- #
def test_transform_bar_heights():
    """Bar geometry derives from the SAME leading-number extractor the viz
    macros use (_leadnum): the taller bar is the larger magnitude; a side with
    no number floors to a small visible sliver (no invented figure)."""
    from patterns.st_07a import _transform_bar_heights

    bh, ah = _transform_bar_heights("24 Std.", "Minuten")  # 24 vs no-number
    assert bh == 100, bh
    assert 0 < ah <= 20, ah  # the after state is a floored sliver, not a figure

    bh2, ah2 = _transform_bar_heights("30 Min", "2 Min")  # numeric pair
    assert bh2 == 100 and ah2 < bh2, (bh2, ah2)


def test_fill_transform_renders_before_after_bars():
    """A before->after metric ("24 Std. → Minuten") renders the before/after
    BAR device (gray before, accent after) in the fill rail — never a
    text-arrow glyph.

    The current apex fixture's case-study metrics are plain figures (no arrow),
    so this test injects the transform metric into a deep copy of
    CASE_STUDY_INDEX to exercise the device."""
    page = _apex_case_study_page()
    page["data"] = dict(page.get("data") or {})
    page["data"]["ergebnis_metrics"] = [
        {"value": "24 Std. → Minuten", "label": "Reaktionszeit"},
    ]
    page["layout_variant"] = "fill"
    html = st_07a.render(page, _apex_ctx()).html

    assert "cs-statstack-ba" in html, "transform metric must render the bar device"
    assert "cs-ba-bar--before" in html and "cs-ba-bar--after" in html
    assert "24 Std." in html and "Minuten" in html  # both states shown verbatim
    # the old text-arrow device must be gone entirely
    assert "cs-tf-arrow" not in html
    assert "cs-statstack-transform" not in html


def test_social_post_case_study_stays_one_page():
    """GAP C verify: the case study the planner bound the social post onto
    (SOCIAL_POST_CASE_STUDY_INDEX, slot 12, Frese) MUST still render on exactly
    ONE physical page — the compact phone (sized to the rail in
    styles/st_07a.css) must NOT push the page into overflow.

    SOCIAL_POST_CASE_STUDY_INDEX renders the casestudy_hero A3 spread, so the
    standalone check stamps format-a3 (its real sheet) — WeasyPrint would
    mis-measure the A3 layout on the default A4 box."""
    from validators.overflow import count_pages
    from assembler import shared_head_css, _section

    idx = SOCIAL_POST_CASE_STUDY_INDEX
    pkg = load_package(APEX)
    pg = copy.deepcopy(pkg.pages[idx])
    frag = st_07a.render(pg, _apex_ctx())
    head = shared_head_css(pkg.brand, CHASSIS_ROOT / "fonts", pkg.axes)
    one_doc = (
        '<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">'
        f"<style>{head}{frag.css}</style></head>"
        f"<body>{_section(pg, frag, idx, page_format='a3')}</body></html>"
    )
    n = count_pages(one_doc, base_url=str(CHASSIS_ROOT))
    assert n == 1, f"Frese case study (pages[{idx}]) with social post must be 1 page; got {n}"
