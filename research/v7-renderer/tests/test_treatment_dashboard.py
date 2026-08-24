"""Tests for the a4_bi_dashboard treatment (the "Power-BI" data spread).

Built per the plan 2026-08-25 (TDD): the treatment is registered in the
catalog; `treatment_is_built` flips when the template + css exist; the data
gate is `("viz",)`; ST-09 context is the apex host (a page with `data.viz`),
ST-09 evidence (no viz) must NOT fit it. Mirrors the ctx/package fixtures in
test_treatment_engine.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from grammar_loader import load_grammar  # noqa: E402
from package_loader import load_package  # noqa: E402
from patterns.base import RenderContext  # noqa: E402
from treatment_catalog import register_all  # noqa: E402
from treatment_engine import (  # noqa: E402
    candidate_fits,
    get_treatment,
    render,
    treatment_is_built,
)

FIXTURE = ROOT / "fixtures" / "apex"


@pytest.fixture(scope="module")
def pkg():
    register_all()
    return load_package(FIXTURE)


@pytest.fixture(scope="module")
def ctx(pkg):
    return RenderContext(
        brand=pkg.brand,
        grammar=load_grammar(),
        package_dir=pkg.package_dir,
        report_assets=pkg.report_assets,
    )


def _st09_page(pkg, role):
    matches = [
        p for p in pkg.pages
        if p["st_type"] == "ST-09" and p.get("continuation_role") == role
    ]
    assert matches, f"no ST-09 {role} page"
    return matches[0]


def test_dashboard_is_built(pkg, ctx):  # noqa: ARG001
    assert treatment_is_built("a4_bi_dashboard") is True


def test_dashboard_contract_is_viz(pkg):  # noqa: ARG001
    t = get_treatment("a4_bi_dashboard")
    assert t is not None
    assert t.required_fields == ("viz",)
    assert t.formats == frozenset({"a4"})


def test_context_with_viz_fits(pkg, ctx):
    context = _st09_page(pkg, "context")
    assert (context.get("data") or {}).get("viz"), "context must carry viz"
    assert candidate_fits(context, ctx, "a4_bi_dashboard") is True


def test_evidence_without_viz_does_not_fit(pkg, ctx):
    ev = _st09_page(pkg, "evidence")
    assert not (ev.get("data") or {}).get("viz")
    assert candidate_fits(ev, ctx, "a4_bi_dashboard") is False


def test_dashboard_render_uses_tokens_and_has_rail(pkg, ctx):
    context = _st09_page(pkg, "context")
    frag = render(context, ctx, "a4_bi_dashboard")
    assert frag is not None
    html = frag.html
    # markup lashes the interior dark rail + the narrative + the device host
    assert "db-rail" in html
    assert "db-narrative" in html
    assert "db-devices" in html
    # token-only: no raw hex in the fragment (a brand URL is runtime DATA from
    # ctx.brand, not an authored client literal, so it is allowed). Check there
    # is no hex-color signature (a # followed by 3-6 hex digits).
    import re as _re
    assert not _re.search(r"#[0-9a-fA-F]{3,6}\b", html), "raw hex color in fragment"
    # the only brand string is the runtime footer URL / wordmark; an authored
    # CLIENT literal would appear outside that. The two real apex client names
    # must not appear as invented chrome.
    for client_word in ("Consesso", "Conesso", "Frese"):
        assert client_word not in html
    # the css is present (non-empty)
    assert frag.css and "var(--color-ink)" in frag.css


def test_dashboard_no_viz_renders_none(pkg, ctx):
    ev = _st09_page(pkg, "evidence")
    assert render(ev, ctx, "a4_bi_dashboard") is None