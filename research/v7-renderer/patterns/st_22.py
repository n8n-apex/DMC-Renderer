"""Pattern for ST-22 — COLLABORATION / process (Plan B rebuild, P-10/P-13).

DATA-PREP ONLY. This module reads the package `page` dict, resolves a
collaboration banner image, shapes the numbered process steps, and renders
`templates/st_22.html.jinja` (which composes the atomic macro library on a
token-themed layout, `styles/st_22.css`). The returned PageFragment.html is that
rendered string; the .css is the layout sheet's contents.

WHY this shape (vs the old hand-built f-string CSS):
  - Brand-agnostic by construction: the template + layout CSS contain ZERO
    client literals (no hex, no font family, no client name). Colors + fonts
    arrive at render time via the token `:root` (compile_tokens) — the heading
    sizes off `var(--font-display)`, which resolves to the SERIF face when the
    brand's axis is headline_type=serif (the apex deck IS serif).
  - The device LOOK (media_figure banner + the horizontal_flow step strip) lives
    in the `c-` classes (components.css, already in the shared <head>); this
    pattern only feeds the macros DATA and positions them.

DATA CONTRACT (preserved from the prior pattern — fields on page["data"]):
  title, body (intro prose), steps[] (list of {n, title, body, dauer} dicts;
  `n` / `dauer` / `body` optional — `n` falls back to the loop index). Steps are
  the "Schritt 1 → N" process. A collaboration banner photo: page["assets"] entry
  (image_type background/scene/photo) OR — when the page carries none, as the
  apex fixture's ST-22 does — a package report_asset (extra_wide / extra_square /
  any background/scene) so the header is a real photo banner, not an empty plate.

Layout (reference §B, checklist #9 full-width banner + #12 horizontal flow):
  a FULL-WIDTH banner photo header, then a serif heading + intro lede, then a
  horizontal numbered step flow (horizontal_flow — accent connectors + Dauer
  durations). The banner bleeds the full CONTENT width (not the physical sheet —
  this is a chromed content page, the persistent header/folio stay).

Graceful: a missing banner asset leaves the media_figure's token --color-surface
placeholder under the heading (never a broken image); empty steps drop the flow;
empty data still yields a non-empty fragment.

History (Plan B): replaced the prior monolithic f-string render (hand-written
.co-*/.hflow CSS with hardcoded color + font-family literals + the legacy
_components.horizontal_flow) with this data-prep → Jinja-template split using the
shared c-hflow macro + a full-width banner. Earlier history documented in git.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow flat imports from the chassis package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from preprocess import preprocess_body  # noqa: E402
from templating import get_env  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402

# Layout CSS lives in a sibling sheet so it's auditable by the brand-agnostic
# guard (tokens only). Read once at import; returned verbatim as fragment.css.
_CSS_PATH = Path(__file__).resolve().parent.parent / "styles" / "st_22.css"
_CSS = _CSS_PATH.read_text(encoding="utf-8")

# Page-level banner asset preference (a collaboration / team / handshake photo).
_BANNER_IMAGE_TYPES = ("background", "scene", "photo")
# When the page carries no banner of its own, fall back to a package report_asset:
# a wide image reads best as a banner, then the square, then any background/scene.
_REPORT_BANNER_SLOTS = ("extra_wide", "extra_square")
_REPORT_BANNER_TYPES = ("background", "scene", "gradient", "texture")


def _banner_uri(page: dict, ctx: RenderContext) -> str:
    """Resolve the collaboration banner image URI (graceful '' when none).

    Prefers a page-level asset; falls back to a package report_asset (the apex
    ST-22 carries no page asset) so the header is a real photo banner.
    """
    for a in (page.get("assets") or []):
        if a.get("image_type") in _BANNER_IMAGE_TYPES and a.get("path"):
            p = ctx.resolve_asset(a["path"])
            if p is not None:
                return p.as_uri()
    return ctx.resolve_report_asset(_REPORT_BANNER_SLOTS, _REPORT_BANNER_TYPES) or ""


def render(page: dict, ctx: RenderContext) -> PageFragment:
    """Render the ST-22 collaboration page as a PageFragment.

    Data-prep → render templates/st_22.html.jinja. Head-level CSS lives in the
    shared head (assembler); this returns only the page body markup + the
    ST-22-scoped layout CSS.
    """
    d: dict = page.get("data") or {}

    # ---- collaboration banner (graceful: '' → media_figure placeholder) ----
    banner_uri = _banner_uri(page, ctx)

    # ---- steps → horizontal_flow cells ({n, title, body, dauer}). The body is a
    # SHORT plain string in the flow box; `n` falls back to the loop index. The
    # fill variant (vertical timeline) reuses the SAME shaped step dicts — its
    # template renders each step as a stacked timeline ROW instead of a flow box. ----
    steps: list[dict] = []
    for i, s in enumerate(d.get("steps") or [], start=1):
        if isinstance(s, dict):
            steps.append({
                "n": s.get("n") or i,
                "title": s.get("title", ""),
                "body": s.get("body", ""),
                "dauer": s.get("dauer", ""),
            })
        else:
            steps.append({"n": i, "title": str(s), "body": "", "dauer": ""})

    # ---- layout variant (per-page hint) ----------------------------------
    # "standard" (DEFAULT, unchanged): a full-width banner, then heading + intro,
    #   then a single HORIZONTAL flow strip of the Schritt 1 → N boxes. The strip
    #   sits in the top ~40% of the sheet and leaves a big empty bottom band (the
    #   N08 dead-space flag fires: largest contiguous empty band > 20% of height).
    # "fill": a VERTICAL TIMELINE — the numbered steps stacked DOWN the page,
    #   joined by a vertical accent spine with numbered nodes, each step a row
    #   (number node + title + body + Dauer), the rows distributed to FILL the
    #   full content height. Keeps the title + intro at the top. This fills the
    #   sheet on one physical page and removes the dead band. Brand-agnostic:
    #   tokens only; this pattern only feeds DATA + the variant flag.
    layout_variant = page.get("layout_variant", "standard")
    if layout_variant not in ("standard", "fill"):
        layout_variant = "standard"

    template = get_env().get_template("st_22.html.jinja")
    viz = d.get("viz")
    viz = viz if isinstance(viz, list) and viz else None

    html = template.render(
        layout_variant=layout_variant,
        banner_uri=banner_uri,
        banner_alt=d.get("title", ""),
        title=d.get("title", ""),
        intro_html=preprocess_body(d.get("body", "")),
        steps=steps,
        viz=viz,
    )
    return PageFragment(html=html, css=_CSS)
