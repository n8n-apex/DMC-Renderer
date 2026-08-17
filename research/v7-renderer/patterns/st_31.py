"""Pattern for ST-31 / ST-32 — ATEMSEITE / breathing page (Plan B rebuild).

DATA-PREP ONLY. This module reads the package `page` dict, resolves the
atmospheric ground image, picks a geometric-overlay variant, shapes a context
dict, and renders `templates/st_31.html.jinja` (which composes the geo_shapes
overlay on a token-themed full-bleed layout, `styles/st_31.css`). The returned
PageFragment.html is that rendered string; the .css is the layout sheet's
contents. ST-32 re-exports this render (the two ST types are the same device).

WHY this shape (vs the old hand-built f-string CSS):
  - Brand-agnostic by construction: the template + layout CSS contain ZERO
    client literals (no hex, no font family, no client name). Colors + fonts
    arrive at render time via the token `:root` (compile_tokens); a short
    optional statement sizes off var(--font-display) (serif via the axis).
  - The breathing page is a DELIBERATE atmospheric PAUSE: a full-page ground (the
    fal-generated brand texture / gradient asset) bleeding edge-to-edge via the
    SAME full-bleed technique the cover uses (the suppressed named `@page bleed`,
    declared in the shared head), with low-opacity token-colored geometric accent
    shapes (the geo_shapes macro — a quiet logo motif) overlaid, and little/no
    text. This fixes the prior complaint that the texture sat awkwardly on a
    content-hugging box — now it is a striking full-bleed pacing page.

DATA CONTRACT (preserved from the prior pattern — fields on page["data"]):
  phrase (OPTIONAL short centered statement; most breathing pages carry none —
  data is {}). Atmospheric ground asset: page["assets"] entry with image_type in
  {gradient, texture, background, scene} (the breathing_bg_* slots) OR, when the
  page carries none, a package report_asset (atmospheric_gradient /
  background_texture / extra_wide / extra_square).

FULL-BLEED: the breathing section assigns itself the suppressed named `@page
bleed` (margin:0, header band + folio removed) via `.page.st-31 { page: bleed }`
in styles/st_31.css. The named page itself is declared in the shared head
(assembler.shared_head_css) — @page rules cannot live in a fragment.

Graceful: a missing atmospheric asset falls back to a token gradient ground
(--color-primary → --color-ink) painted by the layout CSS, so the page is never
blank and never a broken image. An empty `phrase` simply drops the statement
(the ground + geometric overlay carry the page alone — a true breathing pause).

History (Plan B): replaced the prior content-box texture render (.br-page with a
hardcoded font/color literal + an awkward min-height:232mm box that left the
texture sitting inside the chromed content area) with this data-prep →
Jinja-template split + a true full-bleed atmospheric page (the cover's named-page
technique) + a token-colored geometric overlay. Earlier history documented in git.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow flat imports from the chassis package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from templating import get_env  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402

# Layout CSS lives in a sibling sheet so it's auditable by the brand-agnostic
# guard (tokens only). Read once at import; returned verbatim as fragment.css.
_CSS_PATH = Path(__file__).resolve().parent.parent / "styles" / "st_31.css"
_CSS = _CSS_PATH.read_text(encoding="utf-8")

# Atmospheric ground asset preference (the breathing_bg_* slots / report assets).
_GROUND_IMAGE_TYPES = ("gradient", "texture", "background", "scene")
_REPORT_GROUND_SLOTS = ("atmospheric_gradient", "background_texture",
                        "extra_wide", "extra_square")
_REPORT_GROUND_TYPES = ("gradient", "texture", "background", "scene")
# A REAL photo ground (a founder/client scene) gets a LIGHT cinematic gradient so
# the photo shows; an ABSTRACT ground (gradient/texture) gets the deep atmospheric
# darken. "scene"/"photo"/"portrait" are real photos; the rest are abstract.
_PHOTO_GROUND_TYPES = ("scene", "photo", "portrait")

# Three geo-overlay arrangements; pick one per page so the breathing pages in a
# deck don't look identical. Keyed off a stable page integer (page number/slot).
_NUM_VARIANTS = 3


def _ground_uri(page: dict, ctx: RenderContext) -> tuple[str, bool]:
    """Resolve the breathing-page ground image URI + whether it is a real PHOTO.

    Prefers the page's own breathing background (a real founder/client scene when
    routed); falls back to a package report_asset (atmospheric gradient / texture).
    Returns (uri, is_photo): is_photo True when the matched asset is a real photo
    (scene/photo/portrait) — the renderer then uses a LIGHT cinematic gradient so
    the photo shows; otherwise the deep atmospheric darken. Graceful: ('', False).
    """
    for a in (page.get("assets") or []):
        if a.get("image_type") in _GROUND_IMAGE_TYPES and a.get("path"):
            p = ctx.resolve_asset(a["path"])
            if p is not None:
                return p.as_uri(), a.get("image_type") in _PHOTO_GROUND_TYPES
    return ctx.resolve_report_asset(_REPORT_GROUND_SLOTS, _REPORT_GROUND_TYPES) or "", False


def _variant(page: dict) -> int:
    """Pick a geo-overlay variant (1..N) from a stable page integer.

    Uses page_numbers (then slot) so a given breathing page is deterministic and
    the three apex breathing pages (6 / 11 / 17) get different motifs.
    """
    raw = page.get("page_numbers") or page.get("slot") or 1
    try:
        n = int(str(raw).split("-")[0].strip())
    except (TypeError, ValueError):
        n = 1
    return (n - 1) % _NUM_VARIANTS + 1


def render(page: dict, ctx: RenderContext) -> PageFragment:
    """Render the ST-31/ST-32 breathing page as a PageFragment.

    Data-prep → render templates/st_31.html.jinja. The full-bleed named `@page
    bleed` lives in the shared head (assembler); this returns only the page body
    markup + the ST-31-scoped layout CSS.
    """
    d: dict = page.get("data") or {}

    ground_uri, photo_ground = _ground_uri(page, ctx)

    # ---- optional "live social presence" phone mockup (DNA §C2) ----
    # When the page carries a `social_post` (a real IG post + the founder's real
    # avatar + handle), render a RENDERER-DRAWN phone centred on a DEEP BRAND ground
    # (not a full-bleed photo) — the phone is the hero. Never fabricates engagement:
    # only the supplied real photo/avatar/handle (+ optional real caption) show.
    social = d.get("social_post") or {}

    def _res(rel: str) -> str:
        if not rel:
            return ""
        p = ctx.resolve_asset(str(rel))
        return p.as_uri() if p is not None else ""

    social_photo = _res(social.get("photo", ""))
    social_avatar = _res(social.get("avatar", ""))
    # OPTIONAL profile-grid: a list of real post images → the phone shows a 3-col
    # grid (the "active brand presence" look) instead of a single post.
    social_grid = [u for u in (_res(g) for g in (social.get("grid") or [])) if u]
    has_social = bool(social_photo or social_grid)
    if has_social:
        # the phone pops on a deep token brand ground (primary→ink), not a photo.
        ground_uri, photo_ground = "", False

    # The resolved file URI carries no single quotes; keep the style minimal.
    ground_style = (
        f" style=\"background-image:url('{ground_uri}')\"" if ground_uri else ""
    )

    template = get_env().get_template("st_31.html.jinja")
    html = template.render(
        ground_style=ground_style,
        has_ground=bool(ground_uri),
        photo_ground=photo_ground,
        variant=_variant(page),
        phrase=d.get("phrase", ""),
        has_social=has_social,
        social_photo=social_photo,
        social_avatar=social_avatar,
        social_grid=social_grid,
        social_handle=str(social.get("handle", "")).strip(),
        social_caption=str(social.get("caption", "")).strip(),
    )
    return PageFragment(html=html, css=_CSS)
