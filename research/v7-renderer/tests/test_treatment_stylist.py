"""Tests for the treatment STYLIST (assignment engine, Task TS-1.3).

The DATA layer (TreatmentData + adapt) and the DISPATCH layer (Treatment
registry + render + candidate_fits) already exist in treatment_engine. THIS
layer adds:
  - treatment_catalog: the concrete Treatment descriptors (metadata only; their
    Jinja templates + CSS are authored in later tasks), self-registered on
    import via an idempotent register_all().
  - treatment_stylist: assign(pages, ctx) -> list[PageAssignment]. For each page
    it decides (a) treated vs bypass, (b) which treatment, (c) which page_format
    (a3 / a4). Deterministic, index-seeded, never raises.

These tests run against the REAL apex package so the assignment is exercised on
true data, plus one synthetic test for the A3 cap that builds fake hero pages
and a minimal ctx so the cap logic is checked without touching the fixture.

Run ONLY this file:
  python -m pytest tests/test_treatment_stylist.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from package_loader import load_package  # noqa: E402
from grammar_loader import load_grammar  # noqa: E402
from patterns.base import RenderContext  # noqa: E402
from treatment_engine import adapt, get_treatment, meets_contract  # noqa: E402

# Importing the catalog registers all the concrete treatments (idempotent).
import treatment_catalog  # noqa: E402,F401
from treatment_stylist import (  # noqa: E402
    BYPASS_ST_TYPES,
    PageAssignment,
    _page_with_founder,
    assign,
    audit_lines,
    founder_identity,
)

FIXTURE = ROOT / "fixtures" / "apex"

# The eligible (treated) apex indices and the bypass indices, per the verified
# apex deck. Bypass st_types: ST-01, ST-03, ST-31, ST-32, ST-07B.
# idx 4 (ST-14 Irrglauben) is LEGACY-BY-DESIGN: its candidate list is empty on
# purpose (the universal numbered-beliefs pattern P-5 renders beliefs[].irrglaube/
# realitaet; a generic headline+body treatment would silently DROP the beliefs),
# so it is deliberately NOT in the eligible set.
# US-604: the apex ST-06 section now spans TWO pages (intro + result
# continuation) — fixed index tuples are brittle. Indices are computed from
# the package by st_type + identity (durable; see _idx_of below).
_BYPASS_ST = ("ST-01", "ST-03", "ST-31", "ST-32", "ST-07B")


def _idx_of(pkg, st_type: str) -> int:
    for i, pg in enumerate(pkg.pages):
        if (str(pg.get("st_type")) == st_type
                and not pg.get("continuation_index")):
            return i
    raise AssertionError(f"no non-continuation {st_type}")


def _page_of(pkg, st_type: str, role=None) -> dict:
    """The page with `st_type`; when `role` is given it must also match
    continuation_role (US-604: ST-02/ST-05/ST-06/ST-FAZIT span continuation
    pages). With role=None a NON-continuation page is preferred, then the first
    page of that type."""
    for pg in pkg.pages:
        if str(pg.get("st_type")) != st_type:
            continue
        if role is None:
            if not pg.get("continuation_index"):
                return pg
        elif pg.get("continuation_role") == role:
            return pg
    for pg in pkg.pages:
        if str(pg.get("st_type")) == st_type:
            return pg
    raise AssertionError(f"no {st_type} page (role={role!r}) in the apex fixture")


def _st_by_idx(pkg):
    return [str(pg.get("st_type")) for pg in pkg.pages]


ELIGIBLE_IDX = ()      # computed per-package in the fixture-dependent tests
LEGACY_BY_DESIGN_IDX = ()
BYPASS_IDX = ()
# US-604: the editorial ABOUT hero (ST-05) now spans TWO continuation pages
# (identity + proof), and the ST-06 framework spans intro + result. Both are
# continuation-bypassed by the stylist (their sections' own patterns render
# them), so the deck has NO treated A3 page. The 5 case studies (ST-07A) are
# the A3-capable pages that remain: they stay A4 single pages (a4_case_study)
# unless an explicit ST-07C Doppelseite signal promotes one to the deck tail.
A3_TREATMENTS = {"editorial", "glass_card", "split_portrait"}


@pytest.fixture(scope="module")
def pkg():
    return load_package(FIXTURE)


@pytest.fixture(scope="module")
def ctx(pkg):
    return RenderContext(
        brand=pkg.brand,
        grammar=load_grammar(),
        package_dir=pkg.package_dir,
        report_assets=pkg.report_assets,
    )


@pytest.fixture(scope="module")
def assignments(pkg, ctx):
    return assign(pkg.pages, ctx)


def test_bypass_pages_never_treated(pkg, ctx, assignments):
    """Every bypass page (ST-01 / ST-03 / ST-31 / ST-07B) has treatment None and
    page_format None, with a bypass reason. Continuation pages are ALSO bypassed
    (they belong to their section's first page — US-604)."""
    for idx, a in enumerate(assignments):
        if a.st_type in BYPASS_ST_TYPES or (
            str(a.st_type) in ("ST-06", "ST-07A", "ST-22", "ST-FAZIT")
            and "continuation" in (a.reason or "").lower()
        ):
            assert a.treatment is None, f"idx {idx} got treated: {a.treatment}"
            assert a.page_format is None, f"idx {idx} got a format: {a.page_format}"
            assert "bypass" in a.reason.lower()


def test_all_eligible_pages_get_a_treatment(pkg, ctx, assignments):
    """Every eligible apex page gets a non-None treatment whose contract its data
    meets, and a page_format in {a3, a4}.

    The ABOUT page (the editorial hero) has no portrait of its OWN, so its data
    meets the needs_image editorial contract only WITH the founder identity
    injected (the assembler injects the same identity at render time). The fit
    check here mirrors that: it adapts the founder-injected page for the hero.
    """
    founder = founder_identity(pkg.pages, ctx)
    for idx, a in enumerate(assignments):
        if a.st_type in BYPASS_ST_TYPES or (
            "continuation" in (a.reason or "").lower()
        ):
            continue
        if a.st_type == "ST-14":
            # LEGACY-BY-DESIGN: ST-14 has an empty candidate list on purpose
            # (the universal beliefs pattern renders its data; a generic
            # treatment would silently drop the beliefs).
            assert a.treatment is None, f"idx {idx} ST-14 must stay untreated"
            continue
        assert a.treatment is not None, f"idx {idx} ({a.st_type}) left untreated"
        assert a.page_format in {"a3", "a4"}, f"idx {idx} format {a.page_format}"
        treatment = get_treatment(a.treatment)
        assert treatment is not None, f"idx {idx} -> unregistered {a.treatment}"
        # an image-led hero (the editorial About page) is checked against the
        # founder-injected page view, exactly as the stylist + assembler do.
        fit_page = pkg.pages[idx]
        if a.page_format == "a3" and treatment.needs_image:
            fit_page = _page_with_founder(fit_page, founder)
        td = adapt(fit_page, ctx)
        assert meets_contract(td, treatment), (
            f"idx {idx} ({a.st_type}) -> {a.treatment} but data fails contract"
        )
        # the chosen format must be one the treatment supports
        assert a.page_format in treatment.formats


def test_hero_is_a3_editorial(pkg, ctx):
    """US-2026-08-25: the A3 HERO stays on a4_editorial_fill (which carries the
    injected founder portrait). A hero's A3 promotion is NOT an independent
    design goal; the About page renders A4 by design. (The old 2026-07
    "suspended" reason tied it to the now-fixed mid-deck A3 wall; only the
    mechanism showcase uses A3.)"""
    import copy
    hero_page = copy.deepcopy(_page_of(pkg, "ST-05", role="identity"))
    for k in ("page_id", "section_id", "continuation_index",
              "continuation_role", "section_page_count"):
        hero_page.pop(k, None)
    # the deck's founder identity (cover) makes the About page hero-eligible.
    pages = [pkg.pages[0], hero_page]
    hero = assign(pages, ctx)[1]
    assert hero.st_type == "ST-05", f"hero st_type {hero.st_type}"
    assert hero.page_format == "a4"
    assert hero.treatment == "a4_editorial_fill", f"about -> {hero.treatment}"


def test_no_a3_pages_mixed_size_breaks_print(pkg, ctx, assignments):
    """US-2026-08-25 REPLACES the old 2026-08-18 "no A3" assertion: the mid-deck
    A3 wall was removed after EMPIRICAL verification on the current engine that
    a single device-showcase A3 (the ST-06 mechanism spread) renders cleanly
    beside full-height A4s (26pp, no compression, no spill, overlap CLEAN).
    The ST-06 MECHANISM continuation IS that A3 showcase (horizontal_process).
    Everything else stays A4: the 5 case studies use a4_case_study, and the
    ST-06 intro/result continuations stay untreated."""
    a3_indices = [a.index for a in assignments if a.page_format == "a3"]
    # exactly ONE A3: the mechanism showcase page
    assert a3_indices, "expected the ST-06 mechanism showcase to be A3"
    assert len(a3_indices) == 1, f"expected exactly one A3 page; got {a3_indices}"
    for idx in a3_indices:
        a = assignments[idx]
        assert a.st_type == "ST-06", f"A3 must be the ST-06 mechanism page; got {a.st_type}"
        assert a.treatment == "horizontal_process", f"A3 -> {a.treatment}"
    # the 5 case studies stay A4 (a4_case_study) — case A3 stays A4 by design.
    case_indices = [a.index for a in assignments if a.st_type == "ST-07A"]
    assert len(case_indices) == 5, f"expected 5 case studies; got {case_indices}"
    for idx in case_indices:
        a = assignments[idx]
        assert a.page_format == "a4", f"idx {idx} format {a.page_format}"
        assert a.treatment == "a4_case_study", f"idx {idx} -> {a.treatment}"
    # ST-06: mechanism treated; intro + result continuation-bypassed.
    st06 = [a for a in assignments if a.st_type == "ST-06"]
    assert len(st06) == 3, f"expected 3 ST-06 pages; got {len(st06)}"
    treated = [a for a in st06 if a.treatment is not None]
    assert len(treated) == 1 and treated[0].treatment == "horizontal_process"


def test_st07a_no_longer_editorial(pkg, ctx, assignments):
    """The ST-07A case-study pages never route to the A3 editorial: every
    ST-07A page is an A4 case treatment (the former editorial hero is now an A4
    treatment). US-604 shifted the case studies' indices, so they are located by
    type (the 5 ST-07A pages). US-2026-08-18: they are a4_case_study (never a3)."""
    case_indices = [a.index for a in assignments if a.st_type == "ST-07A"]
    assert len(case_indices) == 5, f"expected 5 case studies; got {case_indices}"
    for idx in case_indices:
        a = assignments[idx]
        assert a.st_type == "ST-07A"
        assert a.treatment != "editorial", f"idx {idx} still editorial"
        # explicit page_format:a3 signal -> overridden to A4 (mixed-size fix)
        assert a.page_format == "a4", f"idx {idx} format {a.page_format}"
        assert a.treatment == "a4_case_study", f"idx {idx} -> {a.treatment}"


def test_best_fit_singletons(pkg, ctx, assignments):
    """Best-fit-first picks each page's richest fitting BUILT treatment (subject
    to deck-wide dedup). US-604: ST-02/ST-05/ST-06/ST-FAZIT now span continuation
    pages (context/evidence, identity/proof, intro/result, close/result), so
    those sections are continuation-bypassed by the stylist:
      ST-02 / ST-05  -> continuation-bypassed (the section's own patterns
             render the pages; a4_bi_dashboard / a4_editorial_fill for the
             pre-continuation single pages are no longer assigned)
      ST-06          -> INTRO + RESULT continuation-bypassed; the MECHANISM
             continuation is the 6-step diagram's OWN showcase and IS treated
             (horizontal_process A3) since US-2026-08-25.
      ST-22          -> a4_vertical_timeline (ST-22 stays A4; its own #1)
    """
    # ST-02 and ST-05 pages are all continuation-bypassed.
    for st in ("ST-02", "ST-05"):
        pages = [a for a in assignments if a.st_type == st]
        assert pages, f"{st} pages missing from assignments"
        assert all(a.treatment is None for a in pages), (
            f"{st} continuation pages must be bypassed"
        )
        assert all(a.page_format is None for a in pages)
    # ST-06: intro + result bypassed; the mechanism showcase is TREATED.
    st06 = [a for a in assignments if a.st_type == "ST-06"]
    assert st06, "ST-06 pages missing from assignments"
    mechanism = [a for a in st06 if (a.reason or "") and "mechanism" in a.reason.lower() or (a.treatment == "horizontal_process")]
    bypassed = [a for a in st06 if a not in mechanism]
    assert all(a.treatment is None and a.page_format is None for a in bypassed)
    assert any(a.treatment == "horizontal_process" and a.page_format == "a3"
               for a in st06), "the mechanism showcase must be the A3 horizontal_process"
    # ST-22 keeps the A4 vertical timeline (it is NOT promoted to A3).
    st22 = [a for a in assignments if a.st_type == "ST-22"]
    assert st22 and st22[0].treatment == "a4_vertical_timeline"
    assert st22[0].page_format == "a4"


def test_adjacent_case_studies_share_the_case_treatment(pkg, ctx, assignments):
    """The 5 ST-07A case studies ALL use a4_case_study (the adjacent tail pair
    included).

    A report's case studies must all share the SAME case layout (design rule:
    never mix case variants within one report), so the case treatment is EXEMPT
    from the no-adjacent-repeat variety rule that applies to other page types.
    US-2026-08-18: A4 always (the a3 mixed-size print defect)."""
    case_indices = [a.index for a in assignments if a.st_type == "ST-07A"]
    assert len(case_indices) == 5
    for idx in case_indices:
        a = assignments[idx]
        assert a.treatment == "a4_case_study", f"idx {idx} -> {a.treatment}"
        assert a.page_format == "a4", f"idx {idx} format {a.page_format}"


def test_deterministic(pkg, ctx):
    """Two assign() runs on the same package + ctx yield identical assignments."""
    a = assign(pkg.pages, ctx)
    b = assign(pkg.pages, ctx)
    assert a == b


def test_needs_image_gate(pkg, ctx, assignments):
    """A needs_image treatment (split_portrait) is only ever assigned where the
    page's image resolves; ST-07A non-hero pages (no image) never get a
    needs_image treatment.

    The editorial About hero has no portrait of its OWN; its image resolves via
    the founder identity the assembler injects at render time. So its needs_image
    gate is checked against the founder-injected page view (mirroring the
    assembler), not the bare page."""
    founder = founder_identity(pkg.pages, ctx)
    for a in assignments:
        if a.treatment is None:
            continue
        treatment = get_treatment(a.treatment)
        if treatment is not None and treatment.needs_image:
            page = pkg.pages[a.index]
            if a.page_format == "a3":
                page = _page_with_founder(page, founder)
            td = adapt(page, ctx)
            assert td.image, (
                f"idx {a.index} got needs_image treatment {a.treatment} "
                f"but has no resolved image"
            )

    # the ST-07A case studies all use a4_case_study (needs_image=False, so it
    # renders whether or not a portrait resolves); they are never assigned a
    # needs_image treatment (split_portrait / editorial). US-604 shifted the
    # case-study indices, so they are located by type; idx 13 (the Frese hero
    # with the resolved portrait) is the exception, excluded here.
    case_indices = [a.index for a in assignments if a.st_type == "ST-07A"]
    portrait_less = [
        idx for idx in case_indices
        if not any(s.get("slot_id") == "case_study_portrait"
                   and s.get("status") == "resolved"
                   for s in (pkg.pages[idx].get("slots") or []))
    ]
    assert portrait_less, "expected portrait-less ST-07A case studies"
    for idx in portrait_less:
        a = assignments[idx]
        assert a.treatment == "a4_case_study", f"idx {idx} -> {a.treatment}"
        treatment = get_treatment(a.treatment)
        assert treatment is not None and not treatment.needs_image


def test_a3_cap():
    """Five synthetic hero pages + a stub ctx (slot_uri returns a uri so they look
    image-bearing): at most max_a3 (3) get a3, the rest fall back to a4 (or stay
    untreated if no a4 candidate fits), with no crash and deterministically."""

    class _StubCtx:
        """Minimal ctx whose slot_uri resolves any portrait slot so adapt() sees
        a primary image (making each fake ST-07A page look like a hero)."""

        def slot_uri(self, page, slot_id):
            return "file:///stub/portrait.png"

        def slot_uris(self, page, slot_id):
            return []

    # Five fake ST-07A pages forced to hero via page_role, each with the data the
    # ST-07A (hero) A3 candidates require (editorial: headline+sections;
    # glass_card: stats; split_portrait: headline+image).
    def _fake_hero(n: int) -> dict:
        return {
            "st_type": "ST-07A",
            "page_role": "hero",
            "data": {
                "title": f"Case {n}",
                "ergebnis_headline": f"Result {n}",
                "ausgangssituation": "before text",
                "ergebnis_metrics": [{"value": "42", "label": "X"}],
                "pullquote": {"text": "a quote", "attribution": "someone"},
            },
        }

    pages = [_fake_hero(n) for n in range(5)]
    ctx = _StubCtx()

    result_a = assign(pages, ctx, max_a3=3)
    result_b = assign(pages, ctx, max_a3=3)
    assert result_a == result_b  # deterministic

    a3 = [r for r in result_a if r.page_format == "a3"]
    a4 = [r for r in result_a if r.page_format == "a4"]
    assert len(a3) <= 3, f"a3 cap exceeded: {len(a3)}"
    # 2026-07-13: the A3 HERO PROMOTION IS SUSPENDED (mid-deck A3 breaks
    # Chromium's mixed-size A4 print; see test_hero_is_a3_editorial), so NO
    # hero is promoted: every forced-hero page renders a4 (or untreated),
    # deterministically, no crash. When the engine per-format print+merge
    # lands, restore: the first three (in order) promoted to a3.
    assert [r.index for r in a3] == []
    for r in result_a:
        assert r.page_format != "a3"


def test_audit_lines(pkg, ctx, assignments):
    """audit_lines returns one readable line per page (26 for apex), each naming
    the page index and its decision."""
    lines = audit_lines(assignments)
    # US-604/605: the apex package has 26 pages (ST-02/ST-05/ST-06/FAZIT
    # continuations + the ST-09 split). US-2026-08-25: the ST-06 mechanism A3
    # stays within the 26 (a treated page, not a new sheet).
    assert len(lines) == len(pkg.pages) == 26
    for idx, line in enumerate(lines):
        # each line names its page (folio-ish index) and st_type
        assert assignments[idx].st_type in line
        # a treated line names its treatment; a bypass line says so
        a = assignments[idx]
        if a.treatment is None:
            assert "bypass" in line.lower() or "no fitting" in line.lower()
        else:
            assert a.treatment in line
            assert a.page_format in line
