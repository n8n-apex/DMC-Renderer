"""TDD for the LayoutTemplate model (Phase 4): brand-agnostic, geometry-bounded,
role-vocabulary-validated."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from layout_template import LayoutTemplate  # noqa: E402


def _valid() -> dict:
    return {
        "st_type": "ST-07A",
        "variant": "authority-rail",
        "grid": {"columns": 12,
                 "margin": {"top": 0.06, "right": 0.06, "bottom": 0.06, "left": 0.06},
                 "gutter": 0.02},
        "regions": [
            {"role": "headline", "x": 0.06, "y": 0.06, "w": 0.55, "h": 0.18},
            {"role": "stat_rail", "x": 0.66, "y": 0.06, "w": 0.28, "h": 0.88, "z": 1},
            {"role": "body", "x": 0.06, "y": 0.28, "w": 0.55, "h": 0.60},
        ],
        "type_roles": {"headline": "display", "lede": "lede",
                       "body": "body", "label": "label"},
        "color_roles": {"ground": "ground", "ink": "ink",
                        "accent": "accent", "footer": "footer"},
        "whitespace_target": 0.2,
        "source_refs": [{"deck": "niklas", "page_no": 8}],
    }


def test_valid_template_parses():
    t = LayoutTemplate.from_dict(_valid())
    assert t.st_type == "ST-07A"
    assert len(t.regions) == 3
    assert t.regions[1].role == "stat_rail" and t.regions[1].z == 1
    assert t.grid.columns == 12
    assert t.regions[0].fit == "wrap"  # default


def test_region_out_of_bounds_raises():
    d = _valid()
    d["regions"][0]["w"] = 0.99  # x=0.06 + w=0.99 = 1.05 > 1 -> past the page
    with pytest.raises(ValueError, match="past the page"):
        LayoutTemplate.from_dict(d)


def test_unknown_region_role_raises():
    d = _valid()
    d["regions"][0]["role"] = "sidebar_widget"
    with pytest.raises(ValueError, match="unknown region role"):
        LayoutTemplate.from_dict(d)


def test_color_role_hex_raises_brand_agnostic():
    d = _valid()
    d["color_roles"]["accent"] = "#4A7C7E"  # a brand hex leak
    with pytest.raises(ValueError, match="token ROLE"):
        LayoutTemplate.from_dict(d)


def test_color_role_unknown_value_raises():
    d = _valid()
    d["color_roles"]["accent"] = "neon_cyan"
    with pytest.raises(ValueError, match="token ROLE"):
        LayoutTemplate.from_dict(d)


def test_empty_source_refs_raises():
    d = _valid()
    d["source_refs"] = []
    with pytest.raises(ValueError, match="source_refs"):
        LayoutTemplate.from_dict(d)


def test_bad_type_role_raises():
    d = _valid()
    d["type_roles"]["headline"] = "ginormous"
    with pytest.raises(ValueError, match="scale role"):
        LayoutTemplate.from_dict(d)
