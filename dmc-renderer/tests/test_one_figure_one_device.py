"""G11 + G12: one-figure-one-device must bind across ALL role devices."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build_live import _role_devices  # noqa: E402
import synthesize_visuals  # noqa: E402


def test_claimed_figure_is_excluded_from_verlauf() -> None:
    """A figure already drawn by another device must not reappear in a series.

    Claiming one of two series points leaves a single point, which is not a
    trend, so the column chart is dropped entirely (never a half-empty chart).
    """
    claimed = {synthesize_visuals.digit_key("10")}
    data = {
        "verlauf": {
            "titel": "Entwicklung",
            "punkte": [{"label": "2018", "wert": "10"}, {"label": "2025", "wert": "47"}],
        }
    }
    devices = _role_devices(data, claimed)
    assert not any(d["preset"] == "column_chart" for d in devices), (
        "a series reduced below 2 points must not render"
    )


def test_claimed_figure_is_excluded_from_entitaeten() -> None:
    claimed = {synthesize_visuals.digit_key("3")}
    data = {
        "entitaeten": {
            "titel": "Vergleich",
            "eintraege": [{"name": "A", "wert": "3"}, {"name": "B", "wert": "9"}],
        }
    }
    devices = _role_devices(data, claimed)
    entity = next(d for d in devices if d["preset"] == "entity_bars")
    kept = [i for i in entity["eintraege"] if i.get("wert") == "3"]
    assert not kept, "a claimed figure must not be re-emitted"
    assert any(i.get("wert") == "9" for i in entity["eintraege"]), "unclaimed figures stay"


def test_unclaimed_figure_survives() -> None:
    claimed = {synthesize_visuals.digit_key("99")}  # unrelated figure
    data = {
        "verlauf": {
            "titel": "Entwicklung",
            "punkte": [{"label": "2018", "wert": "10"}, {"label": "2025", "wert": "47"}],
        }
    }
    devices = _role_devices(data, claimed)
    column = next(d for d in devices if d["preset"] == "column_chart")
    assert len(column["punkte"]) == 2, "unclaimed figures are all emitted"
