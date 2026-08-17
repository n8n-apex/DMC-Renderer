"""Treatment CATALOG (Task TS-1.3): the concrete Treatment descriptors.

This module declares the named, brand-agnostic page LAYOUTS the stylist can
assign and registers them all into the shared TREATMENTS registry on import.

This is METADATA ONLY. Each descriptor names the Jinja template + CSS file it
will render through, but those files are authored in LATER tasks. So importing
this module makes the treatments KNOWN (so candidate_fits / get_treatment see
them and the stylist can assign them), without yet being renderable. The
required_fields of every descriptor are chosen to be SATISFIABLE by the verified
adapt() output of the page types that list it as a candidate, so a candidate
that is offered to a page actually fits that page's data.

GROUNDING / BRAND-AGNOSTIC CONTRACT (hard, scanned by the architecture guard):
  Nothing here is client-specific. No client name, no hex color, no font face,
  no per-client conditional branch. The only string constants are the treatment
  NAMES, ARCHETYPE family tags, generic template/css PATHS, and the FIELD NAMES
  of TreatmentData (which the data-fit gate reads). All of those are structural,
  not client data.

PATH CONVENTION (files authored later):
  template = "treatments/<name>.html.jinja"   (relative to the templates root)
  css_path = "styles/treatments/<name>.css"   (relative to the repo root)
"""
from __future__ import annotations

from treatment_engine import Treatment, register


def _template_path(name: str) -> str:
    """The Jinja template path for a treatment, by convention. Authored later."""
    return f"treatments/{name}.html.jinja"


def _css_path(name: str) -> str:
    """The CSS file path for a treatment, by convention. Authored later."""
    return f"styles/treatments/{name}.css"


def _treatment(
    name: str,
    archetype: str,
    formats: frozenset,
    required_fields: tuple,
    needs_image: bool = False,
    min_counts: tuple = (),
) -> Treatment:
    """Build one Treatment descriptor with the conventional template / css paths.

    Keeps the catalog table below declarative: each row is just the metadata that
    differs (name, archetype, formats, required_fields, needs_image, min_counts);
    the template/css paths are derived from the name so they never drift from it.
    """
    return Treatment(
        name=name,
        archetype=archetype,
        formats=formats,
        required_fields=required_fields,
        needs_image=needs_image,
        template=_template_path(name),
        css_path=_css_path(name),
        min_counts=min_counts,
    )


# The catalog. These 12 cover every apex-eligible page type. More treatments are
# added by later tasks; do NOT add them here now. Each required_fields tuple is
# satisfiable by the adapt() output of the page types that list this treatment as
# a candidate (verified against the real apex package), so an offered candidate
# always fits its page's data.
_CATALOG: tuple[Treatment, ...] = (
    # editorial's stylesheet is authored for the A3 sheet ONLY; the A4 case is
    # owned by a4_editorial_fill. Listing a4 here let the format filter offer a
    # layout whose CSS cannot fill an A4 page box.
    _treatment("editorial", "editorial", frozenset({"a3"}), ("headline",), needs_image=True),
    # ST-07A Fallstudie EINZELSEITE (Standard, per 08_DMC_Design_System_v2 §ST-07):
    # a case study is an A4 SINGLE page by default. Left cream narrative + right dark
    # rail (oversized numeral + client photo/initials + big Ergebnis numbers +
    # pullquote). a4-only + leads the ST-07A candidate list, so this is what every
    # case study renders as. needs_image=False (InitialsAvatar fallback when no
    # portrait). This is the reference anatomy (nikl_p08 / aerz_p05-left).
    _treatment("a4_case_study", "case_study", frozenset({"a4"}), ("headline",), needs_image=False),
    # ST-07C Fallstudie DOPPELSEITE (Ausnahmefall): the A3 spread. a3-only, reached
    # ONLY when a page carries an explicit page_format="a3" / case_study_spread
    # signal (report #2/3, exceptional proof, or 28+ pages): NOT the default. See
    # treatment_stylist._wants_explicit_a3.
    _treatment("a3_case_study", "case_study", frozenset({"a3"}), ("headline",), needs_image=False),
    _treatment("glass_card", "glass_card", frozenset({"a3"}), ("stats",)),
    _treatment("split_portrait", "split_portrait", frozenset({"a3"}), ("headline",), needs_image=True),
    # the dots-and-spine column only reads as a connected process with enough
    # rows: 3 one-liners spread over the sheet as floating dots (the 2026-07-14
    # sparse-timeline critique); thin step sets route to the fill layout whose
    # numbered bands flex to the page instead.
    _treatment("a4_vertical_timeline", "timeline", frozenset({"a4"}), ("steps",),
               min_counts=(("steps", 4),)),
    _treatment("a4_bi_dashboard", "dashboard", frozenset({"a3", "a4"}), ("viz",)),
    _treatment("a4_metric_column", "metric", frozenset({"a4"}), ("stats",)),
    _treatment("a4_two_stack", "two_stack", frozenset({"a4"}), ("headline",)),
    # a4_editorial_fill: a REAL fixed-height fill layout for the text page types
    # (Outlook/About/Fazit/Collaboration) that otherwise fall to legacy patterns
    # and leave a dead bottom band. Distributes headline + body + numbered list +
    # synthesized stat rail + quote/CTA to the sheet edges. a4-only; needs only a
    # headline (everything else graceful-omits).
    _treatment("a4_editorial_fill", "editorial_fill", frozenset({"a4"}), ("headline",)),
    _treatment("a4_dark_divider", "dark_divider", frozenset({"a4"}), ("headline",)),
    _treatment("a4_quote_portrait", "quote", frozenset({"a4"}), ("quote",)),
    _treatment("a4_side_rail", "side_rail", frozenset({"a4"}), ("headline",)),
    _treatment("a4_stacked_hero", "stacked_hero", frozenset({"a4"}), ("headline",)),
    _treatment("a4_portrait_card", "portrait_card", frozenset({"a4"}), ("headline",), needs_image=True),
    # A3-landscape horizontal process flow (archetype "process"): the 6-step
    # framework laid LEFT-TO-RIGHT across the full A3 width with a result KPI. A3
    # only (the flow needs the wide sheet); required_fields ("steps",) is met by
    # the ST-06 adapt() output (its 6 steps), so an offered candidate fits.
    _treatment("horizontal_process", "process", frozenset({"a3"}), ("steps",)),
)


def register_all() -> None:
    """Register every catalog treatment into the shared TREATMENTS registry.

    Idempotent: register() replaces by name, so calling this more than once (it
    is called once on import, and a test may call it again) leaves the registry
    in the same state. Safe to call at import time and from a test setup.
    """
    for treatment in _CATALOG:
        register(treatment)


# Register on import so merely importing the catalog makes the treatments known
# to get_treatment / candidate_fits / the stylist.
register_all()
