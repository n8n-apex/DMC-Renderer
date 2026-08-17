"""Tests for the TREATMENT WIRING (Task TS-1.4).

The data layer (TreatmentData + adapt), the dispatch layer (Treatment registry +
render), and the stylist (assign) already exist. THIS task wires the stylist into
the assembler behind a `--treatments` flag (default OFF), dispatches treatments
per page, and stamps the section classes. These tests verify the WIRING with a
PROBE treatment (the real treatment templates are authored in the next task), not
a real layout, and they never run a full PDF render.

Run ONLY this file:
  python -m pytest tests/test_treatment_wiring.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from package_loader import load_package  # noqa: E402
from grammar_loader import load_grammar  # noqa: E402
from patterns.base import PageFragment, RenderContext  # noqa: E402

import treatment_engine  # noqa: E402
from treatment_stylist import PageAssignment  # noqa: E402

from assembler import _section, _render_one_page  # noqa: E402


# --- shared fixtures ---------------------------------------------------------
@pytest.fixture(scope="module")
def pkg():
    return load_package(Path("fixtures/apex"))


@pytest.fixture(scope="module")
def ctx(pkg):
    return RenderContext(
        brand=pkg.brand,
        grammar=load_grammar(),
        package_dir=pkg.package_dir,
        report_assets=pkg.report_assets,
    )


@pytest.fixture
def probe():
    """Register a probe treatment requiring `headline`; pop it in teardown so the
    shared registry leaks nothing into other tests."""
    t = treatment_engine.Treatment(
        name="probe",
        archetype="probe",
        formats=frozenset({"a4"}),
        required_fields=("headline",),
        render_fn=lambda td, ctx: PageFragment(html="<p>PROBE</p>", css=".probe{}"),
    )
    treatment_engine.register(t)
    try:
        yield t
    finally:
        treatment_engine.TREATMENTS.pop("probe", None)


@pytest.fixture
def probe_raises():
    """A probe whose render_fn raises (a treatment BUG); popped in teardown."""
    def _boom(td, ctx):
        raise RuntimeError("probe boom")

    t = treatment_engine.Treatment(
        name="probe",
        archetype="probe",
        formats=frozenset({"a4"}),
        required_fields=("headline",),
        render_fn=_boom,
    )
    treatment_engine.register(t)
    try:
        yield t
    finally:
        treatment_engine.TREATMENTS.pop("probe", None)


def _assignment_for(pkg, index: int, treatment, page_format) -> PageAssignment:
    page = pkg.pages[index]
    return PageAssignment(
        index=index,
        slot=page.get("slot"),
        st_type=str(page.get("st_type", "")),
        treatment=treatment,
        page_format=page_format,
        reason="test",
    )


def _page_with_headline(pkg):
    """The first apex page whose st_type is ST-02 (carries a headline)."""
    for i, p in enumerate(pkg.pages):
        if str(p.get("st_type", "")) == "ST-02":
            return i, p
    raise AssertionError("no ST-02 page in the apex fixture")


def _page_without_headline(pkg):
    """The first apex page whose st_type is ST-31 (a breather, no headline-equiv)."""
    for i, p in enumerate(pkg.pages):
        if str(p.get("st_type", "")) == "ST-31":
            return i, p
    raise AssertionError("no ST-31 page in the apex fixture")


# --- 1. _section stamps treatment + format classes ---------------------------
def test_section_stamps_treatment_and_format(pkg):
    page = pkg.pages[0]
    frag = PageFragment(html="<i>x</i>", css="")
    stamped = _section(page, frag, 0, treatment="editorial", page_format="a3")
    assert 'class="page ' in stamped
    assert "treatment-editorial" in stamped
    assert "format-a3" in stamped

    plain = _section(page, frag, 0)
    assert "treatment-" not in plain
    assert "format-" not in plain


# --- 2. _render_one_page uses the treatment when it fits ----------------------
def test_render_one_page_uses_treatment(pkg, ctx, probe):
    idx, page = _page_with_headline(pkg)
    assignment = _assignment_for(pkg, idx, "probe", "a4")
    warnings: list[str] = []
    frag, used_t, used_f = _render_one_page(
        page, ctx, assignment, treatments=True, warnings=warnings
    )
    assert "PROBE" in frag.html
    assert used_t == "probe"
    assert used_f == "a4"
    assert warnings == []


# --- 3. fall back to legacy when the data does NOT fit ------------------------
def test_render_one_page_falls_back_when_unfit(pkg, ctx, probe):
    # ST-31 has no headline; the probe requires `headline`, so render() returns
    # None and the page renders as a normal legacy A4 page.
    idx, page = _page_without_headline(pkg)
    assignment = _assignment_for(pkg, idx, "probe", "a4")
    warnings: list[str] = []
    frag, used_t, used_f = _render_one_page(
        page, ctx, assignment, treatments=True, warnings=warnings
    )
    assert "PROBE" not in frag.html
    assert used_t is None
    assert used_f is None


# --- 4. fall back (with a warning) when the treatment RAISES ------------------
def test_render_one_page_falls_back_on_raise(pkg, ctx, probe_raises):
    idx, page = _page_with_headline(pkg)
    assignment = _assignment_for(pkg, idx, "probe", "a4")
    warnings: list[str] = []
    frag, used_t, used_f = _render_one_page(
        page, ctx, assignment, treatments=True, warnings=warnings
    )
    # The exception did NOT propagate; the page degraded to a legacy fragment.
    assert "PROBE" not in frag.html
    assert used_t is None
    assert used_f is None
    assert any("probe" in w for w in warnings)


# --- 5. treatments=False ignores the assignment entirely ----------------------
def test_render_one_page_treatments_off(pkg, ctx, probe):
    idx, page = _page_with_headline(pkg)
    assignment = _assignment_for(pkg, idx, "probe", "a4")
    warnings: list[str] = []
    frag, used_t, used_f = _render_one_page(
        page, ctx, assignment, treatments=False, warnings=warnings
    )
    assert "PROBE" not in frag.html
    assert used_t is None
    assert used_f is None


# --- 6. the CLI flag parses ---------------------------------------------------
def test_render_cli_treatments_flag():
    from render import _build_parser

    ns = _build_parser().parse_args(["--treatments"])
    assert ns.treatments is True
    assert _build_parser().parse_args([]).treatments is False
