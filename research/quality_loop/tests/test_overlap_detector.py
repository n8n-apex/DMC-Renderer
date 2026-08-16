"""US-510 QA gate: DET overlap detection — content rendered under an
absolutely-positioned panel must be flagged (the p18 FAZIT cost-block-inside-
CTA-band fault the user caught). This is the structural check the visual
review alone cannot run reliably (it needs pixels + geometry)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from overlap_detector import detect_overlaps  # noqa: E402


def test_detects_flow_content_under_absolute_panel() -> None:
    """A flow element whose box falls inside an absolute bottom-pinned band is
    an overlap — the p18 cost-block-inside-CTA fault."""
    # the flow children live in a NON-absolute section; the CTA band is the
    # absolute panel. The detector flags flow elements under the panel.
    sections = [
        {
            "cls": "fz-fill-flow", "position": "static", "children": [
                {"cls": "fz-header--fill", "y": 17693, "bottom": 17814},
                {"cls": "fz-body--fill", "y": 17814, "bottom": 18142},
                {"cls": "fz-cost--fill", "y": 18477, "bottom": 18630},
            ],
        },
        {"cls": "fz-cta", "y": 18475, "bottom": 18679, "position": "absolute"},
    ]
    faults = detect_overlaps(sections)
    assert any("cost" in f.get("element", "") for f in faults), faults


def test_no_overlap_when_flow_reserves_the_band() -> None:
    """When the flow stops above the absolute band, nothing is flagged."""
    sections = [
        {
            "cls": "fz-fill-flow", "children": [
                {"cls": "fz-cost--fill", "y": 17600, "bottom": 18000},
            ],
        },
        {"cls": "fz-cta", "y": 18475, "bottom": 18679, "position": "absolute"},
    ]
    faults = detect_overlaps(sections)
    assert faults == []


def test_ignores_non_absolute_siblings() -> None:
    """Two normal-flow siblings never collide (no false positive)."""
    sections = [
        {"cls": "a", "y": 0, "bottom": 100, "position": "static"},
        {"cls": "b", "y": 50, "bottom": 150, "position": "static"},
    ]
    assert detect_overlaps(sections) == []
