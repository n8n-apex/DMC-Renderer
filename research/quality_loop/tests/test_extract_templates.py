"""Offline TDD for Phase 4 Task 2 — reference LayoutTemplate extraction.

NO live vision calls: an injected fake ``extract_fn`` / a ``FakeVisionClient``
supplies a canned region map; the stage stamps + validates + writes.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from references.extract_templates import (  # noqa: E402
    build_templates, extract_template, make_vision_extract_fn,
)


def _canned_body():
    return {
        "variant": "authority-rail",
        "grid": {"columns": 12,
                 "margin": {"top": 0.06, "right": 0.06, "bottom": 0.06, "left": 0.06},
                 "gutter": 0.02},
        "regions": [
            {"role": "headline", "x": 0.06, "y": 0.06, "w": 0.55, "h": 0.18},
            {"role": "stat_rail", "x": 0.66, "y": 0.06, "w": 0.28, "h": 0.88, "z": 1},
        ],
        "type_roles": {"headline": "display", "body": "body"},
        "color_roles": {"ground": "ground", "ink": "ink", "accent": "accent"},
        "whitespace_target": 0.2,
    }


def test_extract_template_stamps_and_validates():
    body = extract_template(
        "niklas", 8, "ST-07A", "x.png", extract_fn=lambda p, t, s: _canned_body()
    )
    assert body["st_type"] == "ST-07A"
    assert body["source_refs"] == [{"deck": "niklas", "page_no": 8}]
    assert body["variant"] == "authority-rail"
    assert len(body["regions"]) == 2


def test_extract_template_rejects_invalid_geometry():
    bad = _canned_body()
    bad["regions"][0]["w"] = 0.99  # x 0.06 + 0.99 > 1 -> past the page
    with pytest.raises(ValueError, match="past the page"):
        extract_template("niklas", 8, "ST-07A", "x.png", extract_fn=lambda p, t, s: bad)


def test_extract_template_rejects_hex_color_role():
    leak = _canned_body()
    leak["color_roles"]["accent"] = "#4A7C7E"
    with pytest.raises(ValueError, match="token ROLE"):
        extract_template("niklas", 8, "ST-07A", "x.png", extract_fn=lambda p, t, s: leak)


def test_build_templates_clusters_and_writes(tmp_path):
    index = [
        {"deck": "niklas", "page_no": 8, "st_type": "ST-07A",
         "png_path": "references/pages/niklas/p8.png"},
        {"deck": "apex", "page_no": 12, "st_type": "ST-07A",
         "png_path": "references/pages/apex/p12.png"},   # 2nd exemplar -> first wins
        {"deck": "niklas", "page_no": 1, "st_type": "ST-01",
         "png_path": "references/pages/niklas/p1.png"},
        {"deck": "niklas", "page_no": 2, "st_type": "OTHER",
         "png_path": "references/pages/niklas/p2.png"},  # excluded
    ]
    idx_path = tmp_path / "index.json"
    idx_path.write_text(json.dumps(index), encoding="utf-8")
    written = build_templates(
        extract_fn=lambda p, t, s: _canned_body(),
        index_path=idx_path, out_root=tmp_path / "tpl",
    )
    assert set(written) == {"ST-07A", "ST-01"}  # OTHER excluded
    body = json.loads(Path(written["ST-07A"]).read_text())
    assert body["source_refs"] == [{"deck": "niklas", "page_no": 8}]  # first exemplar
    assert Path(written["ST-07A"]).name == "authority-rail.json"


def test_make_vision_extract_fn_uses_client():
    from vis_client import FakeVisionClient

    c = FakeVisionClient({})
    c.extract_return = _canned_body()
    fn = make_vision_extract_fn(c)
    out = fn("page.png", "", "ST-07A")
    assert out["variant"] == "authority-rail"
    assert c.extract_calls and c.extract_calls[0][0] == "page.png"
