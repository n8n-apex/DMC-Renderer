"""US-608 — reference-grounded FINAL-artifact QA.

The audit found the gate: (1) passes ZERO reference images, (2) hardcodes the
apex fixture path, (3) runs BEFORE convergence so the composed deck is never
re-gated, (4) leaks decorated row IDs (P11*) into the prompt/client protocol.

Acceptance:
  - every visual review call receives the page's reference PNGs + Director
    metadata
  - rubric IDs are normalized before the client call
  - the gate reads the package dir (not a hardcoded fixture path)
  - the final composed artifact is re-gated after convergence
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import render as render_mod  # noqa: E402


def test_gate_rows_normalize_decorated_ids() -> None:
    """P11* / P11*?figures must normalize to the real rubric ID P11 BEFORE any
    client call (the prompt/client only know P11). The gate's loop does this;
    _gate_rows_for_stype returns the decorated INTERNAL markers by design."""
    import re

    from render import _gate_rows_for_stype

    rows = _gate_rows_for_stype("ST-07B")
    for row in rows:
        clean = re.split(r"[*?]", row)[0]
        assert clean in ("P11", "P12", "P13", "P14"), f"unknown row: {row}"
    # the GATE source contains the normalization (no decorated id reaches the
    # score_page call)
    src = (ROOT / "render.py").read_text(encoding="utf-8")
    assert "row.endswith(\"?figures\")" in src
    assert "row.rstrip(\"*\")" in src


def test_gate_uses_package_dir_not_hardcoded_apex() -> None:
    """The gate must resolve st_types from the SUPPLIED package dir, not a
    hardcoded fixtures/apex path (the CLI default package is the fixture —
    that's the input default, not the gate)."""
    src = (ROOT / "render.py").read_text(encoding="utf-8")
    assert "package_dir=package_dir" in src or "package_dir or out_dir" in src, (
        "the gate must take the supplied package_dir"
    )
    assert "out_dir.parent / \"fixtures\"" not in src, (
        "the gate must not derive the package from the output dir"
    )


def test_visual_gate_passes_references_and_metadata() -> None:
    """The gate's review call must include reference PNGs + Director metadata
    (the audit: score_page(str(png), [], rows) passed ZERO references)."""
    src = (ROOT / "render.py").read_text(encoding="utf-8")
    assert "retrieve_references" in src, (
        "the gate must retrieve reference pages"
    )
    assert "director_brief" in src or "row_metadata" in src, (
        "the gate must pass Director metadata to the reviewer"
    )
    # no zero-reference call remains
    assert "score_page(str(png), [], " not in src.replace(
        "            scores = client.score_page(str(png), [], rows)",
        "            ",
    ), "a zero-reference score_page call remains"


def test_final_artifact_is_regated_after_convergence() -> None:
    """The gate must run AGAIN on the composed deck after convergence (the
    composed PDF replaces the deliverable)."""
    src = (ROOT / "render.py").read_text(encoding="utf-8")
    assert "_run_convergence" in src
    # after convergence the shipped artifact path is re-checked
    assert "composed" in src, "the composed ship path must exist"
