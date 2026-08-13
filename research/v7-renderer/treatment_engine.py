"""Treatment data layer (Task TS-1.1): the normalized TreatmentData model and
the adapt(page, ctx) mapper.

A "treatment" is a named, brand-agnostic page LAYOUT (editorial, metric column,
timeline, etc.). Many DIFFERENT package page types must be renderable through
the SAME treatment, so every treatment template consumes ONE normalized data
shape, TreatmentData, rather than the raw per-st_type `data` dict. adapt() is
the mapper from a raw package page dict into that normalized shape.

THIS module is the DATA layer only (model + adapt + the per-st_type overrides).
The render / registry layer that turns a TreatmentData into HTML is a separate,
later task in the same system.

GROUNDING / NO-FABRICATION CONTRACT (hard):
  adapt reads ONLY values present in the page dict. It NEVER bakes a
  client-specific literal as a default or fallback (no client name, no stat
  string, no brand color). When a field is absent from the page, the
  corresponding TreatmentData field is None / [] / empty. The ONLY authored
  string constants here are brand-AGNOSTIC structural section labels that
  describe a section's ROLE for the case-study report TYPE (Ausgangssituation /
  Ziel / Lösung / Ergebnis). To keep the treatment and the legacy ST-07A pattern
  in agreement, those labels and their data-field mapping are imported VERBATIM
  from patterns.st_07a (its _SECTION_SPEC), not re-typed here.

adapt() MUST NOT raise on any page (eligible content type OR bypass type OR a
page with missing slots). It uses .get(...) + truthiness checks throughout, and
relies on the RenderContext slot helpers (slot_uri / slot_uris) which already
return None / [] on any missing asset. No bare excepts that could hide bugs.

ESCAPING CONTRACT: user-copy strings are HTML-escaped at this boundary (the
templates render with autoescape off); URIs (image / images / scene) and the
generated component SVGs stay verbatim. See the markupsafe import note.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

# HTML-escaping at the ADAPT boundary: the shared Jinja env runs with
# autoescape OFF and the treatment templates interpolate td string fields raw,
# so every user-copy string is escaped HERE, where _str / _paragraphs /
# _string_list produce it. markupsafe.Markup marks a string as already-escaped,
# which keeps escaping IDEMPOTENT (a value re-run through _str can never be
# double-escaped). URI fields (td.image / td.images / td.scene) and generated
# SVG markup (td.components) stay VERBATIM: they never pass through these
# helpers (see _generic's produkt_bild note). markupsafe ships with jinja2.
from markupsafe import Markup, escape

# Allow flat imports from the chassis package (mirrors the other root modules).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from patterns.base import PageFragment, RenderContext  # noqa: E402
from templating import get_env  # noqa: E402

# Reuse the EXACT case-study section labels + field mapping the legacy ST-07A
# pattern uses, so the treatment and the pattern agree on wording and order
# (Ausgangssituation, Ziel, Lösung, Ergebnis). These are brand-agnostic
# structural labels for the case-study report TYPE, not client data. Importing
# them (rather than re-typing) is what keeps the two layers from drifting.
from patterns.st_07a import _SECTION_SPEC, _KICKER_BASE  # noqa: E402

# The About-page eyebrow is a brand-agnostic CONTENT label for the About report
# TYPE (the standard German "über uns" kicker), reused VERBATIM from the legacy
# ST-05 pattern so the treatment and the pattern agree on wording. Not client
# data (cf. _KICKER_BASE / _SECTION_SPEC for the case-study type).
from patterns.st_05 import _KICKER as _ABOUT_KICKER  # noqa: E402


# --- the normalized model ----------------------------------------------------
@dataclass
class TreatmentData:
    """Brand-agnostic, treatment-ready view of one package page.

    Every field is OPTIONAL with a safe default (None / empty list) so any
    treatment template reads only the subset it needs and a missing piece of
    data is simply absent (never a fabricated placeholder). Nothing here is
    client-specific: the values are copied straight from the page dict by
    adapt(), and absent inputs leave the field empty.
    """

    # provenance (copied verbatim from the page)
    st_type: str = ""
    css_template: str = ""
    page_role: Optional[str] = None  # hero flag a later task sets on the page

    # the layout VARIANT the adapter selected for the hosting treatment (e.g.
    # ST-05's "portrait_rail"). Variants are decided in ADAPTERS (by st_type
    # intent), never inferred from data presence in templates: a template that
    # forks its layout on incidental data (an image that merely happens to be
    # present) misfires on other st_types sharing the treatment. None means the
    # treatment's default variant.
    variant: Optional[str] = None

    # text spine
    eyebrow: Optional[str] = None          # short section / kicker label
    headline: Optional[str] = None         # the page title (or a type override)
    headline_accent: Optional[str] = None  # a keyword to render in the accent color
    subhead: Optional[str] = None          # a lede / standfirst
    body: list[str] = field(default_factory=list)  # paragraphs

    # the labeled narrative column: [{"label", "text"}, ...]
    sections: list[dict] = field(default_factory=list)

    # quantitative + structured collections
    stats: list[dict] = field(default_factory=list)   # [{"value", "label"}]
    steps: list[dict] = field(default_factory=list)    # [{"title", "body"}]
    list_items: list[str] = field(default_factory=list)  # a generic bullet list

    # a single headline RESULT / payoff line for a process page (ST-06's
    # `ergebnis`): the verbatim outcome sentence + a parsed proof figure when the
    # sentence carries a percentage. {"text", "figure", "source"} where text is
    # the FULL verbatim sentence, figure is the extracted "%"-bearing token (e.g.
    # "30-50%") for a prominent KPI/gauge, and source is the parenthetical
    # citation (e.g. "PwC, 2026") shown as a small caption. None when absent. No
    # fabrication: figure/source are populated only when actually present.
    result: Optional[dict] = None

    # a pull quote / thesis: {"text", "attribution"}
    quote: Optional[dict] = None

    # an identity caption for an image-led column: {"name", "role"}. Used when a
    # treatment paints a portrait that has a person behind it (e.g. the editorial
    # About column's founder name + role). Distinct from `quote.attribution` (a
    # source line under a pull-quote): a caption labels the PORTRAIT, not a quote.
    caption: Optional[dict] = None

    # a trust / logo wall of names
    credentials: list[str] = field(default_factory=list)

    # imagery (resolved file:// URIs from the ctx slot helpers)
    image: Optional[str] = None            # primary portrait / hero photo
    images: list[str] = field(default_factory=list)  # a gallery

    # the page's data-viz spec(s), passed through verbatim for a hosting treatment
    viz: Any = None

    # the page's GENERATED component SVGs (preprocessor charts/diagrams),
    # resolved to inline <svg> strings so a treatment can embed them. Empty when
    # the page carries none (graceful).
    components: list[str] = field(default_factory=list)

    # the page's GENERATED scene/background art (fal), as a file:// URI.
    # Treatments render it as a designed photo band; without a host the
    # generated art was produced-but-invisible on every treated page.
    scene: Optional[str] = None

    # a call to action: {"text", "url"}
    cta: Optional[dict] = None


# --- small grounded helpers --------------------------------------------------
def _str(value: Any) -> Optional[str]:
    """Coerce to a non-empty, stripped, HTML-ESCAPED string, else None.

    User copy is escaped here, at the adapt boundary (the treatment templates
    interpolate td string fields raw; see the markupsafe note in the imports).
    Idempotent: a Markup value is already escaped and passes through unchanged,
    so double-escaping cannot happen. Containers never leak a Python repr: a
    list of strings joins with a single space, a dict yields "" (no text).
    Plain strings and numbers keep their exact text. Never invents text."""
    if value is None:
        return None
    if isinstance(value, Markup):
        s = value.strip()
        return s or None
    if isinstance(value, dict):
        return ""
    if isinstance(value, (list, tuple)):
        parts = [p for p in (_str(v) for v in value) if p]
        return Markup(" ").join(parts) if parts else None
    s = str(value).strip()
    if not s:
        return None
    return escape(s)


def _paragraphs(body: Any) -> list[str]:
    """Split a body into paragraphs on blank-line boundaries.

    Mirrors preprocess.preprocess_body's split (re.split on one-or-more blank
    lines) so the treatment paragraphs match the legacy pattern's. A body LIST
    reads as one paragraph per string entry and a body DICT contributes its
    string VALUES in insertion order (both used to leak nothing: a silent []);
    any other non-string yields []. Paragraphs are HTML-escaped like every
    other user-copy string (see _str). No fabrication: empty in, empty out.
    """
    if isinstance(body, dict):
        body = "\n\n".join(v for v in body.values() if isinstance(v, str))
    elif isinstance(body, (list, tuple)):
        body = "\n\n".join(v for v in body if isinstance(v, str))
    if not isinstance(body, str):
        return []
    text = body.strip()
    if not text:
        return []
    return [escape(p.strip()) for p in re.split(r"\n\n+", text) if p.strip()]


def _stat_pairs(items: Any) -> list[dict]:
    """Normalize a list of {value,label}-shaped entries to [{"value","label"}].

    Accepts dicts (value/label keys) and "label: value" / "value" strings, the
    same shapes the live data carries. Entries with neither a value nor a label
    are dropped. Returns [] for any non-list. Values/labels are copied verbatim.
    Each non-empty value also carries "value_len": the PRE-escape glyph count
    (what actually PRINTS), so the templates' is-figure length checks are not
    skewed by escaped entities ("&amp;" is 5 chars of markup but 1 glyph).
    """
    out: list[dict] = []
    if not isinstance(items, list):
        return out
    for it in items:
        if isinstance(it, dict):
            value = _str(it.get("value"))
            label = _str(it.get("label"))
        elif isinstance(it, str) and ":" in it:
            label_part, value_part = (s.strip() for s in it.split(":", 1))
            value, label = _str(value_part), _str(label_part)
        else:
            value, label = _str(it), None
        if value is None and label is None:
            continue
        stat = {"value": value or "", "label": label or ""}
        # the PRE-escape glyph count: _str escaped the value, and unescape()
        # reverses exactly that, so this is the printed glyph length.
        if value:
            stat["value_len"] = len(Markup(value).unescape())
        # a source citation attached to the figure (kennzahlen `quelle` ->
        # canonical `sub`) travels with it; dropping it silently detached
        # sourced figures from their citation on every treatment path.
        if isinstance(it, dict) and _str(it.get("sub")):
            stat["sub"] = _str(it.get("sub"))
        out.append(stat)
    return out


def _looks_like_stats(items: Any) -> bool:
    """True iff `items` is a non-empty list of {value/label}-shaped dicts.

    The generic stats probe uses this so it only adopts a list that actually has
    the value/label shape (e.g. ST-05 stats, ST-01 proof_stats) and never
    mis-reads an unrelated list (e.g. a list of strings) as stats.
    """
    if not isinstance(items, list) or not items:
        return False
    for it in items:
        if not isinstance(it, dict):
            return False
        if "value" not in it and "label" not in it:
            return False
    return True


def _step_list(items: Any) -> list[dict]:
    """Normalize a steps list to [{"title","body"}]. Copies verbatim; [] if
    absent or not a list. Dict entries read title/body; string entries become a
    body-only step. Empty entries are dropped."""
    out: list[dict] = []
    if not isinstance(items, list):
        return out
    for it in items:
        if isinstance(it, dict):
            title = _str(it.get("title"))
            body = _str(it.get("body"))
        else:
            title, body = None, _str(it)
        if title is None and body is None:
            continue
        out.append({"title": title or "", "body": body or ""})
    return out


def _string_list(items: Any) -> list[str]:
    """A clean list of non-empty strings from a list input; [] otherwise.
    Entries keep their exact text, HTML-escaped via _str (used for zielgruppe /
    symptoms / credibility_points / partners). No fabrication."""
    if not isinstance(items, list):
        return []
    return [s for s in (_str(x) for x in items) if s]


# The TEXT keys of a viz spec: user copy (writer kennzahlen labels, LLM
# labels) that the viz macros interpolate RAW (autoescape is off), so it is
# escaped at the adapt boundary like every other user-copy string. Keys named
# url/uri/path/preset/percent are structural (URIs, preset names, numbers) and
# must stay verbatim; so does every non-string value.
_VIZ_TEXT_KEYS = frozenset(
    {"label", "figure", "sub", "source", "title", "text", "value"})
_VIZ_VERBATIM_KEYS = frozenset({"url", "uri", "path", "preset", "percent"})
_VIZ_NESTED_LIST_KEYS = ("items", "pairs")
_VIZ_NESTED_DICT_KEYS = ("before", "after")


def _escape_viz(spec: Any) -> Any:
    """HTML-escape the known TEXT fields of a viz spec (or a list of specs).

    Walks the spec shape the presets carry: the top-level text keys plus the
    items[] / pairs[] entry dicts and the before/after {value,label} dicts,
    escaping every str value in a TEXT field with the same escape _str uses
    (idempotent: escape() passes a Markup through unchanged, so a re-adapted
    spec is never double-escaped). _VIZ_VERBATIM_KEYS and non-string values
    pass through untouched. Any non-dict/list input is returned unchanged, so
    a missing viz (None) stays None. Closes the raw-interpolation hole for
    writer/LLM labels on the treatment paths (autoescape is off).
    """
    if isinstance(spec, list):
        return [_escape_viz(s) for s in spec]
    if not isinstance(spec, dict):
        return spec
    out: dict = {}
    for key, val in spec.items():
        if key in _VIZ_VERBATIM_KEYS:
            out[key] = val
        elif key in _VIZ_TEXT_KEYS and isinstance(val, str):
            out[key] = escape(val)
        elif key in _VIZ_NESTED_LIST_KEYS and isinstance(val, list):
            out[key] = [_escape_viz(v) for v in val]
        elif key in _VIZ_NESTED_DICT_KEYS and isinstance(val, dict):
            out[key] = _escape_viz(val)
        else:
            out[key] = val
    return out


def _component_svgs(page: dict, ctx: RenderContext) -> list[str]:
    """Resolve the page's `components` file refs to inline SVG strings.

    Mirrors patterns/base.py's resolve_component (package-relative read), so a
    TREATED page embeds the same generated devices the legacy path would have.
    Graceful: unresolvable/absent entries are skipped; no components -> [].
    """
    out: list[str] = []
    comps = page.get("components") or []
    if not comps:
        return out
    root = Path(ctx.package_dir).resolve()
    for rel in comps:
        if not rel or not isinstance(rel, str):
            continue
        try:
            p = (root / rel).resolve()
            # containment: is_relative_to, NOT str.startswith (a bare prefix
            # match let "../richard-v2/x.svg" escape into a sibling dir whose
            # name shares the package dir as a prefix).
            if p.is_relative_to(root) and p.is_file():
                svg = p.read_text(encoding="utf-8")
                if svg.lstrip().startswith("<svg"):
                    out.append(svg)
        except (OSError, ValueError):
            # OSError: unreadable file. ValueError: UnicodeDecodeError on a
            # non-UTF-8 file (it is a ValueError subclass, and this runs in the
            # UNGUARDED stylist-assignment phase where a raise would abort the
            # whole deck build, violating adapt()'s never-raises contract).
            continue
    return out


def _scene_uri(page: dict, ctx: RenderContext) -> Optional[str]:
    """file:// URI of the page's scene/background asset, or None.

    Reads page["assets"] entries with a scene/background image_type. G18: it
    accepts BOTH status "generated" (the fal art) AND status "downloaded" (a
    client-supplied scene from the image manifest) - previously a manifest
    scene never painted on the treated ST-09 because only "generated" passed
    the filter. Graceful: unresolved path or no such asset -> None (never
    raises; a page without a scene simply has no scene band)."""
    for a in page.get("assets") or []:
        if not isinstance(a, dict):
            continue
        if a.get("status") not in ("generated", "downloaded"):
            continue
        if (a.get("image_type") or "") in ("scene", "background"):
            p = ctx.resolve_asset(a.get("path"))
            if p is not None:
                return p.as_uri()
    return None


def _quote_from(value: Any) -> Optional[dict]:
    """Build a {"text","attribution"} quote from a pullquote-shaped value.

    A string pullquote (ST-02) becomes {text, attribution=None}; a dict
    pullquote (ST-07A) reads text + optional attribution. Returns None when no
    real quote text is present (never fabricates a quote)."""
    if isinstance(value, dict):
        text = _str(value.get("text"))
        attribution = _str(value.get("attribution"))
    else:
        text = _str(value)
        attribution = None
    if text is None:
        return None
    return {"text": text, "attribution": attribution}


# A percentage TOKEN inside a result sentence: a number (possibly with German
# thousands dots / decimal commas, e.g. "1.200" or "12,5") or a range (e.g.
# "30 to 50" written with a hyphen or dash), followed by "%". The digit run is
# `\d[\d.,]*` so it does NOT stop at the first comma/dot: "12,5 %" reads "12,5 %"
# (previously it grabbed only the fragment after the separator, "5 %"). A hyphen
# and the Unicode dash range (U+2010..U+2015) count as the range separator;
# surrounding spaces are collapsed by the post-strip. Brand-agnostic: a pure
# shape, no literal. The dash separators are spelled as escapes so no literal dash
# appears in this source (the authored-dash guard scans this module).
# Each number run must START and END on a digit (`\d(?:[\d.,]*\d)?`) so a trailing
# separator right before the % is never captured (e.g. "35,%" does not yield the
# malformed "35,%"); interior thousands/decimal separators are kept.
_PERCENT_FIGURE_RE = re.compile(
    "\\d(?:[\\d.,]*\\d)?(?:\\s*[\\u2010-\\u2015-]\\s*\\d(?:[\\d.,]*\\d)?)?\\s*%")
# A trailing parenthetical CITATION at (or near) the end of the sentence, e.g.
# "(PwC, 2026)". A citation is identified by BOTH a comma AND a 4-digit year
# (19xx/20xx) inside the parens ("Source, Year"), so a temporal aside like
# "(seit 2019)" (year, no comma) or "(im Schnitt)" (neither) is NOT captured and
# stays in the running text. Captured WITHOUT the parens for the caption.
_SOURCE_RE = re.compile(
    r"\((?=[^()]*,)(?=[^()]*\b(?:19|20)\d{2}\b)([^()]+)\)\s*\.?\s*$")


def _result_from(value: Any) -> Optional[dict]:
    """Build a {"text","figure","source"} result from a result SENTENCE.

    `text` is the full verbatim sentence. `figure` is the first percentage token
    found in it (an integer or a range, copied verbatim, with inner spaces around
    the separator collapsed so e.g. "30 - 50 %" reads "30-50%"); None when the
    sentence carries no percentage. `source` is a trailing parenthetical citation
    (without the parens), e.g. "PwC, 2026"; None when absent. Returns None when
    there is no real sentence. No fabrication: figure/source are derived from the
    sentence itself, never invented."""
    text = _str(value)
    if text is None:
        return None
    figure: Optional[str] = None
    m = _PERCENT_FIGURE_RE.search(text)
    if m:
        # collapse any inner whitespace so a spaced range/percent reads tight.
        figure = re.sub(r"\s+", "", m.group(0))
    source: Optional[str] = None
    sm = _SOURCE_RE.search(text)
    if sm:
        # the slice comes out of the ALREADY-ESCAPED sentence, so mark it as
        # Markup before the _str pass: re-escaping it would double-escape.
        source = _str(Markup(sm.group(1)))
    return {"text": text, "figure": figure, "source": source}


# Primary-image slot probe order: a page's most authoritative portrait wins.
# Brand-agnostic slot ids (defined on RenderContext, not client data); the first
# that resolves to a real file is used, else image stays None.
_PORTRAIT_SLOT_ORDER: tuple[str, ...] = (
    "case_study_portrait",
    "founder",
    "about_portrait",
)


def _primary_image(page: dict, ctx: RenderContext) -> Optional[str]:
    """First resolved portrait URI across the probe order, else None. Relies on
    ctx.slot_uri's graceful None on any missing/unresolved slot, so this never
    crashes and never returns a broken path."""
    for slot_id in _PORTRAIT_SLOT_ORDER:
        uri = ctx.slot_uri(page, slot_id)
        if uri:
            return uri
    return None


# --- the generic mapping -----------------------------------------------------
def _generic(page: dict, data: dict, ctx: RenderContext) -> TreatmentData:
    """Robust mapping that works for ALL st_types from common field names.

    Per-st_type adapters refine this where the generic is wrong. Everything is
    grounded: a field is populated ONLY when the matching key is present and
    truthy in `data` (or a slot resolves), else it stays at its empty default.
    """
    td = TreatmentData(
        st_type=_str(page.get("st_type")) or "",
        css_template=_str(page.get("css_template")) or "",
        page_role=_str(page.get("page_role")),
    )

    td.headline = _str(data.get("title"))
    # a headline accent keyword only when the page actually carries one
    td.headline_accent = _str(data.get("title_accent"))
    td.body = _paragraphs(data.get("body"))

    # generic stats probe: first present value/label-shaped list among the
    # common keys. (Type adapters override with the correct source where needed.)
    for key in ("stats", "metrics", "proof_stats"):
        candidate = data.get(key)
        if _looks_like_stats(candidate):
            td.stats = _stat_pairs(candidate)
            break

    td.steps = _step_list(data.get("steps"))
    td.quote = _quote_from(data.get("pullquote"))
    # the viz spec passes through structurally, but its TEXT fields are user
    # copy interpolated raw by the viz macros, so they are escaped here at the
    # adapt boundary (see _escape_viz).
    td.viz = _escape_viz(data.get("viz"))
    td.image = _primary_image(page, ctx)
    # the page's GENERATED component SVGs (charts/diagrams from the
    # preprocessor), resolved to inline strings. Treatments render these in
    # their component slot; without this, a treated page silently DROPPED every
    # generated device (the produced-but-invisible ST-06 'PROZESS · MECHANIK'
    # defect, 2026-07-11 disconnect analysis).
    td.components = _component_svgs(page, ctx)
    # a REAL product visual routed by the writer's bildwunsch (a pre-framed
    # device shot from the client-assets folder, attached by build_live as a
    # file:// URI). Rendered in the treatments' device bands as a src / url()
    # value, so it stays a VERBATIM URI: deliberately NOT routed through _str,
    # which HTML-escapes user copy. Graceful: absent on pages that asked for
    # nothing or when no product files exist.
    produkt = data.get("produkt_bild")
    produkt = produkt.strip() if isinstance(produkt, str) else None
    if produkt and produkt not in td.images:
        td.images = list(td.images) + [produkt]
    # the page's fal-generated scene/background art (a photo band host).
    td.scene = _scene_uri(page, ctx)

    return td


# --- per-st_type overrides ---------------------------------------------------
def _adapt_st07a(td: TreatmentData, page: dict, data: dict, ctx: RenderContext) -> TreatmentData:
    """Case study: the most structured type.

    - eyebrow from fallstudie_number (e.g. "FALLSTUDIE 03"),
    - headline override = ergebnis_headline,
    - subhead = kurzportraet,
    - sections from the (label, field) spec, SKIPPING empty/whitespace text,
    - stats from ergebnis_metrics,
    - quote from pullquote, attribution from kunde.name when the pullquote
      carries none.
    """
    number = data.get("fallstudie_number")
    if number not in (None, "", 0):
        # Zero-pad single-digit numbers to two places (01..09) but keep 10+ intact
        # and pass through already-formatted strings unchanged: a hard-coded "0"
        # prefix printed "010" for case 10 (the 28+ page / ST-07C tier) and "003"
        # for a pre-padded "03". The a4_case_study ghost numeral reads this token.
        try:
            num_str = f"{int(number):02d}"
        except (TypeError, ValueError):
            num_str = str(number).strip()
        # through _str so a string-shaped number is escaped like all user copy.
        td.eyebrow = _str(f"{_KICKER_BASE} {num_str}")

    td.headline = _str(data.get("ergebnis_headline")) or td.headline
    td.subhead = _str(data.get("kurzportraet"))

    sections: list[dict] = []
    for label, field_name in _SECTION_SPEC:
        text = _str(data.get(field_name))
        if text:
            sections.append({"label": label, "text": text})
    td.sections = sections

    # ST-07A stats feed the ERGEBNIS rail. Client RESULTS (ergebnis_metrics)
    # lead; when a case carries none, the generic-probe stats (the writer's
    # kennzahlen figures) fall through so the rail is not left empty. That
    # fallthrough cannot misattribute: _stat_pairs carries each sourced
    # figure's quelle citation as `sub`, and the a4_case_study rail prints it,
    # so a market figure renders WITH its source line rather than posing as an
    # unlabelled client result.
    td.stats = _stat_pairs(data.get("ergebnis_metrics")) or td.stats

    # Client identity for the case-study rail: name + role (funktion) + company
    # URL + initials (the InitialsAvatar fallback when no portrait resolves).
    # Grounded: populated only from what `kunde` actually carries; absent -> no
    # caption. This is what the a4_case_study rail reads for the person block.
    kunde = data.get("kunde") or {}
    if isinstance(kunde, dict):
        name = _str(kunde.get("name"))
        role = _str(kunde.get("funktion"))
        url = _str(kunde.get("company_url"))
        initials = _str(kunde.get("initials"))
        if name or role or url or initials:
            td.caption = {
                "name": name or "", "role": role or "",
                "url": url or "", "initials": initials or "",
            }

    quote = _quote_from(data.get("pullquote"))
    if quote is not None and not quote.get("attribution"):
        quote["attribution"] = _str(kunde.get("name") if isinstance(kunde, dict) else None)
    td.quote = quote

    return td


def _adapt_st05(td: TreatmentData, page: dict, data: dict, ctx: RenderContext) -> TreatmentData:
    """About: stats, partners -> credentials, credibility_points -> list_items,
    proof photos -> images gallery, and (when present) an `author` dict ->
    a portrait caption {name, role}.

    The About page typically carries NO portrait or `author` of its own (its
    slots resolve the proof gallery only); when the image-led editorial treatment
    is chosen for it, the assembler injects the package's FOUNDER IDENTITY (a
    synthetic resolved `founder` slot + an `author` dict) onto the page dict
    BEFORE adapt runs, so `_primary_image` resolves the portrait and this reads
    `author` into `td.caption`. Brand-agnostic: it reads only what is present; an
    About page with no injected author simply has no caption (graceful).

    Also stamps td.variant = "portrait_rail" when a portrait resolved: variants
    are decided in adapters (by st_type intent), never inferred from data
    presence in templates."""
    td.eyebrow = _ABOUT_KICKER  # the brand-agnostic "Über uns" content label
    td.stats = _stat_pairs(data.get("stats"))
    td.credentials = _string_list(data.get("partners"))
    td.list_items = _string_list(data.get("credibility_points"))
    # MERGE the proof gallery into whatever the generic pass already placed in
    # td.images (e.g. the produkt_bild device shot): plain assignment CLOBBERED
    # those. Order-preserving dedup: generic images first, then the proof URIs.
    images = list(td.images)
    for uri in ctx.slot_uris(page, "proof"):
        if uri not in images:
            images.append(uri)
    td.images = images

    # The ABOUT page INTENDS the portrait rail whenever a portrait resolved
    # (its own slot, or the founder identity the assembler injects). Stamped
    # here, in the adapter, so a hosting template renders the rail by DECISION
    # (td.variant), never by inferring it from incidental data presence.
    if td.image:
        td.variant = "portrait_rail"

    author = data.get("author")
    if isinstance(author, dict):
        name = _str(author.get("name"))
        role = _str(author.get("role"))
        if name or role:
            td.caption = {"name": name or "", "role": role or ""}
    return td


def _adapt_steps(td: TreatmentData, page: dict, data: dict, ctx: RenderContext) -> TreatmentData:
    """ST-06 / ST-22: a process expressed as ordered steps.

    Maps the FULL steps list (every step keeps its title + body; nothing is
    dropped) and, when the page carries an `ergebnis` outcome sentence (ST-06's
    framework result), exposes it as td.result via _result_from (verbatim text +
    a parsed "%"-figure + the parenthetical source). ST-22 has no `ergebnis`, so
    td.result stays None there (graceful). The steps are ALSO mirrored into
    list_items ("title: body" strings, verbatim) so a fill-layout fallback (a
    thin step set fails the timeline's min-count contract) renders them as its
    numbered bands instead of dropping the process entirely."""
    td.steps = _step_list(data.get("steps"))
    td.list_items = [
        (f"{s['title']}: {s['body']}" if (s.get("title") and s.get("body"))
         else (s.get("title") or s.get("body") or ""))
        for s in td.steps
    ]
    td.list_items = [i for i in td.list_items if i]
    td.result = _result_from(data.get("ergebnis"))
    return td


def _adapt_fazit(td: TreatmentData, page: dict, data: dict, ctx: RenderContext) -> TreatmentData:
    """Summary: the thesis (`these`) becomes the quote with the author as
    attribution; cta from cta_url. `author` is isinstance-guarded like
    _adapt_st05's: a dict reads its name, a plain STRING author is itself the
    attribution (stripped), anything else yields None (a string author used to
    crash on .get)."""
    these = _str(data.get("these"))
    if these:
        author = data.get("author")
        if isinstance(author, dict):
            attribution = _str(author.get("name"))
        elif isinstance(author, str):
            attribution = _str(author)
        else:
            attribution = None
        td.quote = {"text": these, "attribution": attribution}

    url = _str(data.get("cta_url"))
    if url:
        td.cta = {"text": _str(data.get("cta_text")), "url": url}

    # G14: the cost-of-inaction (`kosten_des_nichtstuns`) was read ONLY by the
    # legacy ST-FAZIT pattern, but ST-FAZIT is always treated, so the block
    # never rendered live. Map it onto a stat so the treated summary shows the
    # named cost (verbatim; a prose value renders as a statement, never a
    # fabricated figure).
    kosten = _str(data.get("kosten_des_nichtstuns"))
    if kosten:
        td.stats.append(
            {"label": "Kosten des Nichtstuns", "value": kosten}
        )
    return td


def _adapt_outlook(td: TreatmentData, page: dict, data: dict, ctx: RenderContext) -> TreatmentData:
    """ST-02 outlook: zielgruppe -> list_items (the generic quote/body already
    cover the rest)."""
    td.list_items = _string_list(data.get("zielgruppe"))
    return td


def _adapt_status_quo(td: TreatmentData, page: dict, data: dict, ctx: RenderContext) -> TreatmentData:
    """ST-09 status quo: symptoms -> list_items."""
    td.list_items = _string_list(data.get("symptoms"))
    return td


def _adapt_cta_hard(td: TreatmentData, page: dict, data: dict, ctx: RenderContext) -> TreatmentData:
    """ST-03 hard CTA: cta from cta_url + cta_text.

    NOTE: ST-03 is a BYPASS type (treatment_stylist.BYPASS_ST_TYPES), so the
    stylist never assigns a treatment to it and this adapter is currently
    inert in the live path (the legacy st_03 pattern renders the CTA). It is
    kept as the documented adapter shape for when ST-03 gains a treatment."""
    url = _str(data.get("cta_url"))
    if url:
        td.cta = {"text": _str(data.get("cta_text")), "url": url}
    return td


# Per-st_type override table. A type with no entry uses the generic mapping
# alone (correct for the bypass types and for the types whose treatments are
# refined later: ST-14 false_beliefs, ST-07B theory, ST-31 atemseite, ST-01).
_ADAPTERS: dict[str, Callable[[TreatmentData, dict, dict, RenderContext], TreatmentData]] = {
    "ST-07A": _adapt_st07a,
    "ST-05": _adapt_st05,
    "ST-06": _adapt_steps,
    "ST-22": _adapt_steps,
    "ST-FAZIT": _adapt_fazit,
    "ST-02": _adapt_outlook,
    "ST-09": _adapt_status_quo,
    "ST-03": _adapt_cta_hard,
}


# --- the public entry point --------------------------------------------------
def adapt(page: dict, ctx: RenderContext) -> TreatmentData:
    """Map a raw package `page` dict into a normalized TreatmentData.

    Builds the generic mapping first, then applies the per-st_type override (if
    one exists) to refine it. Pure + total: it reads only values present on the
    page, leaves absent fields empty, and never raises on a missing slot, a
    bypass type, or a page with no `data`.
    """
    data = page.get("data") or {}
    if not isinstance(data, dict):
        data = {}

    td = _generic(page, data, ctx)

    refine = _ADAPTERS.get(td.st_type)
    if refine is not None:
        td = refine(td, page, data, ctx)

    return td


# --- the render / registry layer (Task TS-1.2) -------------------------------
# This layer turns (page, ctx, treatment_name) into a PageFragment. The DATA
# layer above (TreatmentData + adapt) stays untouched; this is purely additive.
# The ACTUAL treatment templates (editorial, timeline, dashboard, ...) are
# authored in later tasks and register themselves into TREATMENTS; this task
# builds and tests only the machinery, using a probe treatment in the tests.

# The repo root is the directory holding this module. css_path values are
# resolved relative to it so a treatment's stylesheet text can be loaded.
_REPO_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Treatment:
    """Descriptor for one named, brand-agnostic page LAYOUT.

    A treatment is rendered one of two ways:
      - the COMMON, template-driven path: a Jinja `template` (relative to the
        templates search root, e.g. "treatments/editorial.html.jinja") plus a
        `css_path` (repo-relative, e.g. "styles/treatments/editorial.css") whose
        text becomes the PageFragment css, or
      - the ESCAPE HATCH: a `render_fn(td, ctx) -> PageFragment` for a treatment
        that needs custom Python. When present, render_fn takes precedence over
        template / css.

    `required_fields` + `needs_image` form the data-fit gate (meets_contract):
    they name the TreatmentData attributes that must be non-empty (and, if
    needs_image, that td.image must be truthy) for this treatment to render well.
    `archetype` is a family tag (e.g. "editorial", "timeline", "dashboard") the
    stylist uses later to avoid repeating archetypes across a deck. `formats` is
    the subset of {"a3", "a4"} the treatment supports.
    """

    name: str
    archetype: str
    formats: frozenset[str]
    required_fields: tuple[str, ...] = ()
    needs_image: bool = False
    template: Optional[str] = None
    css_path: Optional[str] = None
    render_fn: Optional[Callable[[TreatmentData, RenderContext], PageFragment]] = None
    # CONTENT-VOLUME contract: (field, n) pairs; a list-valued td field must
    # carry at least n entries for the layout's geometry to fill (a timeline
    # with 3 one-liners reads as dots floating in a void; the stylist must
    # route such pages to a layout that flex-fills instead).
    min_counts: tuple = ()


# The treatment registry. Starts EMPTY: the real treatments register themselves
# in later tasks (and tests register a probe). Use register() to add entries and
# get_treatment() to read them, so callers never mutate the dict directly.
TREATMENTS: dict[str, Treatment] = {}


def register(treatment: Treatment) -> None:
    """Insert (or replace) a treatment in the registry, keyed by its name.

    Also invalidates the built-cache entry for the name (re-registering may
    change render_fn/template, so a stale built/unbuilt verdict must not stick;
    a test or a later phase can author a template mid-process) and the CSS text
    cache for the treatment's css_path (a re-register may point at a rewritten
    stylesheet)."""
    TREATMENTS[treatment.name] = treatment
    _BUILT_CACHE.pop(treatment.name, None)
    if treatment.css_path:
        _CSS_CACHE.pop(treatment.css_path, None)


def get_treatment(name: str) -> Optional[Treatment]:
    """The registered treatment for `name`, or None when no such treatment."""
    return TREATMENTS.get(name)


def _is_present(value: Any) -> bool:
    """True iff `value` counts as present (non-empty). None, "", [], {} (and any
    other falsy container) count as not-present. This is the emptiness rule the
    data-fit gate uses for every required field."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return bool(value)


