"""Tests for the treatment RENDER / REGISTRY layer (Task TS-1.2).

Task TS-1.1 built the DATA layer (TreatmentData + adapt). THIS layer adds the
machinery that turns (page, ctx, treatment_name) into a PageFragment:
  - a Treatment descriptor + a TREATMENTS registry (register / get_treatment),
  - meets_contract(td, treatment): the data-fit gate (required_fields +
    needs_image), where None / "" / [] / {} all count as not-present,
  - render(page, ctx, treatment_name): adapt then dispatch. Returns None for the
    EXPECTED non-error cases (unknown name, unmet data contract); does NOT
    swallow a genuine bug raised inside a registered treatment,
  - _render_template_treatment: a template-driven treatment (Jinja template +
    a CSS file whose text becomes the PageFragment css).

These tests use a PROBE treatment registered via the render_fn escape hatch (no
template files needed) so the machinery is tested in isolation, plus one
template-driven test that creates and then removes its own probe files. Every
test that registers a probe pops it afterward so the registry never leaks state.

Run ONLY this file:
  python -m pytest tests/test_treatment_dispatch.py -v
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from package_loader import load_package  # noqa: E402
from grammar_loader import load_grammar  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402
from treatment_engine import (  # noqa: E402
    TREATMENTS,
    Treatment,
    TreatmentData,
    adapt,
    candidate_fits,
    get_treatment,
    meets_contract,
    register,
    render,
)

FIXTURE = ROOT / "fixtures" / "apex"


def _idx_of(pkg, st_type: str, role=None) -> int:
    """Index of the page with `st_type`; when `role` is given it must also match
    continuation_role (US-604: ST-02/ST-05/ST-06/ST-FAZIT span continuation
    pages). With role=None a NON-continuation page is preferred."""
    for i, pg in enumerate(pkg.pages):
        if str(pg.get("st_type")) != st_type:
            continue
        if role is None:
            if not pg.get("continuation_index"):
                return i
        elif pg.get("continuation_role") == role:
            return i
    raise AssertionError(f"no {st_type} page (role={role!r}) in the apex fixture")


def _st07a_with_resolved_portrait_idx(pkg) -> int:
    """Index of the ST-07A case study whose case_study_portrait slot RESOLVES."""
    for i, pg in enumerate(pkg.pages):
        if str(pg.get("st_type")) != "ST-07A":
            continue
        for s in pg.get("slots") or []:
            if s.get("slot_id") == "case_study_portrait" and s.get("status") == "resolved":
                return i
    raise AssertionError("no ST-07A with a resolved case_study_portrait")


# Fixture page indices used below (derived from the real apex package by type —
# US-604 added ST-02/ST-05 continuation pages, so fixed indices are stale):
#   ST02_IDX             : ST-02, has a headline (title), no steps        -> dispatch + contract tests
#   ST07A_IMAGE_IDX      : ST-07A, primary portrait resolves (image set)  -> needs_image returns a fragment
_PKG = load_package(FIXTURE)
ST02_IDX = _idx_of(_PKG, "ST-02", role="context")
ST07A_IMAGE_IDX = _st07a_with_resolved_portrait_idx(_PKG)


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


@contextmanager
def registered(treatment: Treatment):
    """Register a probe treatment for the duration of a test, then pop it so the
    shared TREATMENTS registry never leaks state between tests."""
    register(treatment)
    try:
        yield treatment
    finally:
        TREATMENTS.pop(treatment.name, None)


def test_render_dispatches_to_registered_treatment(pkg, ctx):
    """render() adapts the page, finds the registered treatment, and calls its
    render_fn, returning that PageFragment (html carries the page's title)."""
    page = pkg.pages[ST02_IDX]
    assert page["st_type"] == "ST-02"
    title = page["data"]["title"]

    probe = Treatment(
        name="probe",
        archetype="probe",
        formats=frozenset({"a4"}),
        required_fields=("headline",),
        render_fn=lambda td, ctx: PageFragment(html=f"<p>{td.headline}</p>", css=".x{}"),
    )
    with registered(probe):
        frag = render(page, ctx, "probe")

    assert isinstance(frag, PageFragment)
    assert title in frag.html
    assert frag.css == ".x{}"


def test_unknown_treatment_returns_none(pkg, ctx):
    """An UNKNOWN treatment name returns None (caller falls back); no raise."""
    page = pkg.pages[ST02_IDX]
    assert get_treatment("does-not-exist") is None
    assert render(page, ctx, "does-not-exist") is None


def test_unmet_required_data_returns_none(pkg, ctx):
    """A required field the page lacks (steps on an ST-02 page) -> meets_contract
    is False and render() returns None (no raise)."""
    page = pkg.pages[ST02_IDX]
    td = adapt(page, ctx)
    assert not td.steps  # the ST-02 page carries no steps

    probe = Treatment(
        name="probe-steps",
        archetype="probe",
        formats=frozenset({"a4"}),
        required_fields=("steps",),
        render_fn=lambda td, ctx: PageFragment(html="<x/>", css=""),
    )
    with registered(probe):
        assert meets_contract(td, probe) is False
        assert render(page, ctx, "probe-steps") is None


def test_needs_image_gate(pkg, ctx):
    """needs_image=True: None when td.image is None (a synthetic portrait-less
    page), a fragment when the portrait resolves (ST07A_IMAGE_IDX)."""
    probe = Treatment(
        name="probe-img",
        archetype="probe",
        formats=frozenset({"a4"}),
        required_fields=("headline",),
        needs_image=True,
        render_fn=lambda td, ctx: PageFragment(html="<img/>", css=""),
    )

    # a synthetic ST-07A page with NO portrait slot (the fixture's case studies now
    # carry real portraits); its data meets the headline contract but has no image.
    no_image_page = {
        "st_type": "ST-07A",
        "data": {"ergebnis_headline": "Ohne Bild", "ausgangsproblem": "x"},
    }
    image_page = pkg.pages[ST07A_IMAGE_IDX]
    assert adapt(no_image_page, ctx).image is None
    assert adapt(image_page, ctx).image  # resolves to a file:// URI

    with registered(probe):
        assert render(no_image_page, ctx, "probe-img") is None
        frag = render(image_page, ctx, "probe-img")
        assert isinstance(frag, PageFragment)
        assert frag.html == "<img/>"


def test_template_treatment_renders_and_loads_css(pkg, ctx):
    """A template-driven treatment renders its Jinja template against td and
    loads its CSS file text into the PageFragment css. Creates tiny probe files,
    then removes them (and any dir it created) so the tree is left clean."""
    templates_dir = ROOT / "templates" / "treatments"
    styles_dir = ROOT / "styles" / "treatments"
    created_templates_dir = not templates_dir.exists()
    created_styles_dir = not styles_dir.exists()
    templates_dir.mkdir(parents=True, exist_ok=True)
    styles_dir.mkdir(parents=True, exist_ok=True)

    tpl_file = templates_dir / "__probe.html.jinja"
    css_file = styles_dir / "__probe.css"
    # NOTE: the CSS uses a semantic token (var(--...)), never a raw literal, so
    # the no-literals architecture guard stays green even while the file exists.
    tpl_file.write_text("<h1>{{ td.headline }}</h1>\n", encoding="utf-8")
    css_file.write_text(".t{color:var(--color-ink)}\n", encoding="utf-8")

    page = pkg.pages[ST02_IDX]
    title = page["data"]["title"]

    probe = Treatment(
        name="probe-tpl",
        archetype="probe",
        formats=frozenset({"a4"}),
        required_fields=("headline",),
        template="treatments/__probe.html.jinja",
        css_path="styles/treatments/__probe.css",
    )
    try:
        with registered(probe):
            frag = render(page, ctx, "probe-tpl")
        assert isinstance(frag, PageFragment)
        assert title in frag.html
        assert ".t{" in frag.css
    finally:
        # Leave NO probe files behind; remove any dir we created if now empty.
        tpl_file.unlink(missing_ok=True)
        css_file.unlink(missing_ok=True)
        if created_templates_dir and templates_dir.exists() and not any(templates_dir.iterdir()):
            templates_dir.rmdir()
        if created_styles_dir and styles_dir.exists() and not any(styles_dir.iterdir()):
            styles_dir.rmdir()


def test_template_treatment_missing_css_is_graceful(pkg, ctx):
    """A template treatment whose css_path does not exist renders html with an
    empty css (graceful, no crash)."""
    templates_dir = ROOT / "templates" / "treatments"
    created_templates_dir = not templates_dir.exists()
    templates_dir.mkdir(parents=True, exist_ok=True)
    tpl_file = templates_dir / "__probe_nocss.html.jinja"
    tpl_file.write_text("<h1>{{ td.headline }}</h1>\n", encoding="utf-8")

    page = pkg.pages[ST02_IDX]
    probe = Treatment(
        name="probe-nocss",
        archetype="probe",
        formats=frozenset({"a4"}),
        required_fields=("headline",),
        template="treatments/__probe_nocss.html.jinja",
        css_path="styles/treatments/__does_not_exist.css",
    )
    try:
        with registered(probe):
            frag = render(page, ctx, "probe-nocss")
        assert isinstance(frag, PageFragment)
        assert frag.css == ""
    finally:
        tpl_file.unlink(missing_ok=True)
        if created_templates_dir and templates_dir.exists() and not any(templates_dir.iterdir()):
            templates_dir.rmdir()


def test_meets_contract_empty_vs_present():
    """meets_contract directly: None / "" / [] / {} count as not-present; a
    non-empty value counts as present. needs_image gates on td.image."""
    base = Treatment(
        name="unit",
        archetype="unit",
        formats=frozenset({"a4"}),
        required_fields=("headline",),
    )

    # every empty kind fails the headline requirement
    for empty in (None, "", [], {}):
        td = TreatmentData(headline=empty)  # type: ignore[arg-type]
        assert meets_contract(td, base) is False, f"{empty!r} should count as empty"

    # a non-empty value passes
    assert meets_contract(TreatmentData(headline="Hello"), base) is True

    # a multi-field requirement needs ALL fields present
    multi = Treatment(
        name="unit-multi",
        archetype="unit",
        formats=frozenset({"a4"}),
        required_fields=("headline", "sections"),
    )
    assert meets_contract(TreatmentData(headline="Hi"), multi) is False
    assert meets_contract(
        TreatmentData(headline="Hi", sections=[{"label": "L", "text": "T"}]), multi
    ) is True

    # needs_image: present headline but no image fails; image present passes
    needs_img = Treatment(
        name="unit-img",
        archetype="unit",
        formats=frozenset({"a4"}),
        required_fields=("headline",),
        needs_image=True,
    )
    assert meets_contract(TreatmentData(headline="Hi"), needs_img) is False
    assert meets_contract(TreatmentData(headline="Hi", image="file:///x.png"), needs_img) is True


def test_candidate_fits_wrapper(pkg, ctx):
    """candidate_fits is the thin stylist wrapper: treatment exists AND
    meets_contract(adapt(page, ctx), treatment)."""
    page = pkg.pages[ST02_IDX]

    probe = Treatment(
        name="probe-fits",
        archetype="probe",
        formats=frozenset({"a4"}),
        required_fields=("headline",),
        render_fn=lambda td, ctx: PageFragment(html="<x/>", css=""),
    )
    with registered(probe):
        assert candidate_fits(page, ctx, "probe-fits") is True
    # unknown name: no fit, no raise
    assert candidate_fits(page, ctx, "does-not-exist") is False
