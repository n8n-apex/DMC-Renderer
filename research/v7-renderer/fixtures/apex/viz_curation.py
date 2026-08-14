"""APEX viz curation — hand-mapped data-viz PRESET specs for the apex deck.

CLIENT DATA, by design: this fixture module carries APEX's real figures and
binds them to the renderer's brand-agnostic viz presets (the renderer + the
dispatch + the macros contain ZERO client literals; the numbers live HERE). It
is exempt from `test_no_literals_in_architecture.py` (which scans templates/
styles/ patterns/ components/, never fixtures/).

NO FABRICATION — enforced structurally: every figure a preset DISPLAYS must
already appear, verbatim, in that page's own data. `apply_apex_viz` re-checks
each displayed figure with `_figure_grounded` and FAILS LOUD if any is not
grounded. Geometry numbers (percent for arcs, magnitude for bars) are derived
from the same verbatim string at render time, so they cannot diverge from what
the reader sees. The only NON-grounded value allowed is a `delta` pill on
ba_bars — honest arithmetic on the two real before/after figures (e.g. 30→2 is
−93 %), shown beside both operands so the reader can verify it.

Phasing: this module grows family-by-family. Phase 1 binds the TRANSFORMATION
presets (ba_bars / transform_arrow / completion_ring) onto the five ST-07A case
studies (matched by fallstudie_number 1..5). Phase 2 adds the PROPORTION
radial_cluster onto ST-FAZIT. Phase 4 adds MAGNITUDE (stat_strip on ST-02
Outlook, mega_numeral on ST-09 Status-Quo) and PROCESS (step_cascade on ST-06
Mechanism), one well-grounded preset per host page; pages with no clean verbatim
figure are SKIPPED rather than forced.
"""
from __future__ import annotations

import json
import re
import unicodedata

# ---- grounding (no-fabrication) -------------------------------------------

_WS_RE = re.compile(r"\s+")
_DIGITS_ONLY_RE = re.compile(r"^-?\d+$")


def _norm(s) -> str:
    """NFKC-normalize + collapse whitespace (so '24  Std.' == '24 Std.')."""
    return _WS_RE.sub(" ", unicodedata.normalize("NFKC", str(s or ""))).strip()


def _figure_grounded(figure, page: dict) -> bool:
    """True iff `figure` (a string the viz will DISPLAY) is present in the page.

    Two modes (LOCKED): a figure with any non-digit char must appear as a full
    normalized substring of the page-data JSON ('> 200.000 €', '6 von 6',
    '100 %'); a digits-only figure must match on digit boundaries (so '2' does
    NOT match inside '2025'/'20'). Empty figure → not grounded (caller skips).

    The evidence is the page's COPY: `data['viz']` is EXCLUDED (2026-07-16). A
    package that already carries a persisted viz (the apex fixture does) would
    otherwise let every figure ground itself - the device's own spec counted as
    proof that the page says the figure, so a figure could survive in the
    curation long after the copy that justified it was rewritten. That is how
    '8 Monate' and '50 %' kept passing while the pages actually read 'statt 8'
    and '50 Prozent'. Excluding the device STRENGTHENS the guarantee: a figure
    must come from what the page SAYS, never from what another device claims.
    """
    f = _norm(figure)
    if not f:
        return False
    evidence = {k: v for k, v in (page.get("data") or {}).items() if k != "viz"}
    pj = _norm(json.dumps(evidence, ensure_ascii=False))
    if _DIGITS_ONLY_RE.match(f):
        return re.search(r"(?<!\d)" + re.escape(f) + r"(?!\d)", pj) is not None
    return f in pj


