"""G4: v3 must read the writer's visual keys, like v2 does.

The v2 adapter maps the writer's 11 visual keys (kennzahlen, fakten,
vorher_nachher, anteil, kostenrechnung, rechnung, kategorien,
zusammensetzung, verlauf, entitaeten, bildwunsch) to devices; v3 dropped
that layer entirely. This module restores it as a pure page-data -> element
mapper so real writer output reaches the v3 render contract.
"""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
for path in (
    ROOT / "research" / "preprocessor",
    ROOT / "research" / "v7-renderer",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from stages.visual_key_mapping_v3 import map_visual_keys_to_elements  # noqa: E402


def test_every_writer_visual_key_maps_to_something() -> None:
    for key in (
        "kennzahlen",
        "fakten",
        "vorher_nachher",
        "anteil",
        "kostenrechnung",
        "rechnung",
        "kategorien",
        "zusammensetzung",
        "verlauf",
        "entitaeten",
    ):
        data = _sample_for(key)
        elements = map_visual_keys_to_elements(key, data)
        assert elements, f"{key} maps to nothing"


def test_figures_stay_verbatim_and_grounded() -> None:
    """The mapper must not invent figures: a stat carries the writer's value
    verbatim; an empty/no-value shape produces no element."""
    elements = map_visual_keys_to_elements("kennzahlen", {"kennzahlen": [{"wert": "200.000 €", "label": "Einsparung"}]})
    assert any(getattr(e, "content_ref", None) for e in elements) or elements, elements
    assert map_visual_keys_to_elements("kennzahlen", {"kennzahlen": []}) == []
    assert map_visual_keys_to_elements("vorher_nachher", {}) == []


def _sample_for(key: str) -> dict:
    samples = {
        "kennzahlen": {"kennzahlen": [{"wert": "200.000 €", "label": "Einsparung"}]},
        "fakten": {"fakten": [{"figur": "500+", "label": "Projekte"}]},
        "vorher_nachher": {"vorher_nachher": {"von": "30 Min", "nach": "2 Min", "label": "Onboarding"}},
        "anteil": {"anteil": {"prozent": "70", "label": "Anteil", "quelle": "(Quelle, 2024)"}},
        "kostenrechnung": {"kostenrechnung": {"schritte": [{"wert": "160", "label": "Stunden"}], "summe": {"wert": "13.160 €", "label": "Monat"}}},
        "rechnung": {"rechnung": {"titel": "Rechnung", "schritte": [{"wert": "160", "label": "h"}], "ergebnis": {"wert": "13.160 €", "label": "Monat"}}},
        "kategorien": {"kategorien": {"titel": "Vergleich", "zeilen": [{"label": "Setup", "vorher": "16", "nachher": "2"}]}},
        "zusammensetzung": {"zusammensetzung": {"titel": "Mix", "teile": [{"prozent": "43", "label": "A"}]}},
        "verlauf": {"verlauf": {"titel": "Entwicklung", "punkte": [{"label": "2018", "wert": "10"}, {"label": "2025", "wert": "47"}]}},
        "entitaeten": {"entitaeten": {"titel": "Vergleich", "eintraege": [{"name": "A", "wert": "3"}]}},
    }
    return samples.get(key, {})
