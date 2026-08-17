"""Layout-type system (code-embedded).

The deck is composed from SIX distinct page-layout types, not one reused
template. This module is the single source of truth that binds each report
section (ST-type) to its layout type and records the structural recipe each
layout must follow. The per-ST patterns/templates implement these recipes; this
registry is what makes the "different layouts" real in code and lets tests +
tooling assert that every page has a deliberate, distinct layout.

Canonical spec: docs/superpowers/specs/2026-06-14-richard-design-system-EXTRACTED.md
(+ ...-infographic-vocabulary-EXTRACTED.md). Foundation: cream ground, navy ink,
muted teal micro-accent (exact hex live in the spec + the brand tokens, never
inlined here), tasteful neutral depth (NO neon glow), every page carries a
matched visual, fill the page, no page-count limit. Enforced by
tests/test_design_conformance.py.
"""
from __future__ import annotations

# The six layout types and their structural recipe (what the template must do).
LAYOUT_RECIPES: dict[str, str] = {
    "cover": (
        "Founder hero photo (bounded, ~half the page) + serif headline with 1-2 "
        "teal keyword accents in the opposite half + eyebrow/wordmark + a stat "
        "band. Cream ground, asymmetric, generous breathing. No banner."
    ),
    "content": (
        "Floating header (eyebrow + serif headline w/ teal keywords + sans "
        "subhead, optional ghost numeral upper-right), then a 2-column body with "
        "ONE paired visual sharing the same Y-band as its paragraph. Fills the "
        "page; understated footer."
    ),
    "case_study": (
        "Asymmetric: wide LEFT narrative column (~62%) with the section markers "
        "(Ausgangssituation/Ziel/Lösung/Ergebnis) + one floating insight viz; a "
        "NARROW RIGHT rail (~32%) sized to its content (portrait + name/role/url "
        "+ 2-3 stacked stat cards + pull-quote) that NEVER stretches full-height "
        "and never clips. Rotated 'FALLSTUDIE 0X' side-label on the trim. One "
        "hero transformation viz fills the bottom."
    ),
    "data": (
        "Balanced ~50/50: serif headline + intro + optional numbered points on "
        "the LEFT; ONE hero chart given its own half on the RIGHT, on cream "
        "(transparent, faint grid, teal series), sharing the headline's Y-band. "
        "One chart, its own pocket, never wedged."
    ),
    "fact_sheet": (
        "Body prose LEFT (~60%) + a RIGHT column of 3-5 stacked stat-rail cards "
        "(or a diagram). Optional soft-tint callout band. Cards float on cream; "
        "no full-height fill."
    ),
    "closing": (
        "The ONE dark page: full-bleed navy/deep-teal ground, centered white "
        "serif statement, sans subline, eyebrow above, CTA as a plain white link "
        "or small QR bottom-center. Abandons the 2-col grid; monumental."
    ),
}

# Every report section (ST-type) -> its layout type. A page with no entry falls
# back to "content" (the safe general editorial template).
ST_TO_LAYOUT: dict[str, str] = {
    "ST-01": "cover",
    "ST-02": "content",     # outlook
    "ST-05": "fact_sheet",  # about / in Zahlen
    "ST-06": "data",        # framework (process + efficiency figure)
    "ST-07A": "case_study",
    "ST-07B": "content",    # dark-divider thesis -> editorial content
    "ST-09": "content",     # status quo
    "ST-14": "fact_sheet",  # myths (numbered + convergence diagram)
    "ST-22": "data",        # engagement timeline
    "ST-31": "content",     # breather / scene
    "ST-FAZIT": "closing",
    "ST-03": "closing",     # back-cover CTA
}

_DEFAULT = "content"


def layout_type_for(st_type: str) -> str:
    """Return the layout type for an ST-type (default 'content')."""
    return ST_TO_LAYOUT.get(str(st_type), _DEFAULT)


def recipe_for(st_type: str) -> str:
    """Return the structural recipe string for an ST-type's layout."""
    return LAYOUT_RECIPES[layout_type_for(st_type)]
