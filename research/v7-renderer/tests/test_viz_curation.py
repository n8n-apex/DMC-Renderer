"""Tests for the APEX viz curation (fixtures/apex/viz_curation.py): the
grounding (no-fabrication) guard + apply_apex_viz binding the case studies.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from fixtures.apex.viz_curation import (  # noqa: E402
    apply_apex_viz, _figure_grounded, _spec_figures,
)

APEX = HERE.parent / "fixtures" / "apex"


# ---- grounding guard ----
def test_grounding_rejects_ungrounded_figure():
    page = {"st_type": "ST-07A", "data": {"ergebnis_metrics": [{"value": "30"}]}}
    assert _figure_grounded("30", page) is True
    assert _figure_grounded("999", page) is False


def test_grounding_digit_boundary_no_false_positive():
    page = {"st_type": "X", "data": {"quelle": "PwC 2025"}}
    assert _figure_grounded("2", page) is False          # not inside '2025'
    page2 = {"st_type": "X", "data": {"m": [{"value": "von 30 auf 2 Minuten"}]}}
    assert _figure_grounded("2", page2) is True


def test_grounding_nondigit_substring_mode():
    page = {"st_type": "X", "data": {"m": [{"value": "> 200.000 €"}]}}
    assert _figure_grounded("> 200.000 €", page) is True
    assert _figure_grounded("100 %", page) is False


def test_spec_figures_excludes_delta():
    spec = {"preset": "ba_bars", "pairs": [
        {"before": {"value": "30"}, "after": {"value": "2"}, "delta": "−93 %"}]}
    figs = _spec_figures(spec)
    assert "30" in figs and "2" in figs
    assert "−93 %" not in figs   # delta is derived, never grounded


# ---- apply (uses the real apex package dict) ----
def test_apply_sets_viz_on_case_studies_and_keeps_count():
    pkg = json.loads((APEX / "resolved_package.json").read_text(encoding="utf-8"))
    n = len(pkg["pages"])
    apply_apex_viz(pkg)
    cs = [p for p in pkg["pages"] if p["st_type"] == "ST-07A"]
    assert len(cs) == 5
    assert all(isinstance(p["data"].get("viz"), list) and p["data"]["viz"] for p in cs)
    # the cover (ST-01) is not a viz target
    assert "viz" not in (pkg["pages"][0].get("data") or {})
    assert len(pkg["pages"]) == n  # never adds/removes pages


def test_apply_is_idempotent():
    pkg = json.loads((APEX / "resolved_package.json").read_text(encoding="utf-8"))
    apply_apex_viz(pkg)
    first = [p["data"].get("viz") for p in pkg["pages"]]
    apply_apex_viz(pkg)
    second = [p["data"].get("viz") for p in pkg["pages"]]
    assert first == second