def _spec_figures(spec: dict) -> list[str]:
    """The VERBATIM figure strings a preset will display (for grounding).

    Excludes geometry-only numbers (percent/magnitude/weight) and the optional
    ba_bars `delta` (derived arithmetic, not a copied figure). Covers every
    preset so later phases reuse this unchanged.
    """
    p = spec.get("preset")
    if p == "transform_arrow":
        return [(spec.get("from") or {}).get("value"), (spec.get("to") or {}).get("value")]
    if p == "completion_ring":
        return [spec.get("center")]
    if p == "ba_bars":
        out: list = []
        for pair in spec.get("pairs") or []:
            out.append((pair.get("before") or {}).get("value"))
            out.append((pair.get("after") or {}).get("value"))
        return out
    if p in ("money_bar", "mega_numeral", "kpi_card"):
        return [spec.get("value")]
    if p in ("donut", "gauge", "icon_array"):
        return [spec.get("figure")]
    if p == "split_bar":
        return [str((spec.get("a") or {}).get("percent")),
                str((spec.get("b") or {}).get("percent"))]
    if p == "radial_cluster":
        return [r.get("figure") for r in spec.get("rings") or []]
    if p == "stat_strip":
        return [it.get("value") for it in spec.get("items") or []]
    if p == "ranked_bars":
        return [it.get("figure") for it in spec.get("items") or []]
    if p == "phase_timeline":
        return [ph.get("duration") for ph in spec.get("phases") or []]
    if p == "step_cascade":
        return [s.get("title") for s in spec.get("steps") or []]
    return []


# ---- ST-07A case-study bindings (TRANSFORMATION family, Phase 1) -----------
# Keyed by fallstudie_number (1..5). Every DISPLAYED figure is copied VERBATIM
# from that page's own copy (ergebnis_headline / ergebnis_text /
# ergebnis_metrics); the grounding guard below enforces it. Deltas are honest
# arithmetic on the two real figures.
#
# REALIGNED 2026-07-16. The apex fixture's case studies were REPLACED at some
# point (fallstudie 1 was "Martina Ammon - Support / 24 Std. Antwortzeit"; the
# page now carries GoldmanTax / "Go-live in 2 Monaten statt 8"). The bindings
# below were still describing the OLD clients, so the guard correctly refused to
# print figures the pages no longer contain: '24 Std.' (1), '6 von 6' (2),
# '30'/'60' (4) and '100 %' (5) are all absent from the current copy. The guard
# was right; this table was stale. Each binding now names the client it belongs
# to, so the next replacement fails loudly here instead of drifting silently.

def _st07a_specs(fallstudie: int) -> list:
    if fallstudie == 1:   # GoldmanTax - Support-Einsparung + automatisierte Prozesse
        return [{"preset": "stat_strip", "items": [
            {"value": "> 200.000 €", "label": "Support-Einsparung pro Jahr"},
            {"value": "4", "label": "automatisierte Kernprozesse"}]}]
    if fallstudie == 2:   # Cordes Consulting - "6 von 6" Kernprozesse automatisiert
        return [{"preset": "completion_ring", "percent": 100, "figure": "6 von 6",
                 "label": "Kernprozesse automatisiert"}]
    if fallstudie == 3:   # Frese Recruiting - "von bis zu 24 Stunden auf Minuten"
        return [{"preset": "transform_arrow",
                 "from": {"value": "24 Stunden", "label": "Antwortzeit vorher"},
                 "to": {"value": "Minuten", "label": "mit APEX"}}]
    if fallstudie == 4:   # Conesso - "von 30 auf 2 Minuten" Onboarding-Zeit
        return [{"preset": "transform_arrow",
                 "from": {"value": "30 Minuten", "label": "Onboarding vorher"},
                 "to": {"value": "2 Minuten", "label": "mit APEX"}}]
    if fallstudie == 5:   # Hanisch & Klein - "100 % automatisiert" Lead-Priorisierung
        return [{"preset": "stat_strip", "items": [
            {"value": "100 %", "label": "Lead-Priorisierung automatisiert"}]}]
    return []


# ---- ST-FAZIT bindings (PROPORTION family, Phase 2) -----------------------
# The summary page's market-proof percentages (verbatim, no-space form as in the
# FAZIT body: '58%', '61%'). A compact radial cluster reinforces the thesis.

def _stfazit_specs() -> list:
    return [{"preset": "radial_cluster", "source": "KPMG 2026", "rings": [
        {"percent": 58, "figure": "58%", "label": "B2B auf autonomen Systemen"},
        {"percent": 61, "figure": "61%", "label": "B2B skaliert agentic AI"}]}]


