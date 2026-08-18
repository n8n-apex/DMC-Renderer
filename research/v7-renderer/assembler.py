"""Assembler — package -> one HTML document -> PDF + PNGs + validators.

Flow:
  load_package() -> for each page dispatch to its pattern -> PageFragment
  -> assemble ONE document (shared <head> + deduped fragment CSS + one
  <section class="page st-XX"> per page, each carrying a per-page folio
  via WeasyPrint `string-set: pagefolio`) -> WeasyPrint write_pdf ->
  PyMuPDF rasterize -> overflow + accent-budget validators.

Never crashes: a pattern that raises is caught, the page falls back to
_generic (then to a placeholder), and a warning is recorded. The render
ALWAYS returns a RenderResult with a PDF + a warnings list.

R1 boundaries (documented, not bugs):
  - Print bleed / crop marks: Layer 3 (post-processor) scope; R1 emits
    plain A4 RGB.
  - Full-bleed page backgrounds size to the page CONTENT box (not the
    physical sheet); visual-tuning is R2.
  - report_assets are loaded into LoadedPackage and carried in the
    package, but axis-driven page backgrounds need the §4.0 axes which
    live on the pre-processor BrandProfile, NOT the 10-field BrandConfig
    the renderer consumes — so auto-applying them is R2 (would require
    threading axes into BrandConfig). Per-page background ASSETS (e.g.
    the cover hero) ARE rendered, via _generic.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import weasyprint  # noqa: E402
from weasyprint.text.fonts import FontConfiguration  # noqa: E402

from package_loader import load_package  # noqa: E402
from grammar_loader import load_grammar  # noqa: E402
from tokens.compile_tokens import compile_tokens, BrandAxes  # noqa: E402
from patterns import get_renderer  # noqa: E402
from patterns import _generic  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402
from validators.overflow import check_overflow  # noqa: E402
from validators.accent_budget import AccentBudgetValidator  # noqa: E402

FONT_DIR = (HERE / "fonts").resolve()
COMPONENTS_CSS = (HERE / "styles" / "components.css").resolve()
VIZ_CSS = (HERE / "styles" / "viz.css").resolve()
# Sibling sheet of VIZ_CSS: the COMPARISON family (formula_ladder / grouped_bars /
# stacked_bar_100 / entity_bars). Kept as its own file so the comparison devices
# can evolve without touching the preset library's sheet; scoped to the same
# `c-viz*` namespace, so bundle order with viz.css is conflict-free.
VIZ_COMPARE_CSS = (HERE / "styles" / "viz_compare.css").resolve()
DENSITY_CSS = (HERE / "styles" / "density.css").resolve()

# Deterministic neutral grain tile (seed=7, alpha≤14/255 ≈ 5.5% max opacity —
# a "whisper" texture). The data URI is a raster PNG tile, NOT an SVG
# feTurbulence filter: WeasyPrint 68.1 collapses SVG filter primitives to a
# flat off-color solid. Regenerate via scripts/gen_grain_tile.py.
# Import path: styles/_grain.py lives in the same package tree as assembler.py.
try:
    from styles._grain import GRAIN_DATA_URI as _GRAIN_DATA_URI  # noqa: E402
except ImportError:  # fallback: no grain if the file is missing
    _GRAIN_DATA_URI = ""


@dataclass
class RenderResult:
    pdf_path: Path
    png_paths: list[Path]
    page_count: int              # logical package pages
    overflow: list[str]          # per-page overflow flags (advisory)
    accent_budget_passed: bool
    warnings: list[str] = field(default_factory=list)


def _esc(s: str) -> str:
    return (
        str(s).replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;")
    )


# The booking tagline carried by the persistent running header (DNA §C6/§C7 —
# the DMC report's "persistent furniture"). This is a CONTENT LABEL for the
# report TYPE — the standard German DMC booking-CTA convention — NOT a client
# value (cf. the section-label constants `_EYEBROW` in st_03 and `_SECTION_SPEC`
# in st_07a). It is brand-agnostic: no client name, hex, or font. The URL that
# follows it is brand DATA (brand.company_url_display), supplied at render time.
_HEADER_BOOKING_TAGLINE = "Trage dich zu einem kostenlosen Erstgespräch ein unter:"


def _page_header(brand, eyebrow: str = "") -> str:
    """The persistent header band as a WeasyPrint running element.

    Prepended once to the document body; `.page-header { position: running(
    pageheader) }` (in shared_head_css) lifts it into every INTERIOR page's
    @top-center margin box (the full-bleed cover/back-cover/breathing pages
    suppress the whole margin box via `@page cover` / `@page bleed`, so the band
    — tagline + URL included — never paints there). Layout: the wordmark sits
    top-left (brand DATA, company_name_short); the booking CTA — a small
    secondary tagline (the brand-agnostic `_HEADER_BOOKING_TAGLINE` content
    label) followed by the brand URL (DATA, company_url_display) — is pushed
    hard-right. Together they form the DMC "persistent furniture" (DNA §C6):
    logo + booking tagline + URL above the band's own full-width hairline. The
    optional per-pattern eyebrow, when set, follows the URL. Styling (the
    hairline, the small/secondary CTA type, token colors) is in the head.
    """
    wordmark = _esc(brand.company_name_short)
    url = _esc(getattr(brand, "company_url_display", "") or "")
    # Booking CTA block (right side): the standard tagline + the brand URL. The
    # tagline is a content label; the URL is DATA. Rendered only when a URL is
    # present (graceful: no dangling "… unter:" with nothing after it).
    # US-501 (Richard grammar): the booking CTA is REMOVED from the running
    # header — editorial chrome = wordmark only (plus the optional per-pattern
    # eyebrow). The direct-response ask lives only on the CTA pages.
    eyebrow_html = f'<span class="ph-eyebrow">{_esc(eyebrow)}</span>' if eyebrow else ""
    return (
        '<div class="page-header" style="position: running(pageheader);">'
        '<span class="ph-tick"></span>'
        f'<span class="ph-wordmark">{wordmark}</span>{eyebrow_html}'
        "</div>"
    )


def _veiled_ground_uri(report_ground_uri: str, brand) -> Optional[str]:
    """Bake the surface veil INTO the ground texture and return the derived
    file's URI (None on any failure, so the caller degrades to plain surface).

    CHROMIUM ONLY: Chromium paints @page raster background layers at full
    strength and skips gradient layers entirely, so the paper-whisper contract
    (texture at ~12% under the brand surface) can only be honored there by
    compositing it into the asset itself; the weasyprint branch keeps its live
    CSS layer stack instead. The derived file lives next to the original,
    keyed by the veil color (<name>_veiled-<hex>.png) so a brand-surface
    change re-bakes instead of reusing a stale composite, and is reused when
    fresher than its source. Written atomically (tempfile + os.replace) so a
    crashed bake can never leave a truncated PNG for the next run to trust.
    The veil color is brand DATA (brand_neutral_light), not a literal: when
    the brand carries none, this returns None and the caller's fallback branch
    paints the plain surface."""
    try:
        import os
        import tempfile
        from urllib.parse import urlparse, unquote
        from urllib.request import url2pathname
        from PIL import Image
        surface = str(getattr(brand, "brand_neutral_light", "") or "").lstrip("#").lower()
        if not surface:
            return None
        src = Path(url2pathname(unquote(urlparse(report_ground_uri).path)))
        if not src.is_file():
            return None
        out = src.with_name(f"{src.stem}_veiled-{surface}.png")
        if not (out.is_file() and out.stat().st_mtime >= src.stat().st_mtime):
            rgb = tuple(int(surface[i:i + 2], 16) for i in (0, 2, 4))
            tex = Image.open(src).convert("RGB")
            veil = Image.new("RGB", tex.size, rgb)
            fd, tmp = tempfile.mkstemp(dir=str(src.parent), suffix=".png")
            os.close(fd)
            try:
                Image.blend(tex, veil, 0.88).save(tmp)
                os.replace(tmp, out)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
        return out.as_uri()
    except Exception:  # noqa: BLE001 (a bake failure must never kill a render)
        return None


def shared_head_css(
    brand,
    font_dir: Path,
    axes: "BrandAxes | None" = None,
    report_ground_uri: str = "",
    engine: str = "weasyprint",
) -> str:
    """Cross-page CSS owned by the head: @font-face x4, :root brand vars,
    @page (A4 + margins + persistent header band + per-page folio over a
    bottom ground wash), body, .page (the per-page content ground).

    The :root block is sourced from compile_tokens (the token layer) rather
    than hand-written; it emits the same --brand-* aliases (same values) the
    patterns consume.

    Persistent chrome (Plan B, Task 3 — the report's signature framing):
      - Header band: a single full-width running element (.page-header,
        injected once into the body by render_package and pulled into the
        @top-center margin box via `content: element(pageheader)`). It is a
        flex row: the wordmark (brand DATA) sits on ONE line above the band's
        own border-bottom hairline; an optional data-driven uppercase eyebrow
        is pushed hard-right and collapses to NOTHING (no stray divider) when
        empty. Replaces the prior fragile three-margin-box approach (wordmark
        wrapped to 2 lines, the rule cut through the text, a lone `|` dangled).
      - Folio wash: a pale gradient anchored to the page bottom via the
        @page `background-image` (verified to paint in WeasyPrint 68.1 — the
        running-string folio sits readable over it).
      - Axis page-ground: attribute hooks on <html data-ground-mode> flip the
        per-page content ground toward --color-ink (on-dark text) for
        ground_mode="dark"/"tonal"; light content pages use --color-ground as
        the .page background (--color-ground-wash is retained for the @page
        folio band only). Value-driven, never client-driven.
    """
    font_uri = Path(font_dir).resolve().as_uri()
    css_root, _ = compile_tokens(brand, axes or BrandAxes())

    # Generated report ground (atmospheric / frosted-texture). When the package
    # carries one, it is layered as the full content-box ground on EVERY light
    # page (renderer-owned placement, fed by the preprocessor asset) — replacing
    # the dull flat --color-ground. The whisper-grain stays layered on top. The
    # generated grounds are LIGHT (legible behind dark copy); a dark page keeps
    # its --color-ink ground. Graceful: no asset → grain-only (today's look).
    if report_ground_uri:
        _ground_image = f'url("{report_ground_uri}"), url("{_GRAIN_DATA_URI}")'
        _ground_repeat = "no-repeat, repeat"
        _ground_size = "cover, 128px 128px"
        _ground_position = "center center, top left"
    else:
        _ground_image = f'url("{_GRAIN_DATA_URI}")'
        _ground_repeat = "repeat"
        _ground_size = "128px 128px"
        _ground_position = "top left"

    # DIGITAL FULL-BLEED ground: when a brand has a generated ground AND a light
    # ground mode, paint it on the @page background so it covers the WHOLE sheet
    # (margins included) — edge-to-edge — WITHOUT margin:0 (the running header/folio
    # margin boxes survive) and WITHOUT changing the content box (pagination is
    # unchanged). The content box (.page) then goes transparent so the full-sheet
    # ground shows through seamlessly. Dark/tonal brands (or no ground) keep the
    # content-box treatment + the plain folio wash. Build-time gated → brand-agnostic.
    _ground_mode = (axes or BrandAxes()).ground_mode
    # 2026-07-13: light pages ALWAYS paint their ground on the FULL SHEET
    # (@page), with or without a generated texture. The old content-box-only
    # treatment left a visible GRAY RECTANGLE inside cream sheet margins (the
    # owner: "more like code generated") because .page painted --color-ground
    # while the sheet stayed --color-surface. Now the sheet carries the warm
    # surface + grain (+ texture when present) edge to edge and .page is
    # transparent; --color-ground no longer appears on light pages at all.
    _fullbleed = _ground_mode in ("light", "cool_light")
    _wash = "linear-gradient(to bottom, transparent 78%, var(--color-ground-wash))"
    if _fullbleed:
        if report_ground_uri and engine == "chromium":
            # SURFACE VEIL, PRE-BAKED into a derived asset (CHROMIUM ONLY). The
            # design contract for a generated ground is a paper WHISPER (the
            # old procedural marble shipped at 16% alpha), but Chromium paints
            # @page raster layers at full strength while SKIPPING gradient
            # layers entirely (empirically A/B-printed), so a CSS veil above
            # the texture can never protect the contract there. The composite
            # is baked with the surface token instead, and @page carries ONE
            # clean raster layer. A bake failure degrades to the plain surface
            # (never the raw texture wallpapering the sheet).
            _veiled = _veiled_ground_uri(report_ground_uri, brand)
            if _veiled:
                _page_bg_image = f'url("{_veiled}")'
                _page_bg_size = "cover"
                _page_bg_repeat = "no-repeat"
                _page_bg_position = "center center"
            else:
                _page_bg_image = f'{_wash}, url("{_GRAIN_DATA_URI}")'
                _page_bg_size = "auto, 128px 128px"
                _page_bg_repeat = "no-repeat, repeat"
                _page_bg_position = "center top, top left"
        elif report_ground_uri:
            # WeasyPrint DOES paint @page gradient layers over rasters
            # (verified), so no bake is needed: the veil stays the live
            # three-layer CSS stack (folio wash gradient over the generated
            # ground over the whisper grain).
            _page_bg_image = (
                f'{_wash}, url("{report_ground_uri}"), url("{_GRAIN_DATA_URI}")'
            )
            _page_bg_size = "auto, cover, 128px 128px"
            _page_bg_repeat = "no-repeat, no-repeat, repeat"
            _page_bg_position = "center top, center center, top left"
        else:
            _page_bg_image = f'{_wash}, url("{_GRAIN_DATA_URI}")'
            _page_bg_size = "auto, 128px 128px"
            _page_bg_repeat = "no-repeat, repeat"
            _page_bg_position = "center top, top left"
        _light_page_bg = "background: transparent;"  # @page carries the full-bleed ground
    else:
        _page_bg_image = _wash
        _page_bg_size = "auto"
        _page_bg_repeat = "no-repeat"
        _page_bg_position = "center top"
        _light_page_bg = (
            "background-color: var(--color-ground); "
            f"background-image: {_ground_image}; "
            f"background-repeat: {_ground_repeat}; "
            f"background-size: {_ground_size}; "
            f"background-position: {_ground_position};"
        )
    # ---- engine-specific page chrome (header band + folio) ----
    # WeasyPrint: the rich flex running element (.page-header) pulled into
    # @top-center via element(), folio via string-set — its native strengths.
    # Chromium print: element()/string-set are INERT (verified) — the chrome
    # becomes @page margin-box STRINGS (wordmark top-left, booking CTA top-right,
    # counter(page) folio) + the header hairline painted by the page's own top
    # border (appended below as engine extra CSS). Same margins/geometry either
    # way; the named cover/bleed pages suppress all of it via content:none.
    if engine == "chromium":
        _wm = (brand.company_name_short or "").replace("\\", "").replace("'", "\\'")
        _bk_url = (getattr(brand, "company_url_display", "") or "").replace("\\", "").replace("'", "\\'")
        _page_chrome = f"""
  @top-left {{
    content: '{_wm}';
    font-family: var(--font-head); font-weight: 600; font-size: 6.5pt;
    letter-spacing: 0.16em; text-transform: uppercase;
    color: var(--color-primary);
    vertical-align: bottom; padding-bottom: 1.4mm;
  }}
  /* US-501 (Richard grammar): the top-right header CTA ("Trage dich zu einem
     kostenlosen Erstgespräch ein...") is REMOVED. Richard's decks keep the
     running header as pure editorial chrome (wordmark only); the direct-
     response CTA destroys the premium authority and reads as a low-tier
     marketing funnel on every page. The booking ask lives ONLY on the CTA
     pages (ST-03 / ST-FAZIT), never in the header. */
  @top-right {{
    content: none;
  }}
  /* designed FOOTER: one continuous hairline across the sheet foot (the
     border-top of all three bottom margin boxes) with the brand wordmark
     left, the URL centered, and an accent folio right. */
  /* FOOTER BAND: three margin boxes as ONE level typographic line. No
     per-box border-top: the boxes size to content, so three separate borders
     rendered as a BROKEN 3-segment rule (the 2026-07-13 footer-alignment
     critique). Identical line-height + padding-top puts all three baselines
     on one level; the folio alone carries the accent. */
  @bottom-left {{
    content: '{_wm}';
    font-family: var(--font-head); font-weight: 600; font-size: 6.5pt;
    letter-spacing: 0.16em; text-transform: uppercase;
    color: var(--color-muted);
    line-height: 9pt;
    vertical-align: top; padding-top: 1.8mm; margin-bottom: 7mm;
  }}
  @bottom-center {{
    content: '{_bk_url}';
    font-family: var(--font-head); font-weight: 500; font-size: 6.5pt;
    letter-spacing: 0.08em;
    color: var(--color-muted);
    line-height: 9pt;
    vertical-align: top; padding-top: 1.8mm; margin-bottom: 7mm;
  }}
  @bottom-right {{
    content: counter(page);
    font-family: var(--font-head); font-weight: 700; font-size: 8pt;
    color: var(--color-accent);
    line-height: 9pt;
    vertical-align: top; padding-top: 1.8mm; margin-bottom: 7mm;
  }}"""
    else:
        _page_chrome = """
  /* Header band — a full-width running element (see .page-header below) is
     pulled into the top-center margin box. Repeats on every page. */
  @top-center {
    content: element(pageheader);
    width: 100%;
    vertical-align: bottom;
  }
  @bottom-right {
    content: string(pagefolio);
    font-family: var(--font-head); font-weight: 600; font-size: 8pt;
    color: var(--color-ink); padding: 0 0 4mm 0;
    border-top: 0.2mm solid var(--color-accent);
  }"""
    head = f"""
/* Bundled OFL faces. NO font-weight RANGE descriptor: WeasyPrint 68.1 rejects
   `font-weight:<min> <max>` as "invalid value" (harmlessly), but more important
   these variable faces select the requested weight (incl. bold 700/900) from the
   single declaration. CRITICAL: only faces whose cmap carries a format-12 subtable
   load here — fontconfig computes an EMPTY charset for format-4-only fonts (which
   silently dropped Montserrat/Playfair/Fraunces to system PT-Serif/Hiragino in
   every prior phase). Source Serif 4 + Source Sans 3 (Adobe, format-12) load.
   See plan 2026-06-03-renderer-phase-A. */
@font-face {{ font-family:'Source Sans 3'; src:url('{font_uri}/SourceSans3%5Bwght%5D.ttf') format('truetype'); font-style:normal; }}
@font-face {{ font-family:'Source Sans 3'; src:url('{font_uri}/SourceSans3-Italic%5Bwght%5D.ttf') format('truetype'); font-style:italic; }}
@font-face {{ font-family:'Source Serif 4'; src:url('{font_uri}/SourceSerif4%5Bopsz,wght%5D.ttf') format('truetype'); font-style:normal; }}
@font-face {{ font-family:'Source Serif 4'; src:url('{font_uri}/SourceSerif4-Italic%5Bopsz,wght%5D.ttf') format('truetype'); font-style:italic; }}
/* Inter (OFL variable, format-12 cmap verified) — a common brand heading face
   (P2: kill the Inter -> Source Sans fallback). */
@font-face {{ font-family:'Inter'; src:url('{font_uri}/Inter%5Bopsz,wght%5D.ttf') format('truetype'); font-style:normal; }}
@font-face {{ font-family:'Inter'; src:url('{font_uri}/Inter-Italic%5Bopsz,wght%5D.ttf') format('truetype'); font-style:italic; }}
/* ALIASES: 'Source Serif Pro' / 'Source Sans Pro' are the PRE-RENAME names of the
   same Adobe faces bundled above (Source Serif 4 / Source Sans 3). Brands often
   send the old name; these aliases map it onto the identical bundled file so the
   requested face genuinely renders instead of silently falling back. */
@font-face {{ font-family:'Source Serif Pro'; src:url('{font_uri}/SourceSerif4%5Bopsz,wght%5D.ttf') format('truetype'); font-style:normal; }}
@font-face {{ font-family:'Source Serif Pro'; src:url('{font_uri}/SourceSerif4-Italic%5Bopsz,wght%5D.ttf') format('truetype'); font-style:italic; }}
@font-face {{ font-family:'Source Sans Pro'; src:url('{font_uri}/SourceSans3%5Bwght%5D.ttf') format('truetype'); font-style:normal; }}
@font-face {{ font-family:'Source Sans Pro'; src:url('{font_uri}/SourceSans3-Italic%5Bwght%5D.ttf') format('truetype'); font-style:italic; }}
/* Montserrat + Playfair Display (OFL variable): their TTFs shipped in fonts/ for
   months with NO @font-face, so a brand asking for them silently rendered in the
   fallback face (every christoph deck printed in Source Sans 3, not Montserrat).
   Declaring them here is what makes the brand's own face actually load; the
   family names are also listed in the tokens' $extra-bundled-families so the
   compile step stops warning about them. */
@font-face {{ font-family:'Montserrat'; src:url('{font_uri}/Montserrat%5Bwght%5D.ttf') format('truetype'); font-style:normal; }}
@font-face {{ font-family:'Montserrat'; src:url('{font_uri}/Montserrat-Italic%5Bwght%5D.ttf') format('truetype'); font-style:italic; }}
@font-face {{ font-family:'Playfair Display'; src:url('{font_uri}/PlayfairDisplay%5Bwght%5D.ttf') format('truetype'); font-style:normal; }}
@font-face {{ font-family:'Playfair Display'; src:url('{font_uri}/PlayfairDisplay-Italic%5Bwght%5D.ttf') format('truetype'); font-style:italic; }}
{css_root}
@page {{
  size: A4 portrait;
  margin: 16mm 14mm 20mm 18mm;
  /* Base sheet + folio wash: a pale ground-wash anchored to the page BOTTOM.
     WeasyPrint 68.1 paints linear-gradient on @page background-image; `to
     bottom` lands the solid stop at the bottom edge (verified). Transparent
     for the top ~78% so only the folio band carries the wash. */
  background-color: var(--color-surface);
  background-image: {_page_bg_image};
  background-size: {_page_bg_size};
  background-repeat: {_page_bg_repeat};
  background-position: {_page_bg_position};
{_page_chrome}
}}
/* Named page for the full-bleed COVER (ST-01). margin:0 so the hero bleeds to
   the physical sheet edges, and the persistent header band + folio are
   SUPPRESSED (content:none) — the cover is a showcase, not a chromed page. A
   page assigns itself this via `page: cover` in its scoped layout sheet. Note:
   in WeasyPrint 68.1, `page:` applied to the per-page <section> reliably routes
   that section's box to the named page. Token-only => brand-agnostic. */
@page cover {{
  size: A4 portrait;
  margin: 0;
  background: none;
  @top-center {{ content: none; }}
  @top-left {{ content: none; }}
  @top-right {{ content: none; }}
  @bottom-left {{ content: none; }}
  @bottom-center {{ content: none; }}
  @bottom-right {{ content: none; }}
}}
/* Named page for the full-bleed BREATHING / atmospheric pages (ST-31/ST-32). The
   SAME full-bleed technique as the cover: margin:0 so the atmospheric ground (the
   brand texture/gradient asset, or a token gradient fallback) bleeds to the
   physical sheet edges, and the persistent header band + folio are SUPPRESSED
   (content:none) — a breathing page is a deliberate pause, not a chromed content
   page. A page assigns itself this via `page: bleed` in its scoped layout sheet.
   Token-only => brand-agnostic. */
@page bleed {{
  size: A4 portrait;
  margin: 0;
  background: none;
  @top-center {{ content: none; }}
  @top-left {{ content: none; }}
  @top-right {{ content: none; }}
  @bottom-left {{ content: none; }}
  @bottom-center {{ content: none; }}
  @bottom-right {{ content: none; }}
}}
/* Treatment-library page formats (Task 0.2): named @page rules a logical page
   opts into via the `.page.format-a3` / `.page.format-a4` routing classes
   below. They mirror the base @page EXACTLY (same margins, same background-*
   layers, same {{_page_chrome}} margin boxes) so the persistent header band +
   folio chrome is REPLICATED, not lost. Named @page rules do not inherit the
   base margin boxes (cf. the cover/bleed pages which must re-suppress them).
   a3-landscape is the wide 420x297 sheet; a4-portrait restates the default
   210x297 so a page can pin its size explicitly. Token-only => brand-agnostic.
   These are INERT until a section carries a format class. */
@page a3-landscape {{
  size: A3 landscape;
  margin: 16mm 14mm 20mm 18mm;
  background-color: var(--color-surface);
  background-image: {_page_bg_image};
  background-size: {_page_bg_size};
  background-repeat: {_page_bg_repeat};
  background-position: {_page_bg_position};
{_page_chrome}
}}
@page a4-portrait {{
  size: A4 portrait;
  margin: 16mm 14mm 20mm 18mm;
  background-color: var(--color-surface);
  background-image: {_page_bg_image};
  background-size: {_page_bg_size};
  background-repeat: {_page_bg_repeat};
  background-position: {_page_bg_position};
{_page_chrome}
}}
/* ---- SELF-CHROMED bleed sections (the rail treatments) ----
   Chromium clips page content at the page area AND ignores @page backgrounds,
   so a treatment's dark rail can never bleed past the margins on a chromed
   page: a cream halo framed every rail page (14mm right, 20mm below). Rail
   pages therefore route to the suppressed `bleed` named page (margin:0, the
   proven ST-03/dark-beat technique) and REPLICATE the margins as section
   padding, so the internal geometry is untouched while the rail's negative
   offsets paint into the now-visible padding zone. The suppressed wordmark /
   booking line / folio chrome is re-drawn INSIDE the section by these bars
   (markup injected in _section; the folio ordinal arrives via data-folio).
   Typography mirrors the @page margin-box strings exactly. The folio sits on
   the rail's ink band on these pages, so it reads in the on-dark token. */
.tp-chrome-top {{
  position: absolute;
  top: 0; left: 18mm; right: 14mm; height: 16mm;
  display: block;
  z-index: 3;
}}
.tp-chrome-top .tp-chrome-wm {{
  position: absolute; left: 0; bottom: 1.4mm;
  font-family: var(--font-head); font-weight: 600; font-size: 6.5pt;
  letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--color-primary);
}}
.tp-chrome-top .tp-chrome-booking {{
  position: absolute; right: 0; bottom: 1.4mm;
  font-family: var(--font-head); font-weight: 500; font-size: 6.5pt;
  color: var(--color-muted);
}}
.tp-chrome-bottom {{
  position: absolute;
  bottom: 0; left: 18mm; right: 14mm; height: 20mm;
  display: block;
  z-index: 3;
}}
.tp-chrome-bottom span {{ position: absolute; top: 1.8mm; line-height: 9pt; }}
.tp-chrome-bottom .tp-chrome-wm {{
  left: 0;
  font-family: var(--font-head); font-weight: 600; font-size: 6.5pt;
  letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--color-muted);
}}
.tp-chrome-bottom .tp-chrome-url {{
  left: 50%; transform: translateX(-50%);
  font-family: var(--font-head); font-weight: 500; font-size: 6.5pt;
  letter-spacing: 0.08em;
  color: var(--color-muted);
}}
.tp-chrome-bottom .tp-chrome-folio {{
  right: 0;
  font-family: var(--font-head); font-weight: 700; font-size: 8pt;
  color: var(--color-on-dark);
}}
* {{ box-sizing: border-box; }}
html {{ font-size: 10pt; }}
body {{
  font-family: var(--font-body);
  font-size: var(--type-body);
  color: var(--color-body); margin: 0;
  /* Body leading is FEST-absolute 14pt (canon: 10.5pt body × 14pt leading = 4pt
     baseline grid). The density axis drives column-gap + paragraph-spacing via
     --density-col-gap / --density-para; it does NOT drive body line-height.
     --density-lead remains defined in density.css for pattern consumers (st_08,
     st_22, st_07b, st_02, st_fazit, _generic.py) that may still reference it,
     but it no longer controls the body element's own leading. */
  line-height: 14pt;
}}
/* ---- Persistent header band (running element) — DNA §C6/§C7 furniture ----
   Injected once into the body by the assembler; `position: running(pageheader)`
   lifts it out of the flow into the @top-center margin box on EVERY interior
   page (the full-bleed cover/back-cover/breathing pages suppress that margin box
   entirely via `@page cover`/`@page bleed`, so the band never paints there).
   The band is the DMC "persistent furniture": the wordmark (brand DATA) sits
   top-left; the booking CTA — a small secondary TAGLINE (a brand-agnostic
   content label) + the brand URL (DATA) — is pushed hard-right; an optional
   per-pattern eyebrow follows. A flex row (justify-content:space-between) splits
   left vs right; everything stays on ONE line (nowrap) so the band height never
   grows — the full-width hairline is the band's OWN border-bottom, so the rule
   sits cleanly UNDER the text. When no URL is present the booking block simply
   collapses (no dangling tagline). Token-colored => brand-agnostic. */
