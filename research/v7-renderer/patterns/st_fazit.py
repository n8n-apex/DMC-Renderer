"""Pattern for ST-FAZIT — summary / Zusammenfassung page (Plan B rebuild, P-9).

DATA-PREP ONLY. This module reads the package `page` dict, shapes a context
dict, and renders `templates/st_fazit.html.jinja` (which composes the atomic
macro library on a token-themed layout, `styles/st_fazit.css`). The returned
PageFragment.html is that rendered string; the .css is the layout sheet's
contents.

WHY this shape (vs the old hand-built f-string CSS):
  - Brand-agnostic by construction: the template + layout CSS contain ZERO
    client literals (no hex, no font family, no client name). Colors + fonts
    arrive at render time via the token `:root` (compile_tokens) — the summary
    title + the These statement size off `var(--font-display)`, which resolves to
    the SERIF face when the brand's axis is headline_type=serif (the apex deck IS
    serif).
  - The closing devices (the These pull-statement, the cost block, the giant URL
    band) live in the `c-these` / `c-cost-block` / `c-url-band` classes
    (components.css, already in the shared <head>); this pattern only feeds the
    macros DATA and positions them.

DATA CONTRACT (preserved from the prior pattern — fields on page["data"]):
  title (the summary headline → header band), body (the recap synthesis prose),
  these (the thesis pull-statement), kosten_des_nichtstuns (the cost-of-inaction
  copy → the cost block's supporting note), cta_url (the closing giant URL band).
  Plus brand.qr_target_url / brand.company_url_display as the URL fallback so the
  page always closes with a CTA.

Body fields go through preprocess.preprocess_body (markdown → HTML).

The German content labels (the eyebrow kicker, the cost-block label, the URL
band kicker) are CONTENT labels for this report type — module constants here
(not scattered, not client-specific), passed to the template as data.

A NORMAL (non-bleed) content page (unlike the cover / breathing pages): the
header band, recap body, These, cost block and URL band stack inside the chromed
261mm content box.

History (Plan B): replaced the prior monolithic f-string render (hand-written
.fz-* CSS with hardcoded color + font-family literals baked into the pattern,
plus the legacy dark_cta_panel) with this data-prep → Jinja-template split + the
new these_statement / cost_block / url_band macros. Earlier history in git.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Allow flat imports from the chassis package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from preprocess import preprocess_body  # noqa: E402
from templating import get_env  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402

# Layout CSS lives in a sibling sheet so it's auditable by the brand-agnostic
# guard (tokens only). Read once at import; returned verbatim as fragment.css.
_CSS_PATH = Path(__file__).resolve().parent.parent / "styles" / "st_fazit.css"
_CSS = _CSS_PATH.read_text(encoding="utf-8")

# Content labels for this report TYPE (not client-specific).
_EYEBROW = "Zusammenfassung"
_KOSTEN_LABEL = "Kosten des Nichtstuns"
_CTA_LABEL = "Jetzt handeln"

# A lead figure for the cost block: the FIRST percentage / range in the
# cost-of-inaction copy (e.g. "25-30%") reads as the big figure that anchors the
# block; the prose then sets as the supporting note. Graceful: no figure → the
# block leads with the label + note alone (still a prominent cost plate).
_LEAD_FIGURE_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:[-–]\s*\d+(?:[.,]\d+)?)?\s*%")


def _lead_figure(text: str) -> str:
    """Pull the first percentage/range from the copy (the cost block's big figure)."""
    m = _LEAD_FIGURE_RE.search(text or "")
    return m.group(0).replace(" ", "") if m else ""


def render(page: dict, ctx: RenderContext) -> PageFragment:
    """Render the ST-FAZIT summary page as a PageFragment.

    Data-prep → render templates/st_fazit.html.jinja. Head-level CSS
    (@page/@font-face/:root/body + the component `c-` classes) lives in the
    shared head (assembler); this returns only the page body markup + the
    ST-FAZIT-scoped layout CSS.
    """
    d: dict = page.get("data") or {}

    # data-viz PRESET layer: data['viz'] (a list) → rendered via the dispatch in
    # the template's proof band. Coerce to None unless a non-empty list (graceful).
    viz = d.get("viz")
    viz = viz if isinstance(viz, list) and viz else None

    # The cost-of-inaction copy is the cost block's supporting NOTE (the figure
    # itself stays the label-led prominence of the block); graceful when absent.
    kosten = (d.get("kosten_des_nichtstuns") or "").strip()

    # The closing URL: the page's own cta_url, falling back to the brand's display
    # URL / QR target so the summary always closes with a scannable CTA.
    url = (d.get("cta_url") or ctx.brand.company_url_display
           or ctx.brand.qr_target_url or "").strip()
    # Show the BARE DOMAIN (scheme + trailing slash stripped) — Richard prints
    # "apex-consulting.ai", not "https://…/" (matches the ST-03 back cover). The
    # url_band --on-ground now sizes it proportionately (--type-h2), not oversized.
    for _scheme in ("https://", "http://"):
        if url.lower().startswith(_scheme):
            url = url[len(_scheme):]
            break
    url = url.rstrip("/")

    # ---- layout variant (per-page hint) ----------------------------------
    # "standard" (DEFAULT, unchanged): the header band, recap body, These, cost
    #   block and URL band stack at the TOP of the 261mm content box. On the apex
    #   summary this UNDER-FILLS — a large contiguous empty band sits in the bottom
    #   ~half (the quality loop's N08 dead-space flag fires, gap > 0.20).
    # "fill": the closing-page composition grounded in the design DNA (§C3 — the
    #   DARK authority panel is the rhythm beat; the CTA URL is a full-width
    #   saturated stripe where the URL is the single biggest element). The These
    #   thesis sets as a large accent-ruled pull-statement, the cost-of-inaction
    #   as an OVERSIZED big-number stat, and a FULL-WIDTH DARK CTA band is PINNED
    #   to the BOTTOM carrying the cta_url as the page's biggest element (white/
    #   accent on the dark ground). The dark band fills the lower portion and ends
    #   the report on a strong note — that bottom fill is what removes the dead
    #   band. Brand-agnostic: tokens only (the pattern only positions DATA).
    layout_variant = page.get("layout_variant", "standard")
    if layout_variant not in ("standard", "fill"):
        layout_variant = "standard"

    # ---- founder sign-off (DNA §C2: close the report on the human anchor) ----
    # The closing page carries the founder SLOT (the preprocessor routes the founder
    # portrait here). The fill variant ends with the founder's face + a personal
    # byline in the dark CTA strip — a signed close, the way the reference decks end.
    # Graceful: no founder slot → no avatar (the CTA carries the strip alone); no
    # author → the avatar shows with the brand wordmark only. Brand-agnostic.
    founder_uri = ctx.slot_uri(page, "founder")
    author = d.get("author") or {}
    author_name = str(author.get("name") or "").strip()
    author_role = str(author.get("role") or "").strip()

    # navy-stone material for the viz-island depth treatment (graceful -> token navy)
    panel_texture_uri = ctx.resolve_report_asset(("panel_texture",), ("panel_texture",)) or ""

    template = get_env().get_template("st_fazit.html.jinja")
    html = template.render(
        layout_variant=layout_variant,
        viz=viz,
        panel_texture_uri=panel_texture_uri,
        eyebrow=_EYEBROW,
        title=d.get("title", ""),
        # US-607: the physical-page plan for continuation furniture.
        page_plan={
            "page_id": page.get("page_id"),
            "section_id": page.get("section_id"),
            "continuation_index": page.get("continuation_index") or 1,
            "section_page_count": page.get("section_page_count") or 1,
            "continuation_role": str(page.get("continuation_role") or ""),
        },
        body_html=preprocess_body(d.get("body", "")),
        these=(d.get("these") or "").strip(),
        founder_uri=founder_uri or "",
        author_name=author_name,
        author_role=author_role,
        wordmark=ctx.brand.company_name_short,
        kosten_label=_KOSTEN_LABEL,
        # The cost block leads with a BIG figure (the lead percentage pulled from
        # the cost-of-inaction copy — e.g. "25-30%") over the label, with the prose
        # as the supporting note. When no figure exists the label + note carry the
        # block (the cost here is the price of INACTION).
        kosten_value=_lead_figure(kosten),
        kosten_note=kosten,
        cta_label=_CTA_LABEL,
        url=url,
    )
    return PageFragment(html=html, css=_CSS)
