"""Pattern for ST-01 — report COVER (Phase 4b founder-hero rebuild).

DATA-PREP ONLY. This module reads the package `page` dict, resolves the COVER's
human anchor (the founder portrait SLOT), splits the title into a two-tone
display headline, shapes a context dict, and renders `templates/st_01.html.jinja`
(which composes the atomic macro library on a token-themed full-bleed layout,
`styles/st_01.css`). The returned PageFragment.html is that rendered string; the
.css is the layout sheet's contents.

FOUNDER-AS-HERO (DNA §C2 — "the biggest lever"):
  The founder is THE human anchor of the cover, used PROMINENTLY as a large
  portrait — NOT an abstract generated scene. The portrait arrives via the v2.0
  `page["slots"]` list: the entry with slot_id == "founder" and
  status == "resolved", resolved to a file:// URI by `ctx.slot_uri(page,
  "founder")` (the shared photo-slot primitive). The cover composes the portrait
  as a prominent full-bleed photo block (upper ~60% of the sheet) with a scrim
  ramping to --color-ink, over a dark editorial title band (lower ~40%) carrying
  the founder byline + the two-tone display title + audience/teaser. This mirrors
  the agency's real apex cover (founder portrait dominant, title block beneath).

GRACEFUL FALLBACK (photo-less clients must NOT regress):
  When `ctx.slot_uri(page, "founder")` is None (a client without a founder photo
  on Drive), the hero block falls back to the prior cover behaviour — the
  generated cover-hero SCENE (page["assets"] entry with image_type ==
  "background", slot_id "cover_hero"); and failing THAT, the --color-primary
  ground under the scrim. So the cover never renders blank and photo-less clients
  keep the scene-cover look.

TWO-TONE TITLE (DNA §C1, the signature display headline):
  The title renders through the `two_tone_headline` macro — a neutral serif LEAD
  run + a bold-uppercase ACCENT run (e.g. "Ein kurzer AUSBLICK"). Split heuristic
  (documented): if the data carries a structured `title_accent` (the punch clause)
  it is used verbatim and the LEAD is the remaining `title` prefix; OTHERWISE the
  flat `title` is split on its LAST WORD (lead = all-but-last, accent = last
  word) per §C1's "accent the last word/clause". A 1-word / unsplittable title
  degrades to a plain single-tone headline (the macro's --solo path). The serif
  comes from var(--font-display) (the headline_type axis); accent from
  var(--color-accent) — brand-agnostic, zero literals.

DATA CONTRACT (page["data"]):
  title, title_accent? (optional structured punch run), subtitle,
  audience? (the "für …" band; falls back to nothing), kicker_pills[] (uppercase),
  proof_stats[] ({value,label} → the vertical stat rail overlaid on the photo),
  author.{name,role}, teaser_bullets[] | teaser_items[] (the teaser rail).

FULL-BLEED: the cover section assigns itself the suppressed named `@page cover`
(margin:0, persistent header band + folio removed) via `.page.st-01 { page:
cover }` in styles/st_01.css. The named page itself is declared in the shared
head (assembler.shared_head_css) — @page rules cannot live in a fragment.

History: replaced the abstract-scene cover (read page["assets"] background only)
with this founder-portrait anchor (reads the v2.0 founder SLOT first, scene as a
fallback) + the two-tone display title — closing DNA gap #1 (founder photo not
used as hero) and #10 (no two-tone headlines). Earlier history in git.
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
_CSS_PATH = Path(__file__).resolve().parent.parent / "styles" / "st_01.css"
_CSS = _CSS_PATH.read_text(encoding="utf-8")


def _scene_uri(page: dict, ctx: RenderContext) -> str:
    """The generated cover-hero SCENE URI (the graceful fallback ground).

    The prior cover behaviour: the first page asset with image_type ==
    "background" (slot_id "cover_hero", the fal-generated scene). Returns '' when
    absent so the CSS --color-primary ground shows through the scrim.
    """
    for a in (page.get("assets") or []):
        if a.get("image_type") == "background" and a.get("path"):
            p = ctx.resolve_asset(a["path"])
            if p is not None:
                return p.as_uri()
    return ""


def _split_title(title: str, accent: str) -> tuple[str, str]:
    """Split a cover title into (lead, accent) runs for the two-tone headline.

    - A structured `accent` (data `title_accent`) is the deliberate punch run:
      it is used verbatim; the LEAD is the `title` with that suffix stripped (or
      the whole title when it isn't a suffix — the macro still renders both).
    - Otherwise apply §C1's "accent the last word/clause": LEAD = all words but
      the last, ACCENT = the last word. A single-word (or empty) title returns
      ('', title) so the macro renders a plain single-tone headline.
    """
    title = (title or "").strip()
    accent = (accent or "").strip()
    if accent:
        lead = title
        if title.lower().endswith(accent.lower()):
            lead = title[: len(title) - len(accent)].strip(" –-—:")
        return lead, accent
    words = title.split()
    if len(words) <= 1:
        return "", title          # unsplittable -> macro's solo (plain) path
    return " ".join(words[:-1]), words[-1]


def render(page: dict, ctx: RenderContext) -> PageFragment:
    """Render the ST-01 cover page as a PageFragment.

    Data-prep → render templates/st_01.html.jinja. Head-level CSS
    (@page/@page cover/@font-face/:root/body + the component `c-` classes) lives
    in the shared head (assembler); this returns only the page body markup + the
    ST-01-scoped layout CSS.
    """
    d: dict = page.get("data") or {}

    # ---- the cover's human anchor: the founder portrait SLOT (DNA §C2) ----
    # The v2.0 photo-slot primitive. None => fall back to the generated scene,
    # then to the CSS --color-primary ground (photo-less clients never regress).
    founder_uri = ctx.slot_uri(page, "founder")
    is_portrait = founder_uri is not None
    hero_uri = founder_uri or _scene_uri(page, ctx)
    # The resolved file URI carries no single quotes; keep the style minimal.
    hero_style = f" style=\"background-image:url('{hero_uri}')\"" if hero_uri else ""

    # ---- two-tone display title (DNA §C1) ----
    title_lead, title_accent = _split_title(d.get("title", ""), d.get("title_accent", ""))

    # ---- kicker pills (uppercase strings) ----
    kicker_pills = [str(k) for k in (d.get("kicker_pills") or []) if str(k).strip()]

    # ---- proof_stats → vertical stat rail cells ({value,label} dicts) ----
    stats: list[dict[str, str]] = []
    for s in (d.get("proof_stats") or []):
        if isinstance(s, dict):
            value, label = s.get("value", ""), s.get("label", "")
        elif isinstance(s, str) and ":" in s:
            value, label = (x.strip() for x in s.split(":", 1))
        else:
            value, label = str(s), ""
        if value or label:
            stats.append({"value": value, "label": label})

    # ---- teaser rail bullets ("In diesem Report …") ----
    teaser = [str(t) for t in (d.get("teaser_bullets") or d.get("teaser_items") or [])
              if str(t).strip()]

    author = d.get("author") or {}

    template = get_env().get_template("st_01.html.jinja")
    html = template.render(
        hero_style=hero_style,
        is_portrait=is_portrait,
        wordmark=ctx.brand.company_name_short,
        kicker_pills=kicker_pills,
        stats=stats,
        author_name=author.get("name", ""),
        author_role=author.get("role", ""),
        title_lead=title_lead,
        title_accent=title_accent,
        subtitle=d.get("subtitle", ""),
        audience=d.get("audience", ""),
        teaser=teaser,
    )
    return PageFragment(html=html, css=_CSS)