.page-header {{
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  width: 100%;
  padding: 0 0 var(--space-1) 0;
  border-bottom: 0.2mm solid var(--color-muted);
  font-family: var(--font-head);
  font-size: var(--type-eyebrow);
  line-height: 1.2;
}}
.page-header .ph-wordmark {{
  white-space: nowrap;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--color-primary);
}}
/* The booking CTA on the right: the tagline + URL on one baseline-aligned line,
   kept SMALL + SECONDARY (a header band, not a hero). The tagline is muted
   sentence-case (it reads as a quiet instruction, not a shout — so NOT
   uppercase/letterspaced like the wordmark); the URL carries a touch of weight +
   primary ink so the actionable part stands out without spending accent. */
/* US-501: .ph-booking removed — the header CTA is gone (Richard grammar). */
.page-header .ph-eyebrow {{
  white-space: nowrap;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--color-muted);
  margin-left: var(--space-3);
}}
/* Accent tick — a small static horizontal bar in accent color at the leading
   edge of the header band. Keeps the accent budget small (6mm × 0.6mm ≈ a
   hairline stripe). Never used in the footer/folio — folio stays muted. */
.page-header .ph-tick {{
  display: inline-block; width: 6mm; height: 0.6mm;
  background: var(--color-accent); margin-right: 2mm; vertical-align: middle;
}}
/* .page is the per-page CONTENT ground. Filling the content box height lets
   the axis-driven ground read as a page ground (not a content-hugging box).
   WeasyPrint caution: a background only paints on a block with real content
   AND height — .page always carries fragment markup, and min-height fills the
   A4 content box (297 - 16top - 20bottom = 261mm). */