def meets_contract(td: TreatmentData, treatment: Treatment) -> bool:
    """True iff the data FITS this treatment.

    Every name in `treatment.required_fields` must map to a present (non-empty)
    TreatmentData attribute, and (when `treatment.needs_image`) `td.image` must
    be truthy. None / "" / [] / {} all count as not-present. A missing attribute
    name (defensive) also counts as not-present. This is the gate the stylist and
    render() both use to decide whether a treatment applies to a page's data.
    """
    for name in treatment.required_fields:
        if not _is_present(getattr(td, name, None)):
            return False
    if treatment.needs_image and not td.image:
        return False
    for name, n in treatment.min_counts:
        val = getattr(td, name, None)
        if not isinstance(val, (list, tuple)) or len(val) < n:
            return False
    return True


# CSS text per css_path, so a deck rendering the same treatment many times
# (e.g. five case studies) reads its stylesheet from disk ONCE per process.
# Invalidated in register() alongside _BUILT_CACHE.
_CSS_CACHE: dict[str, str] = {}


def _render_template_treatment(
    treatment: Treatment, td: TreatmentData, ctx: RenderContext
) -> PageFragment:
    """Render a template-driven treatment into a PageFragment.

    Renders `treatment.template` (via the shared Jinja env, which searches both
    templates/ and components/, so a treatment can import the macro library) with
    `td` and `ctx` in the context, so the template reads td.headline, td.stats,
    etc. The PageFragment css is the text of `treatment.css_path` resolved
    relative to the repo root, cached per css_path in _CSS_CACHE; if that file is
    missing (or unreadable) the css is "" (graceful, no crash). Used for every
    treatment without a render_fn.
    """
    html = get_env().get_template(treatment.template).render(td=td, ctx=ctx)

    css = ""
    if treatment.css_path:
        cached = _CSS_CACHE.get(treatment.css_path)
        if cached is None:
            cached = ""
            css_file = (_REPO_ROOT / treatment.css_path).resolve()
            if css_file.exists():
                try:
                    cached = css_file.read_text(encoding="utf-8")
                except OSError:
                    cached = ""
            _CSS_CACHE[treatment.css_path] = cached
        css = cached
    return PageFragment(html=html, css=css)