# ---- MAGNITUDE + PROCESS bindings (Phase 4) -------------------------------
# One well-grounded preset per candidate host page. Every DISPLAYED figure /
# title below is copied VERBATIM from that page's own body/steps in the apex
# package (verified by the grounding guard in apply_apex_viz). No fabrication:
# the geometry-only `percent` on stat cells is NOT shown; the bar magnitudes are
# derived at render time from the same verbatim strings.

def _st02_specs() -> list:
    """ST-02 OUTLOOK — a compact radial cluster (rings fit the page's dark
    island; the 3-item stat strip overflows — verified: 21-page spill). Each
    figure appears VERBATIM in the page body: '30 %' ("bis zu 30 % der
    gesamten Betriebskosten"), '60 %' ("warum 60 % der Unternehmen ... keinen
    messbaren Wert ... ziehen"), '30 bis 50 %' ("dabei 30 bis 50 % ihrer
    Betriebskosten eliminieren").
    """
    return [{"preset": "radial_cluster", "rings": [
        {"percent": 30, "figure": "30 %",
         "label": "der Betriebskosten gehen für manuelle Prozesse drauf"},
        {"percent": 60, "figure": "60 %",
         "label": "der Firmen ziehen keinen messbaren AI-Return"},
        {"percent": 50, "figure": "30 bis 50 %",
         "label": "der Betriebskosten sind eliminierbar"}],
        "source": "BCG 2025 · BCG 2026 · PwC 2026"}]


def _st09_specs() -> list:
    """ST-09 STATUS QUO — a single MAGNITUDE hero. '50 %' is a verbatim substring
    of the body ("Burnout betrifft heute rund 50 % aller Wissensarbeiter").
    """
    return [{"preset": "mega_numeral", "value": "50 %",
             "label": "der Wissensarbeiter sind heute von Burnout betroffen"}]


def _st06_specs(steps: list) -> list:
    """ST-06 MECHANISM — a PROCESS step_cascade built from the page's OWN step
    titles (verbatim). The horizontal flow strip only fires for <5 steps; the
    framework has 6, so the cascade is the at-a-glance overview of the same
    mechanism stages the cards detail. Titles are copied straight from the data.
    """
    titles = []
    for it in steps or []:
        t = it.get("title") if isinstance(it, dict) else str(it)
        if t:
            titles.append(str(t))
    if not titles:
        return []
    return [{"preset": "step_cascade", "title": "Der Ablauf",
             "steps": [{"title": t} for t in titles]}]


def _viz_for_page(page: dict) -> list:
    """Return the curated viz spec list for a page (empty list = none)."""
    st = page.get("st_type")
    d = page.get("data") or {}
    if st == "ST-07A":
        fs = d.get("fallstudie_number")
        try:
            return _st07a_specs(int(fs)) if fs is not None else []
        except (TypeError, ValueError):
            return []
    if st == "ST-FAZIT":
        return _stfazit_specs()
    if st == "ST-02":
        return _st02_specs()
    if st == "ST-09":
        return _st09_specs()
    # ST-06 step_cascade is DISABLED: the mechanism page already lists its 6
    # framework steps as content, so a cascade of the same steps both duplicates
    # them and overflows the sheet (verified: ST-06 split to a 2nd page). Re-enable
    # only with a compact, non-duplicative device that fits the mechanism layout.
    # if st == "ST-06":
    #     return _st06_specs(d.get("steps") or [])
    return []


def apply_apex_viz(pkg: dict) -> None:
    """Write data['viz'] (a list of preset specs) onto each curated apex page.

    Pure mutator (like apply_diagram_plan). FAILS LOUD if any displayed figure
    is not grounded in its page — the structural no-fabrication guarantee.
    """
    for page in pkg.get("pages", []):
        specs = _viz_for_page(page)
        if not specs:
            continue
        for spec in specs:
            for fig in _spec_figures(spec):
                if fig in (None, ""):
                    continue
                if not _figure_grounded(fig, page):
                    raise ValueError(
                        f"viz fabrication guard: figure {fig!r} (preset "
                        f"{spec.get('preset')!r}) is not grounded on page "
                        f"{page.get('st_type')} "
                        f"fallstudie={ (page.get('data') or {}).get('fallstudie_number') }"
                    )
        page.setdefault("data", {})["viz"] = specs
