"""Restore the copy-to-device mapping in v3 (G4).

v2 maps the writer's 11 visual keys to devices (docs/ROLE-DEVICE-CONTRACT.md);
v3 dropped that layer entirely, so real writer output never reached the v3
render contract. This module is the pure, brand-agnostic restorer: it reads a
writer page's visual keys and returns element PAYLOAD dicts (kind + data
fields, WITHOUT element_id/region_id), which the materialize stage wraps with
face and region identity.

Grounding rule (non-negotiable): a figure becomes a device ONLY when the
writer actually stated it. The printed value is the writer's figure VERBATIM;
nothing is computed, nothing is invented. An empty or value-less shape yields
nothing (graceful omit), exactly like v2's `_role_devices`.
"""

from __future__ import annotations

import re
from typing import Any


_VISUAL_KEYS = (
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
    "bildwunsch",
)


def _txt(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _rows(value: Any, required: tuple[str, ...]) -> list[dict]:
    """Rows that actually carry a value for at least one required field."""
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if not isinstance(item, dict):
            continue
        if any(_txt(item.get(field)) for field in required):
            out.append(item)
    return out


def _stat_payload(value: str, label: str, source: str) -> dict:
    """A single grounded stat: value verbatim, label + inline source."""
    payload = {"kind": "stat", "content_ref": _txt(label), "value": _txt(value)}
    if _txt(source):
        payload["source"] = _txt(source)
    return payload


def _figures_in(data: dict) -> list[tuple[str, str, str]]:
    """(value, label, source) for every figure the page states, in order."""
    figures: list[tuple[str, str, str]] = []

    for item in _rows(data.get("kennzahlen"), ("wert", "value")):
        value = _txt(item.get("wert") or item.get("value"))
        if value:
            figures.append((value, _txt(item.get("label")), _txt(item.get("quelle"))))

    for item in _rows(data.get("fakten"), ("figur",)):
        value = _txt(item.get("figur"))
        if value:
            figures.append(
                (value, _txt(item.get("label")), _txt(item.get("quelle")))
            )

    return figures


def map_visual_keys_to_elements(key: str, data: dict) -> list[dict]:
    """Return element payloads for one writer visual key on a page.

    ``key`` is one of the 11 visual keys; ``data`` is the page's ``data``
    dict. Returns a list of payload dicts (each carries ``kind`` plus the
    fields the render-contract element of that kind needs, minus the
    element_id/region_id the materialize stage assigns).
    """
    if key == "kennzahlen":
        out = []
        for value, label, source in _figures_in({"kennzahlen": data.get("kennzahlen", [])}):
            out.append(_stat_payload(value, label, source))
        return out

    if key == "fakten":
        out = []
        for value, label, source in _figures_in({"fakten": data.get("fakten", [])}):
            out.append(_stat_payload(value, label, source))
        return out

    if key == "vorher_nachher":
        pair = data.get("vorher_nachher")
        if not isinstance(pair, dict):
            return []
        before, after = _txt(pair.get("von")), _txt(pair.get("nach"))
        if not (before and after):
            return []
        return [
            {
                "kind": "grouped_comparison",
                "label_content_ref": _txt(pair.get("label")),
                "before_value": before,
                "after_value": after,
                "unit": _txt(pair.get("einheit")),
            }
        ]

    if key == "anteil":
        share = data.get("anteil")
        if not isinstance(share, dict):
            return []
        percent = _txt(share.get("prozent") or share.get("wert"))
        if not percent:
            return []
        payload = {
            "kind": "share",
            "label_content_ref": _txt(share.get("label")),
            "value": percent,
        }
        if _txt(share.get("quelle")):
            payload["source"] = _txt(share.get("quelle"))
        return [payload]

    if key in ("rechnung", "kostenrechnung"):
        calc = data.get(key)
        if not isinstance(calc, dict):
            return []
        steps = [
            {"value": _txt(step.get("wert")), "label": _txt(step.get("label"))}
            for step in _rows(calc.get("schritte"), ("wert",))
        ]
        erg = calc.get("summe") if key == "kostenrechnung" else calc.get("ergebnis")
        result_value = _txt((erg or {}).get("wert")) if isinstance(erg, dict) else ""
        if steps and result_value:
            return [
                {
                    "kind": "formula_ladder",
                    "label_content_ref": _txt(calc.get("titel")),
                    "operands": steps,
                    "result_value": result_value,
                    "result_label": _txt((erg or {}).get("label")),
                }
            ]
        return []

    if key == "kategorien":
        cat = data.get("kategorien")
        if not isinstance(cat, dict):
            return []
        rows = _rows(cat.get("zeilen"), ("vorher", "nachher"))
        if not rows:
            return []
        return [
            {
                "kind": "grouped_comparison",
                "label_content_ref": _txt(cat.get("titel")),
                "rows": [
                    {
                        "label": _txt(row.get("label")),
                        "before_value": _txt(row.get("vorher")),
                        "after_value": _txt(row.get("nachher")),
                    }
                    for row in rows
                ],
                "unit": _txt(cat.get("einheit")),
                "before_label": _txt(cat.get("vorher_label")),
                "after_label": _txt(cat.get("nachher_label")),
            }
        ]

    if key == "zusammensetzung":
        comp = data.get("zusammensetzung")
        if not isinstance(comp, dict):
            return []
        parts = _rows(comp.get("teile"), ("prozent",))
        if not parts:
            return []
        return [
            {
                "kind": "distribution",
                "label_content_ref": _txt(comp.get("titel")),
                "segments": [
                    {
                        "value": _txt(part.get("prozent")),
                        "label": _txt(part.get("label")),
                    }
                    for part in parts
                ],
                "source": _txt(comp.get("quelle")),
            }
        ]

    if key == "verlauf":
        series = data.get("verlauf")
        if not isinstance(series, dict):
            return []
        points = _rows(series.get("punkte"), ("wert",))
        if len(points) < 2:
            return []
        return [
            {
                "kind": "time_series",
                "label_content_ref": _txt(series.get("titel")),
                "points": [
                    {"label": _txt(point.get("label")), "value": _txt(point.get("wert"))}
                    for point in points
                ],
                "unit": _txt(series.get("einheit")),
                "source": _txt(series.get("quelle")),
            }
        ]

    if key == "entitaeten":
        entities = data.get("entitaeten")
        if not isinstance(entities, dict):
            return []
        items = _rows(entities.get("eintraege"), ("wert",))
        if not items:
            return []
        return [
            {
                "kind": "grouped_comparison",
                "label_content_ref": _txt(entities.get("titel")),
                "rows": [
                    {
                        "label": _txt(item.get("name")),
                        "after_value": _txt(item.get("wert")),
                        "mark": _txt(item.get("marke")),
                    }
                    for item in items
                ],
                "unit": _txt(entities.get("einheit")),
                "source": _txt(entities.get("quelle")),
            }
        ]

    # bildwunsch is an IMAGE intent, not a figure device; the asset planner
    # owns it. Any unknown key maps to nothing (graceful).
    return []


def visual_keys_present(data: dict) -> list[str]:
    """Which of the writer's visual keys a page actually carries."""
    return [key for key in _VISUAL_KEYS if key in data]
