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


def _st_by_idx(pkg):
    return [str(pg.get("st_type")) for pg in pkg.pages]


ELIGIBLE_IDX = ()      # computed per-package in the fixture-dependent tests
LEGACY_BY_DESIGN_IDX = ()
BYPASS_IDX = ()
# The editorial A3 HERO is now the ABOUT page (ST-05, idx 2): its rich data (the
# 30-50% figure, the 100+/€200k+ figures, and the partner wall) is what the A3
# editorial spread was designed for. The founder-identity fallback supplies its
# portrait + name + role (it has no portrait of its own).
HERO_IDX = 2
A3_TREATMENTS = {"editorial", "glass_card", "split_portrait"}
# The FRAMEWORK page (ST-06, idx 15) is promoted to A3 for the horizontal_process
# flow (an A3-only "process" treatment that needs the wide sheet). So the deck now
# has TWO A3 pages: the About editorial (idx 2) and the framework flow (idx 15),
# still within the A3 cap of 3.
FRAMEWORK_IDX = 15
A3_INDICES = [HERO_IDX, FRAMEWORK_IDX]


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


def test_hero_is_a3_editorial(pkg, ctx, assignments):
    """2026-07-13: the A3 HERO PROMOTION IS SUSPENDED. A mid-deck A3-landscape
    named page makes Chromium's mixed-size print compress the surrounding A4
    pages to ~71% (verified by bisect on the christoph deck; blanket-pinning
    every section made it universal). Until the engine prints per-format and
    merges, the About page renders on A4 via the fill treatment (which carries
    the injected founder portrait). When the engine fix lands, restore the old
    expectation: editorial [a3]."""
    hero = assignments[HERO_IDX]
    assert hero.st_type == "ST-05", f"hero idx {HERO_IDX} st_type {hero.st_type}"
    assert hero.page_format == "a4"
    assert hero.treatment == "a4_editorial_fill", f"about -> {hero.treatment}"
    assert "suspended" in (hero.reason or ""), hero.reason


def test_a3_pages_are_about_and_framework(pkg, ctx, assignments):
    """US-604: the ST-06 section now spans TWO A4 continuation pages (intro +
    result), so there is NO A3 framework page — the section's pages render via
    the ST-06 pattern's continuation composition, not a treatment. The deck's
    A3 set is empty (the About hero promotion remains suspended)."""
    a3_indices = [a.index for a in assignments if a.page_format == "a3"]
    assert a3_indices == [], f"unexpected a3 pages: {a3_indices}"
    # both ST-06 pages are continuation-bypassed (no treatment)
    st06 = [a for a in assignments if a.st_type == "ST-06"]
    assert len(st06) == 2, f"expected 2 ST-06 pages (intro+result); got {len(st06)}"
    for a in st06:
        assert a.treatment is None, f"ST-06 continuation treated: {a.treatment}"
        assert a.page_format is None


def test_st07a_no_longer_editorial(pkg, ctx, assignments):
    """The ST-07A case-study pages no longer route to the A3 editorial: every
    ST-07A page is an A4 case treatment (idx 11, which used to be the editorial
    hero, is now an A4 treatment). The editorial hero moved to the About page."""
    for idx in (6, 8, 11, 13, 14):
        a = assignments[idx]
        assert a.st_type == "ST-07A"
        assert a.treatment != "editorial", f"idx {idx} still editorial"
        assert a.page_format == "a4", f"idx {idx} format {a.page_format}"
    # specifically idx 11 (the former hero) is now A4 and not editorial.
    assert assignments[11].treatment != "editorial"


def test_best_fit_singletons(pkg, ctx, assignments):
    """Best-fit-first picks each page's richest fitting BUILT treatment (subject
    to deck-wide dedup). The singleton best-fits below are unused before their
    page, so they land on their first BUILT fitting candidate:
      idx 1  ST-02 -> a4_editorial_fill. a4_bi_dashboard leads the candidate
             list but is a metadata-only STUB (no template): assigning it raised
             TemplateNotFound at render and silently dropped the page to the
             flat legacy pattern (the 2026-07-13 ST-02 regression). candidate_fits
             now requires the template to be BUILT, so a stub is never assigned;
             when a4_bi_dashboard's template is authored it re-enters
             automatically and this expectation flips back to the dashboard.
      idx 2  ST-05 -> a4_editorial_fill [a4] (the A3 hero is SUSPENDED; the
             About page renders on A4 with the injected founder portrait)
      idx 15/16 ST-06 -> continuation-bypassed (US-604: the section now
             spans intro + result pages rendered by the ST-06 pattern)
      idx 19 ST-22 -> a4_vertical_timeline (ST-22 stays A4; its own #1)
    """
    assert assignments[1].treatment == "a4_editorial_fill"
    assert assignments[2].treatment == "a4_editorial_fill"
    assert assignments[2].page_format == "a4"
    st06 = [a for a in assignments if a.st_type == "ST-06"]
    assert len(st06) == 2 and all(a.treatment is None for a in st06), (
        "ST-06 continuation pages must be bypassed"
    )
    # ST-22 keeps the A4 vertical timeline (it is NOT promoted to A3).
    st22 = [a for a in assignments if a.st_type == "ST-22"]
    assert st22 and st22[0].treatment == "a4_vertical_timeline"
    assert st22[0].page_format == "a4"


def test_adjacent_case_studies_share_the_case_treatment(pkg, ctx, assignments):
    """Adjacent ST-07A case studies (idx 13, 14) BOTH use a4_case_study.

    A report's case studies must all share the SAME case layout (design rule:
    never mix case variants within one report), so the case treatment is EXEMPT
    from the no-adjacent-repeat variety rule that applies to other page types."""
    a13 = assignments[13]
    a14 = assignments[14]
    assert a13.treatment == "a4_case_study"
    assert a14.treatment == "a4_case_study"
    assert a13.page_format == "a4" and a14.page_format == "a4"


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
    # needs_image treatment (split_portrait / editorial).
    for idx in (6, 8, 13, 14):
        a = assignments[idx]
        assert a.treatment == "a4_case_study"
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
    """audit_lines returns one readable line per page (20 for apex), each naming
    the page index and its decision."""
    lines = audit_lines(assignments)
    # US-604: the apex package now has 21 pages (ST-06 spans intro+result).
    assert len(lines) == len(pkg.pages) == 21
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