def render(page: dict, ctx: RenderContext, treatment_name: str) -> Optional[PageFragment]:
    """Render `page` through the named treatment, or None when it does not apply.

    Steps: adapt the page to TreatmentData, look up the treatment, gate on the
    data contract, then dispatch (render_fn if set, else the template path).

    The None returns here are the EXPECTED, non-error "this treatment does not
    apply" cases, so the caller (the assembler) can cleanly fall back to the
    legacy pattern:
      - an UNKNOWN treatment_name (no such entry), and
      - a page whose data does NOT meet the treatment's contract.
    Neither raises.

    By contrast, a registered treatment's own render_fn / template MAY raise on a
    genuine BUG; render() does NOT swallow that. The assembler calls render()
    inside its existing per-page try/except, so a buggy treatment degrades to the
    generic pattern there rather than being masked here (which would hide real
    defects behind a silent fallback).
    """
    treatment = get_treatment(treatment_name)
    if treatment is None:
        return None

    td = adapt(page, ctx)
    if not meets_contract(td, treatment):
        return None

    if treatment.render_fn is not None:
        return treatment.render_fn(td, ctx)
    return _render_template_treatment(treatment, td, ctx)


_BUILT_CACHE: dict[str, bool] = {}


def treatment_is_built(treatment_name: str) -> bool:
    """True iff the treatment's TEMPLATE actually exists in the Jinja loader.

    The catalog registers treatments whose templates are authored LATER
    (metadata-only stubs). A stub must never be ASSIGNED: it passes the data-fit
    check, then render() raises TemplateNotFound and the page falls back to the
    LEGACY pattern, silently eating the real treatment that was next in the
    candidate list (the 2026-07-13 ST-02 regression: synthesized viz made the
    a4_bi_dashboard stub fit, and the fill treatment was lost to a flat legacy
    page). Checked against the SAME loader render() uses; cached per name."""
    cached = _BUILT_CACHE.get(treatment_name)
    if cached is not None:
        return cached
    treatment = get_treatment(treatment_name)
    built = False
    if treatment is not None:
        if treatment.render_fn is not None:
            # the documented ESCAPE HATCH: a render_fn treatment needs no
            # template, and render() dispatches render_fn FIRST. It is built.
            built = True
        else:
            try:
                env = get_env()
                env.loader.get_source(env, treatment.template)
                built = True
            except Exception:  # noqa: BLE001 - TemplateNotFound or loader error
                built = False
    _BUILT_CACHE[treatment_name] = built
    return built


def candidate_fits(page: dict, ctx: RenderContext, treatment_name: str) -> bool:
    """True iff `treatment_name` is registered AND its template is BUILT AND the
    page's adapted data meets its contract. The thin data-fit check the stylist
    uses to shortlist treatments for a page (without rendering). No raise on an
    unknown name."""
    treatment = get_treatment(treatment_name)
    if treatment is None:
        return False
    if not treatment_is_built(treatment_name):
        return False
    return meets_contract(adapt(page, ctx), treatment)