.page {{ position: relative; break-after: page; min-height: 261mm; }}
.page:last-child {{ break-after: auto; }}
/* ---- Treatment page-format routing (Task 0.2) ----
   A logical page opts into a non-default sheet size by carrying a format class.
   format-a3 routes to the wide A3-landscape sheet; because that sheet is the
   SAME 297mm tall but the 261mm min-height + 0.4mm content border were sized for
   the A4 portrait content box, the A3 page DROPS both (min-height:0, border:none)
   so the slightly-taller-border + min-height can never push content onto a blank
   second sheet. format-a4 just pins the default A4-portrait sheet explicitly.
   INERT until a section carries one of these classes. Token-only / no literals. */
.page.format-a3 {{ page: a3-landscape; min-height: 0; border: none; }}
/* tp-rail sections route to the margin-0 bleed page in their treatment sheet;
   letting this rule ALSO claim them creates two competing page: declarations,
   and Chromium's print pass then lays the fragment out against one page
   geometry while printing on the other (observed: the whole rail page printed
   vertically squeezed to ~85 percent with a dead band below). The :not()
   leaves exactly one page: declaration per section. */
.page.format-a4:not(.tp-rail) {{ page: a4-portrait; }}

/* ---- Axis page-ground hooks (value-driven, not client-driven) ----
   PERCEPTIBLE by default: a neutral --color-ground sits behind light content
   pages (a readable, clearly-visible neutral — not the near-invisible 5%-accent
   wash that was here before Task 6). The @page folio-band gradient retains
   --color-ground-wash (its own subtle bottom strip — untouched).
   Task 7: a whisper-grain background-image (raster PNG tile, seed=7,
   alpha≤14/255 ≈ 5.5% max) is layered ON TOP of the background-color.
   The grain is always-on for light grounds (decoupled from the texture axis)
   so the default look is "rich". The tile is a base64 data-URI so it embeds
   directly in the CSS — no external file reference needed. */
