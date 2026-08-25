"""Treatment STYLIST (Task TS-1.3): the per-page assignment engine.

Given a package's pages (in order) and a RenderContext, assign() decides, for
each page:
  (a) whether the page is TREATED at all (bypass types render legacy, untreated),
  (b) WHICH treatment (from an ordered, per-st_type candidate list, filtered to
      the ones that are registered, support the chosen format, and FIT the data),
  (c) WHICH page format (a3 for an A3 hero, else a4).

It is a PURE, deterministic function of the page index + data: no randomness, no
wall clock. The same package + ctx yields identical assignments every run. It
NEVER raises: it leans on the graceful engine helpers (candidate_fits returns
False on an unknown name or unmet contract) and guards against empty data, so a
page that has no candidate, or whose data fits none, is left untreated cleanly.

This module is BRAND-AGNOSTIC (scanned by the architecture guard): no client
name, no hex color, no font face, no per-client conditional branch. Every literal
here is a structural st_type code, a treatment NAME, a format code, or a reason
string. The candidate config maps a page TYPE to an ordered list of treatment
names; it keys only on the content type, never on who the client is.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from treatment_engine import (
    adapt,
    candidate_fits,
    get_treatment,
    meets_contract,
    treatment_is_built,
)

# --- bypass set --------------------------------------------------------------
# st_types that are NEVER treated: they own their full-bleed sheet (cover,
# back-cover CTA, breathers, dark dividers) and render through their legacy
# pattern. A bypass page gets treatment=None, page_format=None.
BYPASS_ST_TYPES: frozenset[str] = frozenset(
    {"ST-01", "ST-03", "ST-31", "ST-32", "ST-07B"}
)

# Default cap on how many pages may be promoted to A3 in one deck. Per Richard's
# rule (08_DMC_Design_System_v2 §D.3): a 20-page report carries ~2 THEMATIC
# spreads (Mechanismus+Diagramm, Zahlen+Kompetenz) plus the About editorial hero.
# Case studies are A4 single pages (Einzelseite), NOT auto-promoted. 4 leaves
# headroom for the hero + the ~2 thematic spreads + an occasional ST-07C
# exception, without letting the deck over-spend on large sheets.
DEFAULT_MAX_A3: int = 4

# Format codes (structural, not client data).
_A3 = "a3"
_A4 = "a4"

# Portrait slot probe order, mirroring treatment_engine._PORTRAIT_SLOT_ORDER, so
# the hero check (does a primary image resolve?) agrees with adapt()'s image.
_PORTRAIT_SLOTS: tuple[str, ...] = ("case_study_portrait", "founder", "about_portrait")

# The brand-agnostic slot id that carries the package's FOUNDER portrait, and the
# data key that carries the founder NAME + ROLE (an {name, role} dict). Both are
# structural keys defined by the package shape, not client data.
_FOUNDER_SLOT_ID = "founder"
_AUTHOR_KEY = "author"


# --- the candidate config ----------------------------------------------------
# Ordered candidate treatment names per st_type, BEST-FIT FIRST (richest fitting
# treatment first). The stylist walks them in this order (after filtering) and
# prefers the first that is unused deck-wide and not an adjacent repeat. Every
# candidate's required_fields is satisfiable by that st_type's adapt() output
# (verified against real apex), so a candidate offered to a page genuinely fits.
#
# The ABOUT page (ST-05) is the editorial HERO: its rich data (the 30-50% figure,
# the 100+/€200k+ figures, and the partner wall) is exactly what the A3 editorial
# spread was designed for, so `editorial` leads its candidate list and the page is
# promoted to A3 when editorial fits and its founder portrait resolves (see
# _is_hero). The A4 fallbacks remain for when A3 is unavailable (the A3 cap is hit
# or the portrait does not resolve).
#
# ST-07A (case study) leads with a4_case_study: a case study is an A4 SINGLE page
# (Einzelseite) by default, per Richard's rule. a3_case_study is ALSO listed but is
# a3-only, so the format filter (_fitting_candidates) selects it ONLY when the page
# has been promoted to A3 by the explicit ST-07C exception signal (see
# _wants_explicit_a3); at the default a4 format it is filtered out and a4_case_study
# leads. The remaining A4 entries are generic fallbacks if the case treatment ever
# fails its data contract.
_CANDIDATES: dict[str, list[str]] = {
    # a4_editorial_fill is the REAL fixed-height fill layout for TEXT-only pages:
    # it distributes headline + body + numbered list + synthesized stat rail +
    # quote/CTA to the sheet edges so the page FILLS instead of clumping at the top
    # over a dead bottom band. It requires only ("headline",) so it ALWAYS fits --
    # therefore it must sit AFTER any data-gated richer treatment (a dashboard
    # needs viz, a timeline needs steps): a data page still wins its rich layout,
    # and a text-only page (no viz/steps) falls through to the fill. It is the
    # graceful FALLBACK, not an override.
    "ST-02": ["a4_bi_dashboard", "a4_editorial_fill", "a4_two_stack", "a4_quote_portrait"],
    # ST-09: the DATA status-quo page. The CONTEXT continuation carries
    # data.viz (a dashboard-eligible rail) and is ST-09-continuation-EXEMPT, so
    # a4_bi_dashboard leads and wins when viz is present; the EVIDENCE page
    # (symptoms, no viz) fails the ("viz",) contract and falls through to the
    # fill. Dashboard sits BEFORE the always-fitting editorial_fill so it is not
    # shadowed by the repeatable-fill shortcut.
    "ST-09": ["a4_bi_dashboard", "a4_editorial_fill", "a4_two_stack", "a4_dark_divider"],
    # ST-05: the A3 editorial hero when a founder portrait resolves, else the fill
    # layout (not a bare legacy page). editorial-only left every portrait-less
    # About untreated (the 2026-07-11 portrait-less About regression).
    "ST-05": ["editorial", "a4_editorial_fill", "a4_side_rail"],
    # ST-14 has NO candidates on purpose: the legacy numbered-beliefs pattern (P-5,
    # universal across all references) renders beliefs[].irrglaube/realitaet; a
    # generic headline+body treatment would silently DROP the beliefs.
    "ST-14": [],
    "ST-07A": ["a4_case_study", "a3_case_study", "a4_two_stack", "a4_quote_portrait",
               "a4_metric_column", "a4_dark_divider", "a4_bi_dashboard"],  # A4 single leads; A3 only on ST-07C signal
    # ST-06 ends on a4_editorial_fill so a THIN mid-deck mechanism page (too few
    # steps for the timeline's min-count, horizontal_process gated to the deck
    # tail, a4_two_stack still an unbuilt stub) cannot dead-end on the silent
    # legacy fallback: _adapt_steps mirrors the steps into td.list_items, so the
    # fill layout renders them as its numbered bands.
    "ST-06": ["horizontal_process", "a4_vertical_timeline", "a4_two_stack",
              "a4_editorial_fill"],
    "ST-22": ["a4_vertical_timeline", "a4_editorial_fill", "a4_two_stack"],
    "ST-FAZIT": ["a4_editorial_fill", "a4_stacked_hero", "a4_two_stack"],
}

# ST-07A st_type code + its A3 exception treatment name (ST-07C). Structural, not
# client data.
_ST_CASE_STUDY = "ST-07A"
_CS_A3 = "a3_case_study"

# Treatments that INTENTIONALLY repeat across a deck and are therefore EXEMPT from
# the deck-wide dedup + no-adjacent variety rules. A report's case studies must
# ALL use the SAME case layout (design rule: never mix case-study variants within
# one report). Without this, the variety-seeking _choose would give only the FIRST
# case study the case treatment and scatter the rest onto generic fallbacks.
_REPEATABLE_TREATMENTS: frozenset[str] = frozenset(
    {"a4_case_study", "a3_case_study", "a4_editorial_fill"})

# The A3 candidate list for the page promoted to HERO (the About page). Kept
# separate from the per-st_type A4 lists so a hero uses the A3 archetypes
# (editorial first, then the other A3 families as fallbacks) and a non-hero page
# uses its A4 list above. editorial leads: the About page's data fits it best.
_HERO_CANDIDATES: list[str] = ["editorial", "glass_card", "split_portrait"]

# The st_type that is eligible to be the editorial A3 HERO when its founder
# portrait resolves (via the founder-identity fallback the assembler injects).
_HERO_ST_TYPE = "ST-05"


# --- the assignment record ---------------------------------------------------
@dataclass(frozen=True)
class PageAssignment:
    """One page's treatment decision.

    index       : the page's position in the package (0-based).
    slot        : the page's slot id (copied verbatim; provenance for wiring).
    st_type     : the page's content type code.
    treatment   : the chosen treatment NAME, or None when the page is left
                  untreated (a bypass type, or no candidate fit).
    page_format : "a3" / "a4" for a treated page, else None.
    reason      : a short, human-readable account of the decision (for the audit).
    """

    index: int
    slot: Any
    st_type: str
    treatment: Optional[str]
    page_format: Optional[str]
    reason: str


# --- founder identity (the brand-agnostic portrait fallback) -----------------
def founder_identity(pages: list[dict], ctx: Any) -> Optional[dict]:
    """The package's FOUNDER IDENTITY, computed ONCE from all pages, or None.

    Returns {"path", "author"} where:
      - "path" is the package-relative path of the FIRST resolved `founder` slot
        found across the pages (verbatim, the package's founder portrait), and
      - "author" is the FIRST `author` dict (a {name, role} shape) found on any
        page's `data`.
    Brand-agnostic: it scans only the structural `founder` slot id and the
    `author` data key, never a client path or name. Returns None unless BOTH a
    resolved founder slot path AND an author are found (an image-led page can
    only borrow a COMPLETE identity: a portrait WITH a name + role). Never
    raises: it reads with .get and skips malformed entries.

    This is the mechanism that lets an image-led treatment on a page that has NO
    portrait of its own (the About page) fall back to the package's founder
    portrait + name + role. The assembler injects the result onto such a page
    BEFORE rendering, so adapt()'s `_primary_image` probe and `_adapt_st05`'s
    author->caption read resolve it.
    """
    path: Optional[str] = None
    author: Optional[dict] = None
    for page in pages:
        if not isinstance(page, dict):
            continue
        if path is None:
            for s in (page.get("slots") or []):
                if not isinstance(s, dict):
                    continue
                if s.get("slot_id") == _FOUNDER_SLOT_ID and s.get("status") == "resolved":
                    candidate = s.get("path")
                    if candidate and ctx.resolve_asset(candidate) is not None:
                        path = candidate
                        break
        if author is None:
            data = page.get("data") or {}
            if isinstance(data, dict):
                a = data.get(_AUTHOR_KEY)
                if isinstance(a, dict) and (a.get("name") or a.get("role")):
                    author = a
        if path is not None and author is not None:
            break
    if path is None or author is None:
        return None
    return {"path": path, "author": author}


# --- small helpers -----------------------------------------------------------
def _is_hero(page: dict, ctx: Any, has_founder: bool) -> bool:
    """True iff this page should be an A3 HERO.

    The rule is data-gated (no per-st_type fixture flag required):
      - an explicit page_role == "hero" (a future deck may set this), OR
      - the ABOUT page (ST-05) when a founder portrait is available package-wide
        (`has_founder`, computed once by founder_identity). The About page has no
        portrait of its OWN, so the hero gate keys on the package founder rather
        than the page's own image: the assembler injects that founder identity
        onto the page before rendering, so the editorial portrait column resolves.
    Honors an explicit hero flag without REQUIRING it. Never raises.
    """
    if str(page.get("page_role") or "").strip().lower() == "hero":
        return True
    if str(page.get("st_type") or "") == _HERO_ST_TYPE:
        return has_founder
    return False


def _wants_a3_process(st_type: str) -> Optional[str]:
    """The A3-ONLY lead candidate for a non-hero page that should be PROMOTED to
    A3, or None.

    A non-hero page is "a3-preferring" when its FIRST configured candidate is a
    registered treatment whose only supported format is a3 (an a3-exclusive
    layout, e.g. the horizontal_process flow that needs the wide A3 sheet). Such a
    page is promoted to A3 (subject to the A3 cap + the data fit), so the
    a3-exclusive layout is reachable without an explicit per-st_type branch. The
    return value is that lead candidate's NAME (for the audit), else None.

    Brand-agnostic + structural: it keys only on the st_type's candidate config +
    the treatment's declared formats, never on who the client is."""
    candidates = _CANDIDATES.get(st_type, [])
    if not candidates:
        return None
    lead = get_treatment(candidates[0])
    if lead is None:
        return None
    if lead.formats == frozenset({_A3}):
        return candidates[0]
    return None


def _wants_explicit_a3(page: dict) -> bool:
    """True iff a case-study page carries an EXPLICIT ST-07C (Doppelseite) signal.

    A case study is an A4 single page by default (Richard's rule). It is promoted
    to the A3 Doppelseite ONLY as an editorial exception (report #2/3, an
    exceptionally strong case with much proof, or a 28+ page report). That decision
    is made UPSTREAM and stamped on the page as an explicit signal; the stylist
    does not guess it. Recognised signals (any one): page_format == "a3", a
    truthy `case_study_spread` flag, or a truthy `data.doppelseite` flag. Absent
    all of them (the default) the page stays A4. Structural, brand-agnostic; never
    raises."""
    if str(page.get("page_format") or "").strip().lower() == _A3:
        return True
    if page.get("case_study_spread") is True:
        return True
    data = page.get("data")
    if isinstance(data, dict) and data.get("doppelseite") is True:
        return True
    return False


def _candidate_list(st_type: str, hero: bool) -> list[str]:
    """The ordered candidate names for this st_type + hero flag.

    A hero page uses the A3 hero list (editorial first); everything else uses the
    per-st_type non-hero list (empty for a type with no config, which yields an
    untreated page gracefully)."""
    if hero:
        return list(_HERO_CANDIDATES)
    return list(_CANDIDATES.get(st_type, []))


def _page_with_founder(page: dict, founder: Optional[dict]) -> dict:
    """A shallow page view with the founder identity injected as a resolved
    `founder` slot + an `author`, used ONLY for the fit check (and mirrored by the
    assembler at render time). Returns the page unchanged when there is no founder
    to inject or the page already has the slot. Never mutates the input.

    This makes candidate_fits honest for an image-led HERO whose own portrait is
    absent: the editorial treatment's needs_image gate sees the founder portrait
    the assembler WILL inject, so a fitting hero is not wrongly skipped."""
    if not founder:
        return page
    slots = list(page.get("slots") or [])
    if any(isinstance(s, dict) and s.get("slot_id") == _FOUNDER_SLOT_ID
           and s.get("status") == "resolved" for s in slots):
        return page
    view = dict(page)
    view["slots"] = slots + [{
        "slot_id": _FOUNDER_SLOT_ID,
        "status": "resolved",
        "path": founder["path"],
    }]
    data = dict(page.get("data") or {})
    data.setdefault(_AUTHOR_KEY, founder["author"])
    view["data"] = data
    return view


def _fitting_candidates(
    page: dict, ctx: Any, st_type: str, hero: bool, page_format: str
) -> list[str]:
    """The candidate names that are registered, support `page_format`, and FIT
    the page's data, preserving the configured order.

    `page` here is the fit-view (founder injected for an image-led hero) so an
    image-led hero whose portrait the assembler will inject is not wrongly
    skipped.

    PERF: adapt(page, ctx) runs ONCE for the whole candidate list, not once per
    candidate. Routing every check through candidate_fits() re-ran the full
    adapt (component-SVG disk reads + portrait slot probes) O(candidates) times
    per page; the page object is not mutated between these checks, so one td
    serves every meets_contract() test. Same gates as candidate_fits:
    registered, BUILT (a metadata-only stub must never be assigned), format,
    contract."""
    names = [
        name for name in _candidate_list(st_type, hero)
        if (t := get_treatment(name)) is not None
        and page_format in t.formats
        and treatment_is_built(name)
    ]
    if not names:
        return []
    td = adapt(page, ctx)
    return [name for name in names if meets_contract(td, get_treatment(name))]


def _choose(
    fitting: list[str],
    hero: bool,
    used: set[str],
    prev_adjacent_treatment: Optional[str],
) -> tuple[str, str]:
    """BEST-FIT-FIRST selection with deck-wide dedup + no-adjacent-repeat.

    Returns (chosen_name, reason). `fitting` is non-empty (callers guard that)
    and is in CONFIGURED best-fit order (richest fitting treatment first).

    The index is NOT used as a rotation seed. Determinism comes from the fixed
    page order + the `used` set (treatments chosen by earlier TREATED pages).
    No randomness, no wall clock.

    POLICY:
      HERO pages: take the FIRST fitting candidate outright (no dedup, no
        no-adjacent). The hero list is already richest-first, so its first
        fitting archetype is the one we want (e.g. 'editorial').

      NON-HERO pages: walk `fitting` IN ORDER (best-first) and apply the first
        rule that yields a candidate:
        (a) BEST-FIT, UNUSED: first candidate that is BOTH unused deck-wide AND
            differs from the immediately-preceding treated page (no-adjacent ok).
        (b) REUSED: relax dedup. First candidate that satisfies no-adjacent
            (allowing a deck-wide reuse).
        (c) RELAXED NO-ADJACENT: relax adjacency too (only when the sole fit
            equals the neighbor). First fitting candidate, unconditionally.
      The relaxation level used is recorded in the reason. Never raises; never
      leaves a fitting page unassigned.

    `used` is the deck-wide set of treatments already chosen by earlier treated
    pages (the caller adds each chosen treatment after the fact).
    `prev_adjacent_treatment` is the treatment of page index-1 ONLY when that
    page was treated; otherwise None (so no-adjacent is not enforced)."""
    n = len(fitting)

    # HERO: first fitting candidate, no dedup / no-adjacent.
    if hero:
        chosen = fitting[0]
        return chosen, f"hero; first fitting '{chosen}' (of {n})"

    # REPEATABLE: a case-study treatment that is the best fit is taken outright
    # (no dedup, no no-adjacent) so EVERY case study in the report renders through
    # the SAME case layout (design rule: never mix case variants).
    if fitting[0] in _REPEATABLE_TREATMENTS:
        return fitting[0], f"repeatable best-fit '{fitting[0]}' (of {n})"

    def _ok_adjacent(name: str) -> bool:
        return prev_adjacent_treatment is None or name != prev_adjacent_treatment

    # (a) best-fit AND unused deck-wide AND no-adjacent ok.
    for name in fitting:
        if name not in used and _ok_adjacent(name):
            return name, f"best-fit, unused '{name}' (of {n}); no-adjacent ok"

    # (b) relax dedup: first no-adjacent-ok candidate (allowing a reuse).
    for name in fitting:
        if _ok_adjacent(name):
            return name, (
                f"reused (all best candidates used) '{name}' (of {n}); "
                f"no-adjacent ok"
            )

    # (c) relax no-adjacent: only the neighbor's treatment fits. Take the first
    #     fitting candidate anyway (variety yields to having a treatment).
    chosen = fitting[0]
    return chosen, (
        f"relaxed no-adjacent: only candidate(s) equal neighbor "
        f"'{prev_adjacent_treatment}', took best-fit '{chosen}' (of {n})"
    )


# --- the public entry point --------------------------------------------------
def assign(
    pages: list[dict], ctx: Any, max_a3: int = DEFAULT_MAX_A3
) -> list[PageAssignment]:
    """Assign a treatment + format to every page in order. Pure + total.

    For each page:
      1. BYPASS types -> untreated (treatment None, format None).
      2. Determine hero/format (honoring the A3 cap counter): a hero wants A3, but
         if promoting it would exceed `max_a3`, fall back to A4 (and the non-hero
         candidate list at A4). Non-hero A3 promotions are additionally
         TAIL-GATED: only a page in the final quarter of the deck
         (index >= 3*len(pages)//4) may promote (see the tail-gate note below).
      3. Filter the ordered (best-fit-first) candidate list to registered +
         format-supporting + data-fitting names.
      4. No fitting candidate -> untreated ("no fitting candidate").
      5. Best-fit-first selection with deck-wide dedup + no-adjacent-repeat
         (see _choose).
      6. Record; if A3, increment the A3 counter; add the chosen treatment to
         the deck-wide used set.

    Deterministic: depends only on the page order + data + ctx (no rotation
    seed). Never raises.
    """
    assignments: list[PageAssignment] = []
    a3_used = 0
    # The package FOUNDER IDENTITY (portrait path + author), computed ONCE from
    # all pages. An image-led HERO page that has no portrait of its own (the About
    # page) borrows this; None when the package carries no founder identity (then
    # the About page is not a hero and falls back to its A4 candidates). See
    # founder_identity + _page_with_founder + _is_hero.
    founder = founder_identity(pages, ctx)
    has_founder = founder is not None
    # Treatments chosen by earlier TREATED pages, deck-wide. Drives the dedup
    # preference in _choose (prefer an as-yet-unused treatment). Bypass /
    # untreated pages do not contribute. Heroes DO add their treatment so a
    # later page does not redundantly reuse it when an unused option fits.
    used: set[str] = set()
    # The treatment of the immediately-preceding page, ONLY if that page was
    # treated. Reset to None after any bypass / untreated page so no-adjacent is
    # enforced strictly against the page at index-1 (the spec's definition).
    prev_treatment: Optional[str] = None

    for index, page in enumerate(pages):
        if not isinstance(page, dict):
            # Defensive: a non-dict page is left untreated (never crash).
            assignments.append(
                PageAssignment(index, None, "", None, None, "bypass (non-dict page)")
            )
            prev_treatment = None
            continue

        st_type = str(page.get("st_type") or "")
        slot = page.get("slot")

        # US-604: CONTINUATION pages (a section's 2nd+ physical page) are not
        # independent pages needing their own treatment; they belong to the
        # section's first page's composition. Leave them untreated (the
        # section's own pattern renders them) and reset adjacency so the next
        # treated page isn't blocked.
        # US-2026-08-18 (ST-09): EXCEPTION : the ST-09 split (context/evidence)
        # halves render SPARSE through the legacy st_09 pattern (a body-only
        # context page and a symptoms-only evidence page each leave the sheet
        # half-empty; verified on pixels). The a4_editorial_fill treatment
        # handles BOTH shapes well (prose fill + the dense symptom grid), so
        # ST-09 continuation pages ARE treated.
        # US-2026-08-25 (ST-06): the MECHANISM continuation is the 6-step
        # diagram's OWN showcase page. It must be TREATED too — the whole point
        # of the page is a device (a process flow), and re-assembling its full
        # steps (assemble_package now attaches them) lets the wide A3
        # horizontal_process treatment render them legibly instead of the
        # chopped A4 legacy strip. Continuations that are NOT a device showcase
        # (intro / result) stay untreated.
        _cont_role = str(page.get("continuation_role") or "").strip()
        if (
            page.get("continuation_index") is not None
            and st_type not in ("ST-09",)
            and not (st_type == "ST-06" and _cont_role == "mechanism")
        ):
            assignments.append(
                PageAssignment(
                    index, slot, st_type, None, None,
                    f"bypass (continuation {page.get('continuation_index')} "
                    f"of {page.get('section_page_count')})",
                )
            )
            prev_treatment = None
            continue

        # 1. bypass types render legacy, untreated.
        if st_type in BYPASS_ST_TYPES:
            assignments.append(
                PageAssignment(index, slot, st_type, None, None, f"bypass ({st_type})")
            )
            prev_treatment = None
            continue

        # 2. hero / format decision, honoring the A3 cap.
        wants_hero = _is_hero(page, ctx, has_founder)
        hero = False
        page_format = _A4
        cap_note = ""
        if wants_hero:
            # US-2026-08-25: the A3 HERO stays on its A4 treatment. The mid-deck
            # A3 wall is removed for the MECHANISM spread (horizontal_process,
            # ST-06's wide diagram showcase — verified clean: 26pp, A3 pages
            # unchanged, neighbours full-height, no spill). The ABOUT hero goes
            # on a4_editorial_fill (which carries the founder portrait) by
            # design, not by a suspension; case-study A3 (explicit a3 signal)
            # also stays A4 unless the continuation mechanism needs it.
            cap_note = ""
        else:
            # A non-hero page whose lead candidate is an A3-ONLY layout (e.g. the
            # horizontal_process flow) is PROMOTED to A3 when the cap allows AND
            # that A3 candidate actually fits the page's data. If any gate fails,
            # it stays A4 and uses its A4 fallbacks.
            # US-2026-08-25: the mid-deck A3 wall is REMOVED. It was added under
            # the 2026-07 "mixed-size print compresses A4 to ~71%" finding, which
            # is STALE after the engine moved to per-format `@page` routing
            # (.format-a3 -> a3-landscape). Verified EMPIRICALLY on this engine:
            # a forced mid-deck A3 (index 19 of 26) renders 26pp, A3 intact
            # (1191x842) alongside 595x842 A4s, no spill, overlap CLEAN. The
            # real safety net is the renderer's overflow/physical-vs-logical
            # guard, not a position-based wall. The A3 cap still binds.
            a3_lead = _wants_a3_process(st_type)
            if a3_lead is not None:
                if a3_used < max_a3 and candidate_fits(page, ctx, a3_lead):
                    page_format = _A3
                elif a3_used >= max_a3:
                    cap_note = f" (a3 cap {max_a3} hit, fell back to a4)"
            elif st_type == _ST_CASE_STUDY and _wants_explicit_a3(page):
                # US-2026-08-18: an explicit `page_format: "a3"` is NOT honored
                # as an A3 promotion. The mixed-size print defect is PROVEN by
                # investigation: a mid-deck A3 named page makes Chromium
                # compress EVERY A4 page to ~92% (the cover/breathers rendered
                # with 25-40% white bottoms : the exact measured defect).
                # Until the engine prints per-format and merges, ALL case
                # studies render A4 (a4_case_study leads the candidate list).
                cap_note = " (a3 signal overridden: mixed-size A3 compresses A4 pages - render A4)" 

        # 3. filter candidates to the ones that fit at the chosen format. A HERO
        #    page that has no portrait of its own borrows the founder identity for
        #    the fit check (the assembler injects the same identity at render
        #    time), so an image-led hero is not wrongly skipped.
        fit_page = _page_with_founder(page, founder) if hero else page
        fitting = _fitting_candidates(fit_page, ctx, st_type, hero, page_format)

        # 4. nothing fits -> untreated, gracefully.
        if not fitting:
            assignments.append(
                PageAssignment(
                    index, slot, st_type, None, None,
                    "no fitting candidate" + cap_note,
                )
            )
            prev_treatment = None
            continue

        # 5. best-fit-first selection with deck-wide dedup + no-adjacent-repeat.
        chosen, reason = _choose(fitting, hero, used, prev_treatment)
        if cap_note:
            reason += cap_note

        assignments.append(
            PageAssignment(index, slot, st_type, chosen, page_format, reason)
        )

        # 6. update counters / dedup set / adjacency.
        if page_format == _A3:
            a3_used += 1
        used.add(chosen)
        prev_treatment = chosen

    return assignments


# --- the audit view ----------------------------------------------------------
def audit_lines(assignments: list[PageAssignment]) -> list[str]:
    """One readable line per page for an eyeball pass.

    Examples:
      "p01 ST-01 -> (bypass)"
      "p06 ST-07A -> a4_two_stack [a4]  (candidate 'a4_two_stack' (of 5); ...)"
      "p11 ST-07A -> editorial [a3]  (hero; candidate 'editorial' (of 3); ...)"
    Total lines == number of assignments (one per page)."""
    lines: list[str] = []
    for a in assignments:
        tag = f"p{a.index:02d} {a.st_type}"
        if a.treatment is None:
            if a.reason.lower().startswith("bypass"):
                lines.append(f"{tag} -> (bypass)  ({a.reason})")
            else:
                lines.append(f"{tag} -> (untreated)  ({a.reason})")
        else:
            lines.append(f"{tag} -> {a.treatment} [{a.page_format}]  ({a.reason})")
    return lines
