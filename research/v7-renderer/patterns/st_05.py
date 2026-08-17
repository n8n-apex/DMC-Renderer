"""Pattern for ST-05 — ABOUT / "über uns" (Plan B rebuild, grammar P-3).

DATA-PREP ONLY. This module reads the package `page` dict, resolves an OPTIONAL
founder-portrait + any partner-logo assets, shapes a context dict, and renders
`templates/st_05.html.jinja` (which composes the atomic macro library on a
token-themed layout, `styles/st_05.css`). The returned PageFragment.html is that
rendered string; the .css is the layout sheet.

WHY this shape (vs the old hand-built f-string CSS):
  - Brand-agnostic by construction: the template + layout CSS contain ZERO
    client literals (no hex, no font family, no client name). Colors + fonts
    arrive at render time via the token `:root` (compile_tokens) — the heading
    sizes off `var(--font-display)`, which resolves to the SERIF face when the
    brand's axis is headline_type=serif (the apex deck IS serif). Set against the
    sans `var(--font-body)` body prose, that serif/sans pairing is the §18 contrast.
  - The device LOOK (stat_strip "in Zahlen" big numbers; logo_wall grayscale
    "bekannt aus" tiles; media_figure founder plate; section_label rules) lives in
    the `c-` classes (components.css, already in the shared <head>); this pattern
    only feeds the macros DATA and positions them.

DATA CONTRACT (preserved from the prior pattern — fields on page["data"]):
  title (the heading), body (the about prose, markdown), stats[] (list of
  {value, label} dicts — the "in Zahlen" trio), partners[] (list of partner NAME
  strings — the "bekannt aus" wall), credibility_points[] (list of proof-point
  strings). Plain-string or absent fields degrade gracefully (no heading / no body
  / no stats / no logo wall / no credibility list).

POSITIONING PANEL (DNA §C3/§D — the About page anchors on a DARK panel):
  Richard's About pages put the positioning STATEMENT on a dark "authority" panel
  (navy/primary/ink ground + on-primary text), NOT a pale tint. So the FIRST
  paragraph of `body` (the thesis / positioning statement) renders on a dark panel
  (.ab-lead, --color-primary ground via the page CSS) at the top of the body; the
  REMAINING paragraphs flow as normal prose beneath it. The split is on the first
  blank-line boundary of the raw markdown (preprocess splits paragraphs there), so
  each half is preprocessed independently. A single-paragraph body → just the
  panel (no prose tail); an empty body → no panel at all (graceful).

PHOTOS — v2.0 `slots[]` (DNA §C2/§C4; all graceful, the apex slot states vary):
  - About/team PORTRAIT: ctx.slot_uri(page, "about_portrait") (the v2.0 single-
    photo primitive). Resolved → framed in the sidebar via media_figure; absent
    (apex: status "absent") → NO portrait block.
  - PROOF gallery (NEW, DNA §C4 social-proof): ctx.slot_uris(page, "proof") — the
    resolved credibility/deal photos as a framed full-COLOR row via the
    proof_gallery macro under a "Referenzen" label. Empty → nothing rendered.
    (apex: THREE resolved proof photos.)
  - Partner LOGOS ("bekannt aus" wall): ctx.slot_uris over the logo slot_ids
    (press_logo / client_logo / about_logo), in that order. Resolved → grayscale
    logo wall of the resolved image URIs; none resolved (apex: all "absent") → the
    logo wall DEGRADES GRACEFULLY to a restrained text fallback of the partner
    NAMES (it never fabricates logo art).

The German eyebrow kicker (Über uns), the stat label (In Zahlen), the proof label
(Referenzen), and the logo wall label (Bekannt aus) are CONTENT labels for this
report TYPE (not client-specific) — module constants passed to the template as
data.

History (Plan B → Phase 4b): replaced the prior monolithic f-string render with a
data-prep → Jinja split; then Phase 4b moved photo sourcing onto the v2.0 slots[]
(about_portrait / proof / logo slots via ctx.slot_uri[s]) — adding the §C4 proof
gallery + the §C3 dark positioning panel — closing DNA gaps #2 (social proof) and
#4 (pale panels). Earlier history documented in git.
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
_CSS_PATH = Path(__file__).resolve().parent.parent / "styles" / "st_05.css"
_CSS = _CSS_PATH.read_text(encoding="utf-8")

# Content labels for this report TYPE (not client-specific).
_KICKER = "Über uns"
_STATS_LABEL = "In Zahlen"
_PROOF_LABEL = "Referenzen"
_TESTIMONIALS_LABEL = "Das sagen unsere Kunden"
_LOGOS_LABEL = "Bekannt aus"

# v2.0 slot_ids, in display order, that feed the "bekannt aus" logo wall when
# resolved (graceful: none resolved → the partner-NAME text fallback).
_LOGO_SLOTS: tuple[str, ...] = ("press_logo", "client_logo", "about_logo")


def _split_lead(body: str) -> tuple[str, str]:
    """Split the about prose into (lead, rest) at the first paragraph boundary.

    The LEAD (the positioning statement / thesis) rides the dark authority panel;
    the REST flows as normal prose beneath it. Splits the RAW markdown on the
    first blank-line boundary (where preprocess splits paragraphs), so each half
    preprocesses independently. A single-paragraph body → (whole body, ''); an
    empty body → ('', '').
    """
    text = (body or "").strip()
    if not text:
        return "", ""
    parts = re.split(r"\n\n+", text, maxsplit=1)
    lead = parts[0].strip()
    rest = parts[1].strip() if len(parts) > 1 else ""
    return lead, rest


def render(page: dict, ctx: RenderContext) -> PageFragment:
    """Render the ST-05 about page as a PageFragment.

    Data-prep → render templates/st_05.html.jinja. Head-level CSS lives in the
    shared head (assembler); this returns only the page body markup + the
    ST-05-scoped layout CSS.
    """
    d: dict = page.get("data") or {}

    # ---- photos from the v2.0 slots[] (all graceful) ----
    # Founder/team portrait — the single-photo primitive (absent → no block).
    portrait_uri = ctx.slot_uri(page, "about_portrait") or ""
    # Proof gallery — the resolved credibility/deal photos (DNA §C4).
    proof_photos = ctx.slot_uris(page, "proof")
    # Partner logos for the "bekannt aus" wall, in slot order across the logo
    # slots; none resolved → the partner-NAME text fallback below carries it.
    logos: list[str] = []
    for slot_id in _LOGO_SLOTS:
        logos.extend(ctx.slot_uris(page, slot_id))

    # ---- testimonial cards (DNA §C4): designed client-quote graphics (real client
    # quote + metric + name, e.g. scraped from the founder's socials). Shown WHOLE
    # (not cropped) as the page's social proof. Graceful: none → falls back to the
    # proof-photo gallery in the template. Brand-agnostic (paths only). ----
    testimonials: list[str] = []
    for rel in (d.get("testimonials") or []):
        if not str(rel).strip():
            continue
        p = ctx.resolve_asset(str(rel))
        if p is not None:
            testimonials.append(p.as_uri())

    # ---- positioning statement (lead) → dark panel; rest → prose beneath ----
    lead_raw, rest_raw = _split_lead(d.get("body", ""))

    # ---- stats → the "in Zahlen" trio (dicts {value, label} OR "label: value") ---
    stats: list[dict[str, str]] = []
    for m in (d.get("stats") or []):
        if isinstance(m, dict):
            value, label = m.get("value", ""), m.get("label", "")
        elif isinstance(m, str) and ":" in m:
            label, value = (s.strip() for s in m.split(":", 1))
        else:
            value, label = str(m), ""
        if value or label:
            stats.append({"value": value, "label": label})

    # ---- partner names (the "bekannt aus" text fallback when no logo art) ----
    partner_names = [str(p) for p in (d.get("partners") or []) if str(p).strip()]

    # ---- credibility proof points ----
    credibility = [str(c) for c in (d.get("credibility_points") or []) if str(c).strip()]

    template = get_env().get_template("st_05.html.jinja")
    html = template.render(
        kicker=_KICKER,
        title=d.get("title", ""),
        lead_html=preprocess_body(lead_raw),
        body_html=preprocess_body(rest_raw),
        portrait_uri=portrait_uri,
        portrait_alt=d.get("title", ""),
        portrait_caption="",
        stats=stats,
        stats_label=_STATS_LABEL if stats else "",
        credibility=credibility,
        testimonials=testimonials,
        testimonials_label=_TESTIMONIALS_LABEL if testimonials else "",
        proof_photos=proof_photos,
        proof_label=_PROOF_LABEL if proof_photos else "",
        logos=logos,
        partner_names=partner_names,
        logos_label=_LOGOS_LABEL if (logos or partner_names) else "",
        # US-609: continuation-aware composition — the About's identity/proof
        # pages fill the sheet (the last band pins via margin-top:auto).
        continuation_role=str(page.get("continuation_role") or ""),
    )
    return PageFragment(html=html, css=_CSS)