[data-ground-mode="light"] .page,
[data-ground-mode="cool_light"] .page {{
  {_light_page_bg}
}}
/* [data-texture] intensifiers: marble_paper / crumpled_paper use multiply
   blend mode to deepen the grain into the ground tone. The grain still
   paints even without a data-texture attribute (the always-on whisper). */
[data-texture="marble_paper"] .page,
[data-texture="crumpled_paper"] .page {{
  background-blend-mode: multiply;
}}
/* ground_mode dark/tonal: flip the content ground toward ink with on-dark
   text. Scoped to .page (the content box) — NOT a full-bleed atmospheric
   sheet (those are specific patterns handled elsewhere). */
[data-ground-mode="dark"] .page,
[data-ground-mode="tonal"] .page {{
  background-color: var(--color-ink);
  color: var(--color-on-dark);
}}
/* ---- per-page MODE register (the rank-1 unlock) ----
   An OPTIONAL page['page_mode'] flips ONE section to a dark/flooded full-bleed
   BEAT without touching the whole-deck ground-mode — the missing 'this spread is
   a dark essay divider' register. It routes to the full-bleed `bleed` named page
   (margin:0, running header + folio SUPPRESSED) so the beat bleeds to the sheet
   edges like a section curtain, with internal padding standing in for the lost
   margins. The text-colour TOKENS are reassigned LOCALLY so EVERY descendant
   copy element auto-reverses (no per-element overrides needed); --color-accent +
   --color-primary stay intact so accent figures/panels still read. Token-only =>
   brand-agnostic. dark_divider/data_dark = near-black ink ground; color_flood =
   a saturated brand-primary field. */
