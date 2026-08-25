"""Template Bank tests (Proof of A).

Pin that the unified bank catalog
  - loads the v3 contexts, the live templates, and the device presets,
  - browses by ROLE (context vocabulary) and returns the right candidates,
  - and the planner (bank_plan.plan_pages) reproduces the renderer's actual
    per-page assignments for the apex deck, each annotated with role + devices.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from bank_catalog import browse_by_role, catalog  # noqa: E402
from bank_catalog import _device_entries  # noqa: E402
from bank_plan import plan_pages, PagePlan, _ROLE_BY_ST  # noqa: E402
from brand_tokens import parse_brand_tokens  # noqa: E402
from grammar_loader import load_grammar  # noqa: E402
from package_loader import load_package  # noqa: E402
from patterns.base import RenderContext  # noqa: E402


@pytest.fixture(scope="module")
def pkg():
    return load_package(ROOT / "fixtures" / "apex")


@pytest.fixture(scope="module")
def ctx(pkg):
    return RenderContext(brand=pkg.brand, grammar=load_grammar(),
                         package_dir=pkg.package_dir,
                         report_assets=pkg.report_assets)


def test_catalog_has_all_three_levels():
    cat = catalog()
    assert cat["contexts"], "v3 contexts must load"
    assert cat["templates"], "live treatments must load"
    assert cat["devices"], "device presets must load"


def test_browse_by_role_returns_contexts_templates_devices():
    r = browse_by_role("status_quo")
    assert r["role"] == "status_quo"
    assert any(c["name"] == "editorial_lead" for c in r["contexts"]), \
        "status_quo must map to the editorial_lead v3 context"
    built = [t for t in r["templates"] if t["built"]]
    assert "a4_bi_dashboard" in {t["name"] for t in built}, \
        "status_quo browse must include the built dashboard"
    assert r["devices"], "browse must include candidate devices"


def test_plan_reproduces_the_renderer_assignment(pkg, ctx):
    """The planner's assignments MUST match the renderer's (treatment_engine):
    they are the SAME decision path. Pin the known apex assignments."""
    plans = plan_pages(pkg.pages, ctx)
    by_slot = {(p.slot, p.reason): p for p in plans}
    # ST-09 context -> a4_bi_dashboard (role status_quo)
    st09 = [p for p in plans if p.st_type == "ST-09"]
    assert any(p.template == "a4_bi_dashboard" for p in st09), \
        "ST-09 context must plan the dashboard"
    assert any(p.template == "a4_editorial_fill" for p in st09), \
        "ST-09 evidence must plan the fill"
    # all five case studies plan the case-study treatment
    cases = [p for p in plans if p.st_type == "ST-07A" and p.template]
    assert len(cases) == 5, f"expected 5 case plans, got {len(cases)}"
    assert all(p.template == "a4_case_study" for p in cases)
    # every plan carries a role (structural vocab) + candidate devices
    treated = [p for p in plans if p.template]
    assert treated and all(p.role for p in treated), "treated plans must carry a role"
    assert all(len(p.devices) > 0 for p in treated), "treated plans must carry devices"


def test_role_mapping_covers_every_live_stype():
    # every renderer st_type with a possible treatment has a role in the vocab
    for st in ("ST-02", "ST-05", "ST-09", "ST-14", "ST-07A", "ST-06",
               "ST-22", "ST-FAZIT", "ST-03", "ST-01", "ST-31"):
        assert st in _ROLE_BY_ST, f"{st} has no role in the bank vocabulary"


def test_plan_is_deterministic(pkg, ctx):
    p1 = [p.__dict__ for p in plan_pages(pkg.pages, ctx)]
    p2 = [p.__dict__ for p in plan_pages(pkg.pages, ctx)]
    assert p1 == p2