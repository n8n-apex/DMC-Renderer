"""DET overlap detection — the structural QA gate (US-510).

The user caught the p18 FAZIT fault: the cost block (25-30% big number) was
rendered INSIDE the absolutely-positioned bottom CTA band — content under a
panel. The existing gates (empty_gap, contrast, fonts) cannot see this class;
it needs geometry. This detector takes the rendered sections' bounding boxes
(from the Chromium print pass) and flags any flow element whose box falls
inside an absolutely-positioned sibling band. It is deterministic and
engine-true (it measures the ACTUAL print geometry).
"""

from __future__ import annotations


def _overlaps(a: dict, b: dict) -> bool:
    """True when a's vertical span intersects b's with real overlap."""
    return a["y"] < b["bottom"] and a["bottom"] > b["y"]


def detect_overlaps(sections: list[dict]) -> list[dict]:
    """Return overlap faults: flow elements rendered under an absolute panel.

    `sections` is the rendered geometry: a list of dicts with `y`, `bottom`,
    `cls` (and optional `position`, `children`). Any section (or child) with
    `position: absolute` defines a PANEL; every NON-absolute flow element
    whose box intersects a panel is a collision (the panel paints over the
    content — the p18 cost-block-inside-CTA fault). Returns
    [{"element", "under", "detail"}] per fault.
    """
    panels: list[dict] = []
    flow: list[dict] = []
    for section in sections:
        if "y" not in section or "bottom" not in section:
            pass  # a container (no own geometry); only its children matter
        elif section.get("position") == "absolute":
            panels.append(section)
        else:
            flow.append(section)
        for child in section.get("children") or []:
            if "y" not in child or "bottom" not in child:
                continue
            # a decorative ghost (z-index:-1, behind content) is NOT an
            # overlapping panel — the Richard section-number watermark.
            if str(child.get("z_index", "")).strip().endswith("-1"):
                continue
            # the rail treatments re-draw their own header/folio chrome inside
            # the section (tp-chrome-top/bottom) because they route to the
            # suppressed `bleed` named page — the SAME furniture the @page
            # margin boxes paint on normal pages (which this detector never
            # sees). It is decorative page chrome, not a content panel; a flow
            # element under it is the padding zone, not a collision.
            if str(child.get("cls", "")).startswith("tp-chrome"):
                continue
            if child.get("position") == "absolute":
                panels.append(child)
            else:
                flow.append(child)

    faults: list[dict] = []
    for el in flow:
        for panel in panels:
            if _overlaps(el, panel):
                faults.append({
                    "element": el.get("cls", "?"),
                    "under": panel.get("cls", "?"),
                    "detail": (
                        f"{el.get('cls','?')} ({el['y']}-{el['bottom']}) "
                        f"under absolute {panel.get('cls','?')} "
                        f"({panel['y']}-{panel['bottom']})"
                    ),
                })
    return faults