.page[data-page-mode="dark_divider"],
.page[data-page-mode="data_dark"],
.page[data-page-mode="color_flood"] {{
  page: bleed;
  min-height: 297mm;
  padding: 22mm 22mm 24mm 22mm;
  position: relative;
  z-index: 0;            /* stacking context so the ghost letterform can sit
                            ABOVE the page ground but BEHIND the content */
  overflow: hidden;
}}
.page[data-page-mode="dark_divider"],
.page[data-page-mode="data_dark"] {{
  /* bg uses --color-neutral-dark (the near-black #brand_neutral_dark) which is
     NOT reassigned below — so it stays dark; --color-ink is repurposed as the
     LIGHT text token for descendants. (Using --color-ink for the bg here would
     resolve to its OWN reassigned light value — the bug that left the page light.)
     The MATERIAL (vs flat ink): a diagonal brand-primary cast deepening toward
     the base + a faint accent aurora top-right — chroma at mid value (the audit's
     fix for "saturation parked in near-black"), all token-derived via color-mix. */
  background-color: var(--color-neutral-dark);
  background-image:
    radial-gradient(circle at 84% 8%,
      color-mix(in srgb, var(--color-accent) 16%, transparent), transparent 52%),
    linear-gradient(160deg, transparent 30%,
      color-mix(in srgb, var(--color-primary) 42%, transparent) 130%);
  color: var(--color-on-dark);
  --color-ink: var(--color-on-dark);
  --color-body: var(--color-on-dark);
  --color-muted: var(--color-on-dark);
}}
/* ghost SECTION NUMBER on the dark beats — Richard's signature device
   (niklas "01"/"02"/"03" overlapping the dark panel). US-505/506: the prior
   brand-letter watermark read as generic filler; the giant zero-padded page
   number is Richard's actual move. Sized to the panel (~40% height), low
   contrast, anchored top-right behind the content. */
.page[data-page-mode] .pm-ghost {{
  position: absolute;
  z-index: -1;
  top: -8mm;
  right: -6mm;
  font-family: var(--font-head);
  font-size: 88mm;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.03em;
  color: var(--color-on-dark);
  opacity: 0.07;
}}
.page[data-page-mode="color_flood"] {{
  background-color: var(--color-primary);
  color: var(--color-on-primary);
  --color-ink: var(--color-on-primary);
  --color-body: var(--color-on-primary);
  --color-muted: var(--color-on-primary);
}}
/* ---- Axis headline-type hooks ----
   sans_allcaps: uppercase + tracked headline for a geometric sans display.
   Scoped ONLY to headline selectors (.c-two-tone DNA §C1 display titles + the
   page h1); body/thesis/captions remain sentence-case. */
[data-headline-type="sans_allcaps"] .c-two-tone,
[data-headline-type="sans_allcaps"] h1 {{ text-transform: uppercase; letter-spacing: 0.04em; }}
"""
    # Append the atomic component library ONCE. Its rules are all scoped to the
    # `c-` component namespace (.c-pill/.c-eyebrow/.c-section-label/.c-media/
    # .c-qr/.c-stat-strip/.c-pull-quote) which collides with no existing pattern
    # markup, so adding it changes nothing visually until a pattern adopts a macro.
    try:
        head += "\n" + COMPONENTS_CSS.read_text(encoding="utf-8")
    except OSError:
        pass
    # Data-viz PRESET library sheet (viz_* macros) — inlined right after the
    # component sheet so the .c-viz* premium classes are available to every page.
    # Token-only / brand-agnostic; Chromium honours its gradients/glow.
    try:
        head += "\n" + VIZ_CSS.read_text(encoding="utf-8")
    except OSError:
        pass
    # Comparison-family sheet (formula_ladder / grouped_bars / stacked_bar_100 /
    # entity_bars), inlined right after the preset library it extends. Same
    # token-only contract, same `c-viz*` namespace, so it adds no rule that an
    # existing page can collide with until a page carries one of those presets.
    try:
        head += "\n" + VIZ_COMPARE_CSS.read_text(encoding="utf-8")
    except OSError:
        pass
    # Density axis sheet — defines --density-* custom props per [data-density].
    # Only custom properties (no element rules), so bundle order is conflict-free;
    # the base body/column rules below consume these vars.
    try:
        head += "\n" + DENSITY_CSS.read_text(encoding="utf-8")
    except OSError:
        pass
    if engine == "chromium":
        head += """
/* Chromium print: the header hairline (the running band's border-bottom under
   the weasyprint chrome) is painted by the page's own top border. Suppressed on
   the full-bleed showcase pages (cover/breathers/back cover/dark beats own their
   sheet: their named pages already suppress the margin-box chrome) AND on the
   self-chromed bleed RAIL sections (the case-study page + the editorial-fill
   rail variant, both stamped .tp-rail by _section): those route to the margin:0
   bleed page, where the borders would print as hairlines at the physical sheet
   edges (the tp-chrome bars are the chrome there). TWO empirical Chromium
   fragmentation constraints shape the rail exemption (both verified on the
   apex deck; violating either splits the case-study sheets and adds four
   overflow sheets):
     (1) it must be a PLAIN class, not a `:has(.ef-grid.has-rail)` probe on the
         section, and
     (2) the editorial-fill rail section's border-TOP box is LOAD-BEARING for
         its named-page fragmentation, so that edge is hidden by color
         (transparent keeps the 0.2mm box; border-top:none re-paginates the
         deck onto 24 sheets). border-bottom: none is safe there. */
.page { border-top: 0.2mm solid var(--color-muted); border-bottom: 0.2mm solid var(--color-accent); }
.page.st-01, .page.st-31, .page.st-32, .page.st-03,
.page.treatment-a4_case_study,
.page[data-page-mode] { border-top: none; border-bottom: none; }
.page.tp-rail { border-top-color: transparent; border-bottom: none; }
/* FULL-BLEED SHEET CLAMP. Every bleed page (cover / breathers / back cover /
   dark beats / rail sections) sets its ground to the full 297mm sheet, which
   leaves its fragment at ~297.1mm inside a 297mm page area: a knife edge
   Chromium resolves per deck by luck (the christoph cover fit; the apex cover
   spilled a blank second sheet, and every later page shifted with it). The
   0.5mm clamp + clip is invisible at trim and makes the fit deterministic for
   ANY deck. Same rule the rail sections use. */
