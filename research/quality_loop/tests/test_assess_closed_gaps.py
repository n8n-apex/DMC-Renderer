"""US-020: the standing closed-gap assessment harness is honest."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "quality_loop"))

from assess_closed_gaps import REGISTRY, assess  # noqa: E402


def test_registry_lists_every_closed_gap() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert registry["schema_version"] == "1.0"
    ids = [g["id"] for g in registry["gaps"]]
    assert "G1" in ids and "G24" in ids and "D6" in ids, "the full gap register is present"
    assert len(ids) == len(set(ids)), "no duplicate gap ids"


def test_registry_has_no_unknown_check_types() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    known = {
        "suite_zero", "test", "harness", "node_test", "guard",
        "grep_present", "grep_absent", "file", "manual",
    }
    for gap in registry["gaps"]:
        assert gap["check_type"] in known, gap


def test_manually_open_gap_is_reported_not_failing(tmp_path: Path) -> None:
    registry = {
        "gaps": [
            {"id": "X1", "description": "manual", "check_type": "manual", "check": "x"},
        ]
    }
    results = assess(registry)
    assert results[0]["status"] == "CLOSED"  # manual is not a regression
    assert results[0]["check_type"] == "manual"


def test_a_failing_check_is_reopened(tmp_path: Path) -> None:
    """A gap whose grep_absent check now finds the literal is REOPENED."""
    target = tmp_path / "sample.txt"
    target.write_text("fazit_background slot", encoding="utf-8")
    registry = {
        "gaps": [
            {
                "id": "X2",
                "description": "should be absent",
                "check_type": "grep_absent",
                "check": f"fazit_background in {target}",
            },
        ]
    }
    results = assess(registry)
    assert results[0]["status"] == "REOPENED"