.page.st-01, .page.st-31, .page.st-32, .page.st-03, .page[data-page-mode] {
  height: 296.5mm;
  min-height: 0;
  overflow: hidden;
}
/* SELF-CHROMED RAIL SECTIONS: one routing rule for every railed page, keyed on
   the section-level .tp-rail stamp _section applies (the case-study treatment
   always, the editorial-fill portrait-rail variant via its fragment). The
   :has()-based routing this replaces silently failed in Chromium's PRINT pass
   (the About rail printed clipped at the chromed content box). EXPLICIT
   height a hair under the sheet + clip, never min-height 297mm: an exact-fit
   fragment on a named page is a knife edge Chromium resolves by spilling or
   by silently squeezing the page's whole vertical axis (both observed). */
.page.tp-rail {
  page: bleed;
  height: 296.5mm;
  min-height: 0;
  padding: 16mm 14mm 20mm 18mm;
  box-sizing: border-box;
  overflow: hidden;
  position: relative;
}
"""
    return head


def _folio(page: dict, index: int) -> str:
    val = page.get("page_numbers")
    folio = str(val) if val else str(index + 1)
    return folio.replace("\\", "").replace("'", "")


def _section(page: dict, frag: PageFragment, index: int,
             ghost_letter: str = "",
             treatment: Optional[str] = None,
             page_format: Optional[str] = None,
             chrome: Optional[tuple[str, str, str]] = None) -> str:
    st = str(page.get("st_type", "")).lower()
    folio = _folio(page, index)
    # Per-page MODE (the missing register): an OPTIONAL page['page_mode'] flips a
    # SINGLE section to a dark/flooded full-bleed beat without touching the
    # whole-deck ground-mode. Empty / "standard" → the normal chromed light page.
    mode = str(page.get("page_mode", "") or "").strip().lower()
    mode_attr = f' data-page-mode="{mode}"' if mode and mode != "standard" else ""
    # Treatment + format classes (Task 1.4 wiring): when the treatment system
    # actually rendered this page, stamp `treatment-<name>` (so per-treatment CSS
    # can scope to it) and `format-<a3|a4>` (the routing class that pins the named
    # @page sheet). A page that fell back to legacy passes both as None and is
    # stamped + sized as a normal page. Token-class only, brand-agnostic.
    extra_classes = ""
    if treatment:
        extra_classes += f" treatment-{treatment}"
    if page_format:
        extra_classes += f" format-{page_format}"
    # NOTE (2026-07-13): do NOT blanket-pin unclassed sections to the a4-portrait
    # named page. Chromium's mixed-size print compresses A4 content around a
    # MID-DECK A3 named page, and pinning every section made the compression
    # UNIVERSAL (even pages before the A3). Until the engine prints per-format
    # and merges (backlog), the stylist suppresses the A3 HERO promotion and
    # tail-guards the remaining A3 promotions (flow/spread pages only qualify
    # near the deck tail, the empirically safe zone).
    # Ghost brand letterform (Richard's 5-10% watermark) on the dark beats: the
    # brand's INITIAL (DATA — company_name_short[0], brand-agnostic) painted huge
    # at whisper opacity behind the content (z-index -1 inside the section's
    # stacking context). Light pages stay clean.
    ghost_html = ""
    if mode and mode != "standard" and ghost_letter:
        ghost_html = f'<div class="pm-ghost" aria-hidden="true">{_esc(ghost_letter)}</div>'
    # SELF-CHROME for the rail treatments: these sections route to the
    # suppressed `bleed` named page (their dark rail must reach the sheet
    # edges, and Chromium neither lets content escape the page area nor paints
    # @page backgrounds), so the wordmark / booking line / folio chrome that
    # the named page suppressed is re-drawn INSIDE the section. The folio is
    # the physical ordinal (each section is exactly one sheet; the page-count
    # QC enforces that), matching counter(page) on the chromed pages. The
    # a4_editorial_fill case keys on its rendered rail variant (fragment
    # markup), mirroring the CSS `:has(.ef-grid.has-rail)` routing.
    chrome_html = ""
    railed = treatment == "a4_case_study" or (
        treatment == "a4_editorial_fill" and "has-rail" in frag.html
    )
    if railed:
        # SECTION-level rail marker. The head's chromium border exemption keys
        # on this class instead of a `:has(.ef-grid.has-rail)` probe: a :has()
        # rule on the page sections derails Chromium's named-page print
        # fragmentation (verified on the apex deck: case-study sheets split
        # and four overflow sheets appeared), so the routing decision is
        # stamped here, where `railed` is already known.
        extra_classes += " tp-rail"
    if railed and chrome:
        _wm, _burl, _bk_line = chrome
        chrome_html = (
            '<div class="tp-chrome-top" aria-hidden="true">'
            f'<span class="tp-chrome-wm">{_esc(_wm)}</span>'
            f'<span class="tp-chrome-booking">{_esc(_bk_line)}</span></div>'
            '<div class="tp-chrome-bottom" aria-hidden="true">'
            f'<span class="tp-chrome-wm">{_esc(_wm)}</span>'
            f'<span class="tp-chrome-url">{_esc(_burl)}</span>'
            f'<span class="tp-chrome-folio">{index + 1}</span></div>'
        )
    return (
        f'<section class="page {st}{extra_classes}"{mode_attr} '
        f'style="string-set: pagefolio \'{folio}\';">{ghost_html}{frag.html}'
        f'{chrome_html}</section>'
    )


def _render_legacy_page(page: dict, ctx: "RenderContext", *,
                        warnings: list[str]) -> PageFragment:
    """Render ONE page through its legacy pattern (the path the default build has
    always used). A pattern that raises degrades to _generic, then to a static
    placeholder, recording a warning each step. Never raises."""
    st_type = str(page.get("st_type", ""))
    slot = page.get("slot")
    try:
        return get_renderer(st_type)(page, ctx)
    except Exception as exc:  # noqa: BLE001 (isolate per-page failures)
        warnings.append(f"slot {slot} ({st_type}): pattern raised {exc!r}; using generic")
        try:
            return _generic.render(page, ctx)
        except Exception as exc2:  # noqa: BLE001
            warnings.append(f"slot {slot} ({st_type}): generic raised {exc2!r}; placeholder")
            return PageFragment(
                html=f'<div class="st-generic"><p>page {slot} could not render</p></div>',
                css="",
            )


def _render_one_page(page: dict, ctx: "RenderContext", assignment, treatments: bool,
                     *, warnings: list[str]
                     ) -> tuple[PageFragment, Optional[str], Optional[str]]:
    """Render ONE page. Returns (frag, used_treatment, used_format).

    When treatments is on AND `assignment` names a treatment, try the treatment
    engine first. If it returns a PageFragment, use it and report the treatment
    name + page_format (so the section can be stamped + sized). If it returns
    None (data does not fit / unknown) OR raises (bug / missing template), fall
    back to the legacy pattern and report used_treatment=None, used_format=None
    (the page renders as a normal A4 legacy page, NOT mis-sized to A3). Genuine
    legacy-pattern failures still degrade to _generic, exactly as today.
    """
    if treatments and assignment is not None and assignment.treatment:
        # Lazy import here too: only reached on the treatments path, so the
        # default build never imports the engine.
        import treatment_engine
        slot = page.get("slot")
        st_type = str(page.get("st_type", ""))
        try:
            frag = treatment_engine.render(page, ctx, assignment.treatment)
        except Exception as exc:  # noqa: BLE001 (a treatment bug must NOT crash the deck)
            warnings.append(
                f"slot {slot} ({st_type}): treatment {assignment.treatment!r} "
                f"raised {exc!r}; using legacy pattern"
            )
            frag = None
        if frag is not None:
            return frag, assignment.treatment, assignment.page_format
        # frag is None: the data did not fit (or the treatment is unknown), so
        # fall through to the legacy pattern as a normal page.

    return _render_legacy_page(page, ctx, warnings=warnings), None, None


def render_package(package_dir: Path, output_dir: Path,
                   engine: str = "weasyprint",
                   treatments: bool = True) -> RenderResult:
    package_dir = Path(package_dir).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    pkg = load_package(package_dir)
    grammar = load_grammar()
    warnings: list[str] = []

    # Build the RenderContext ONCE: it is package-level (brand, grammar,
    # package_dir, report_assets), so it is shared by the stylist and every page
    # (and reused for the report-ground resolution below).
    ctx = RenderContext(brand=pkg.brand, grammar=grammar, package_dir=pkg.package_dir,
                        report_assets=pkg.report_assets)

    # ---- treatment assignments (ON BY DEFAULT — the core layout engine) ----
    # Every report the system ingests renders through the deterministic stylist
    # (per-page treatment + format). treatments=False is the legacy rollback
    # (exact pre-treatment behavior). assignments aligns 1:1 with pkg.pages.
    assignments = None
    if treatments:
        import treatment_catalog  # noqa: F401 (importing registers the descriptors)
        from treatment_stylist import assign, founder_identity
        import treatment_engine  # noqa: F401 (render dispatch used in _render_one_page)
        assignments = assign(pkg.pages, ctx)

        # ---- founder-identity fallback (brand-agnostic) ----
        # An image-led treatment (needs_image) assigned to a page that has NO
        # portrait of its OWN borrows the package's FOUNDER IDENTITY: the first
        # resolved `founder` slot path + the `author` (name + role) found on any
        # page (computed once by founder_identity). We inject a SYNTHETIC resolved
        # `founder` slot + an `author` onto such a page IN PLACE, before rendering,
        # so adapt()'s `_primary_image` probe resolves the portrait and the
        # type adapter reads the author into a caption. No client path/name is
        # hardcoded here: founder_identity finds them structurally. Graceful: when
        # the package has no founder identity, nothing is injected (the page keeps
        # whatever it had, and the stylist will not have made it an image-led hero).
        founder = founder_identity(pkg.pages, ctx)
        if founder is not None:
            for i, page in enumerate(pkg.pages):
                a = assignments[i]
                if not (a and a.treatment):
                    continue
                treatment = treatment_engine.get_treatment(a.treatment)
                if treatment is None:
                    continue
                # inject for image-led treatments AND for the ABOUT page on any
                # treatment: with the A3 hero suspended (mid-deck A3 breaks
                # Chromium A4 sizing), the About page renders via a text
                # treatment that can still SHOW the founder portrait when the
                # identity exists. A treatment with no image slot ignores it.
                if not (treatment.needs_image
                        or str(page.get("st_type") or "").upper() == "ST-05"):
                    continue
                # only inject when the page has no portrait of its own
                if treatment_engine.adapt(page, ctx).image:
                    continue
                slots = list(page.get("slots") or [])
                slots.append({
                    "slot_id": "founder",
                    "status": "resolved",
                    "path": founder["path"],
                })
                page["slots"] = slots
                data = dict(page.get("data") or {})
                data.setdefault("author", founder["author"])
                page["data"] = data

    # ---- dispatch each page (never crash) ----
    # (treatment, format) actually rendered per page; legacy pages record (None,
    # None) so they are stamped + sized as normal pages.
    fragments: list[tuple[dict, PageFragment]] = []
    page_treatments: list[tuple[Optional[str], Optional[str]]] = []
    for i, page in enumerate(pkg.pages):
        assignment = assignments[i] if assignments is not None else None
        frag, used_t, used_f = _render_one_page(
            page, ctx, assignment, treatments, warnings=warnings
        )
        # ---- CONTENT-QC gate (2026-07-04 full-deck defects D1/D2) ----
        # The overflow gate counts sheets; it cannot see a leaked Python value
        # PRINTED on a page. Two PRECISE structural signatures on the RAW html:
        #   (a) an element whose ENTIRE content is a bare singleton (None/True/
        #       False) -> a null/bool that stringified from `{{ field }}`. Matching
        #       ">None<" (not the word inside prose) so legitimate copy like "None
        #       of the agencies delivered this" does NOT false-positive.
        #   (b) a leaked CONTAINER repr: a list of quoted strings "['..." / '["...',
        #       a str-key dict "{'..." / '{"...', or an int-key dict "{0:". The old
        #       `\{\s*['"]` missed lists and numeric-key dicts entirely.
        _html = frag.html or ""
        # M1 scans RAW html for a singleton that is an element's WHOLE content
        # (">None<"). M2 (container reprs) scans the TAG-STRIPPED visible text, NOT
        # the raw html, so a legit ATTRIBUTE value (e.g. style="url('data:...')",
        # data-json="{'a':1}") inside a <tag ...> cannot false-positive and block
        # shipping; a leaked list/dict is visible TEXT, so it still fires.
        _text = re.sub(r"<[^>]+>", " ", _html)
        if re.search(r">\s*(?:None|True|False)\s*<", _html):
            warnings.append(
                f"CONTENT-QC slot {page.get('slot')} ({page.get('st_type')}): "
                f"a bare Python singleton (None/True/False) rendered on the page "
                f"(null/bool leaked to print)"
            )
        if re.search(r"""[\[{]\s*['"]|\{\s*\d+\s*:""", _text):
            warnings.append(
                f"CONTENT-QC slot {page.get('slot')} ({page.get('st_type')}): "
                f"raw list/dict repr rendered on the page (unformatted data)"
            )
        fragments.append((page, frag))
        # Page-format wiring. A TREATED page uses the format its treatment set
        # (used_f). The package `page_format` opt-in only applies on the LEGACY
        # path (treatments OFF): under treatments, an untreated page fell back to
        # the legacy A4 pattern precisely because no A3 treatment fit, so honoring
        # a package page_format="a3" here would stamp format-a3 on an A4-designed
        # fragment and mis-size it onto the wide sheet (contradicting
        # _render_one_page's "not mis-sized to A3" guarantee). Keep it A4.
        _pkg_format = page.get("page_format") if not treatments else None
        page_treatments.append((used_t, used_f or _pkg_format))

    # ---- shared head + deduped fragment CSS ----
    # Resolve the generated report ground (frosted TEXTURE preferred, then the
    # atmospheric gradient) ONCE and hand it to the head so it grounds EVERY light
    # page — replacing the dull flat --color-ground the user flagged. Renderer-owned
    # placement, fed by the preprocessor report asset; graceful to grain-only when
    # the package carries no such asset.
    report_ground_uri = ctx.resolve_report_asset(
        ("background_texture", "atmospheric_gradient"),
        ("texture", "gradient", "background"),
    ) or ""
    head = shared_head_css(pkg.brand, FONT_DIR, pkg.axes,
                           report_ground_uri=report_ground_uri, engine=engine)
    seen: set[str] = set()
    css_blocks: list[str] = []
    for _, frag in fragments:
        if frag.css and frag.css not in seen:
            seen.add(frag.css)
            css_blocks.append(frag.css)

    # Persistent header band (running element) — prepended ONCE under weasyprint;
    # it floats into every page's @top-center margin box. Chromium has no
    # position:running (the div would render in-flow as junk before page 1), so
    # its chrome comes from the @page margin-box strings in shared_head_css.
    # US-505/506 (Richard grammar): the dark beats' watermark was the brand's
    # first letter ("A") — the audit called it "cheap generic decorative art".
    # Richard's actual signature device is the GIANT low-contrast SECTION
    # NUMBER (niklas "01"/"02"/"03" overlapping the dark panel). The watermark
    # is now the page's logical index, zero-padded. The value is passed per
    # section (index-aware), not a single brand letter.
    _burl = getattr(pkg.brand, "company_url_display", "") or ""
    _chrome = (
        pkg.brand.company_name_short or "",
        _burl,
        "",  # US-501: no booking CTA in the header
    )
    sections_html = "".join(
        _section(page, frag, i,
                 ghost_letter=f"{i + 1:02d}",
                 treatment=page_treatments[i][0], page_format=page_treatments[i][1],
                 chrome=_chrome)
        for i, (page, frag) in enumerate(fragments)
    )
    body = sections_html if engine == "chromium" else (
        _page_header(pkg.brand) + sections_html
    )
    _, data_attrs = compile_tokens(pkg.brand, pkg.axes)
    attr_str = "".join(f' {k}="{v}"' for k, v in data_attrs.items())
    from templating import get_env
    html_doc = get_env().get_template("base.html.jinja").render(
        html_attrs=attr_str,
        head_css=head,
        fragment_css="".join(css_blocks),
        body=body,
    )

    # ---- HTML -> PDF (engine branch) ----
    pdf_path = output_dir / "report.pdf"
    if engine == "chromium":
        # Chromium print-to-PDF via Playwright: the engine that renders the FULL
        # premium depth vocabulary (soft shadows, conic gradients, blends, blur)
        # WeasyPrint silently drops. Then the Layer-3 Ghostscript FLATTEN pass
        # (PDF 1.3 @300dpi) composites Chromium's transparency groups so the PDF
        # renders identically in EVERY viewer (Quartz/Preview chokes on the raw
        # soft-mask groups — verified). Fonts/assets are absolute file:// URIs,
        # so the written HTML resolves from anywhere.
        import shutil
        import subprocess
        html_path = output_dir / "report.html"
        html_path.write_text(html_doc, encoding="utf-8")
        raw_pdf = output_dir / "report_print.pdf"
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            pg = browser.new_page()
            pg.goto(html_path.resolve().as_uri())
            # FRAGMENT-OVERFLOW GUARD (the silent-shrink trigger). When ANY
            # section's box exceeds its sheet, Chromium's mixed/named-page
            # print SCALES THE WHOLE DOCUMENT down to fit (empirically
            # reproduced: 0.4mm of frame borders on 297mm bleed sections
            # shrank every deck to ~84.6 percent, silently, for weeks). The
            # spill QC below cannot see that failure mode (the shrink PREVENTS
            # the spill), so measure the fragments here, before printing.
            pg.emulate_media(media="print")
            _over = pg.evaluate(
                """() => {
                  const mm = (px) => Math.round(px * 25.4 / 96 * 10) / 10;
                  const out = [];
                  for (const s of document.querySelectorAll('section.page')) {
                    const h = s.getBoundingClientRect().height;
                    const cls = s.className;
                    const a3 = cls.includes('format-a3');
                    const sheet = a3 ? 297 : 297;  /* both formats are 297mm tall */
                    /* rail sections carry the SECTION-level .tp-rail stamp
                       (the inner .ef-grid.has-rail marker is not visible in
                       the section className). */
                    const bleed = /st-01|st-31|st-32|st-03|treatment-a4_case_study/.test(cls)
                      || s.hasAttribute('data-page-mode') || cls.includes('tp-rail');
                    const budget = bleed ? 297 : 261.4;  /* chromed content box + frame */
                    if (mm(h) > budget + 0.5) out.push(cls.split(' ').slice(0, 3).join(' ') + ': ' + mm(h) + 'mm > ' + budget + 'mm');
                  }
                  return out;
                }"""
            )
            for _o in _over:
                warnings.append(
                    "fragment overflow (silent-shrink trigger): " + _o
                )
            pg.pdf(path=str(raw_pdf), print_background=True,
                   prefer_css_page_size=True)
            browser.close()
        gs = shutil.which("gs")
        if gs:
            # A gs failure must not discard the finished Chromium PDF: ship the
            # unflattened raw file with a warning instead of aborting the render.
            try:
                subprocess.run(
                    [gs, "-dBATCH", "-dNOPAUSE", "-sDEVICE=pdfwrite",
                     "-dCompatibilityLevel=1.3", "-r300", "-dPDFSETTINGS=/printer",
                     "-dColorConversionStrategy=/LeaveColorUnchanged",
                     "-o", str(pdf_path), str(raw_pdf)],
                    check=True, capture_output=True,
                )
            except subprocess.CalledProcessError as e:
                shutil.copy(raw_pdf, pdf_path)
                warnings.append(
                    "ghostscript flatten FAILED (exit %s): shipping the "
                    "unflattened Chromium PDF; Preview/Quartz may show gray "
                    "boxes" % e.returncode
                )
        else:
            shutil.copy(raw_pdf, pdf_path)
            warnings.append("ghostscript (gs) not found: transparency NOT "
                            "flattened; Preview/Quartz may show gray boxes")
    else:
        # WeasyPrint path. FontConfiguration is required for @font-face faces to
        # register reliably (WeasyPrint best practice + Railway/Linux portability).
        font_config = FontConfiguration()
        weasyprint.HTML(string=html_doc, base_url=str(HERE)).write_pdf(
            str(pdf_path), font_config=font_config
        )

    # ---- rasterize PNGs (best-effort) ----
    png_paths: list[Path] = []
    try:
        import fitz  # PyMuPDF

        # G10 (determinism): Chromium and WeasyPrint stamp wall-clock creation
        # metadata, so identical inputs produce different PDF bytes. Pin the
        # metadata to a fixed instant before rasterizing / shipping. fitz
        # refuses to save over the open source path, so write a temp file and
        # atomically replace.
        import tempfile as _tempfile

        with fitz.open(pdf_path) as _meta_doc:
            _meta = dict(_meta_doc.metadata)
            _meta.update(
                {
                    "creator": "DMC renderer",
                    "producer": "DMC renderer",
                    "creationDate": "D:20000101000000Z",
                    "modDate": "D:20000101000000Z",
                }
            )
            _meta_doc.set_metadata(_meta)
            _tmp = pdf_path.with_suffix(".pdf.meta-tmp")
            _meta_doc.save(_tmp, garbage=4, clean=True, deflate=True, no_new_id=True)
        _tmp.replace(pdf_path)

        doc = fitz.open(pdf_path)
        for i, pg in enumerate(doc):
            pix = pg.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            png = output_dir / f"report-p{i + 1}.png"
            pix.save(str(png))
            png_paths.append(png)
        doc.close()
    except ImportError:
        warnings.append("PyMuPDF (fitz) unavailable; PNGs skipped")

    # ---- overflow validator (advisory) ----
    overflow: list[str] = []
    if engine == "chromium":
        # AUTHORITATIVE under deterministic pagination: every section is exactly
        # one sheet, so physical pages > logical pages == some section spilled.
        if png_paths and len(png_paths) != len(fragments):
            overflow.append(
                f"physical pages {len(png_paths)} != logical pages "
                f"{len(fragments)}: a section overflowed its sheet"
            )
    else:
        for i, (page, frag) in enumerate(fragments):
            # Skip the A4-box overflow check for treated pages: a page that a
            # treatment rendered (page_treatments[i][0] is not None) has its own
            # layout contract, and an A3 page (format "a3") uses a wider box, so
            # the A4-sized check would false-flag them. Legacy A4 pages still run.
            used_t, used_f = page_treatments[i]
            if used_t is not None or used_f == "a3":
                continue
            one_doc = (
                "<!DOCTYPE html><html lang=\"de\"><head><meta charset=\"utf-8\">"
                f"<style>{head}{frag.css}</style></head>"
                f"<body>{_section(page, frag, i)}</body></html>"
            )
            try:
                if check_overflow(one_doc, base_url=str(HERE)):
                    overflow.append(f"slot {page.get('slot')} ({page.get('st_type')}) overflow")
            except Exception as exc:  # noqa: BLE001 — advisory only
                warnings.append(f"overflow check failed for slot {page.get('slot')}: {exc!r}")

    # ---- accent-budget validator (stub today; seam is real) ----
    ab = AccentBudgetValidator(brand=pkg.brand).validate(
        rendered_html=html_doc, rendered_pdf_pages=[]
    )

    return RenderResult(
        pdf_path=pdf_path,
        png_paths=png_paths,
        page_count=len(fragments),
        overflow=overflow,
        accent_budget_passed=ab.passed,
        warnings=warnings,
    )
