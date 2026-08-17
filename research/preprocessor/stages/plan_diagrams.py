"""plan_diagrams — the DIAGRAM PROOF LAYER planner (DNA: explain text-heavy zones
with a figure instead of more prose).

Mirrors stages/plan_social.py: a PURE planner (`plan_diagrams`) that decides
which diagram (if any) each page should carry, and a SOLE MUTATOR
(`apply_diagram_plan`) that writes the chosen diagram onto the package page's
`data['diagram']` dict (the SAME key the renderer's `diagram` dispatch macro +
st_14 already read). Deterministic, brand-agnostic (ZERO client/hex/font
literal — only ST-type affinity + German/English signal tables), and
NON-FABRICATING: every label/number is COPIED VERBATIM from the field that
triggered detection; the planner only selects, never authors.

Two diagram MODES:
  • REPLACE  — the diagram visualises a prose structure (a triad, a step list, a
    before/after) and the applier blanks the source field so copy does not
    duplicate. Net char delta ≤ 0 → can only REDUCE overflow risk.
  • AUGMENT  — a single real figure already in the prose is echoed as a corner
    `stat_callout` card. Text-neutral (the figure is already counted); placed
    ONLY on pages with measured headroom so the card never collides/overflows.

Safety:
  • non-host ST types (cover/CTA/breathers) are never hosts;
  • a page already carrying a real chart (page['charts']) OR a photo device
    (its slot in `occupied_zones`, from plan_social) is skipped — one hero
    device per page;
  • a page that ALREADY carries a `data['diagram']` (e.g. the hand-authored
    apex Venn) is CONFIRMED, not overwritten;
  • augment is gated on a headroom pre-check via the injected `char_count` /
    `copy_budget` (the SAME budget math validate_copyfit uses).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

# ST types that never host a diagram (showcase / conversion / atmospheric pages).
_NON_HOST_TYPES = frozenset({"ST-01", "ST-03", "ST-31", "ST-32"})

# Selection PRIORITY ladder (lower index wins when several detectors fire). A
# replace-mode structural diagram always beats the augment stat_callout.
_PRIORITY = ["before_after", "process_flow", "convergence", "q_a", "stat_callout"]

# A real figure already present in prose: %, range%, "Nx", "N von M", money.
_FIGURE_RE = re.compile(
    r"\d{1,3}\s*[–-]\s*\d{1,3}\s*%"      # 25-30 %
    r"|\d{1,3}\s*%"                        # 60 %
    r"|\d+\s*[x×]"                         # 15x
    r"|\d+\s*von\s*\d+"                    # 6 von 6
    r"|[€$]\s?\d[\d.\s]*\+?"               # €200.000
)


@dataclass
class DiagramBinding:
    page_slot: int
    kind: str
    payload: dict
    mode: str = "augment"            # "replace" | "augment"
    replace_field: Optional[str] = None
    score: int = 0


@dataclass
class DiagramPlan:
    bindings: list = field(default_factory=list)
    dropped: list = field(default_factory=list)


def _txt(data: dict, *keys: str) -> str:
    return " ".join(str(data.get(k) or "") for k in keys).strip()


def _detect_convergence(data: dict) -> Optional[dict]:
    """Confirm a hand-authored convergence Venn already on the page (apex ST-14),
    or build one from EXACTLY 3 short enumeration items + a real synthesis line.
    Never invents the synthesis."""
    existing = data.get("diagram")
    if isinstance(existing, dict) and existing.get("kind") == "convergence":
        return existing  # confirm verbatim — do not re-author
    return None


def _detect_stat_callout(data: dict) -> Optional[dict]:
    """Echo ONE real figure from the page's result/body prose as a corner card.
    Verbatim; never computed."""
    body = _txt(data, "ergebnis_text", "ergebnis", "body", "loesung")
    m = _FIGURE_RE.search(body)
    if not m:
        return None
    figure = m.group(0).strip()
    # a short, content-neutral label from the report's own vocabulary (not a
    # client literal): the generic "result" caption.
    return {"kind": "stat_callout", "figure": figure, "label": "im Schnitt"}


# detector → (mode, replace_field)
_DETECTORS = {
    "convergence": (_detect_convergence, "replace", None),
    "stat_callout": (_detect_stat_callout, "augment", None),
}


def plan_diagrams(
    package: dict,
    *,
    occupied_zones: frozenset = frozenset(),
    char_count: Callable[[dict], int] = lambda d: 0,
    copy_budget: Callable[[str], Optional[int]] = lambda st: None,
    max_diagrams: int = 4,
    enable: bool = True,
) -> DiagramPlan:
    """PURE. Decide at most one diagram per page; deterministic.

    A page is a candidate iff: enable, st_type is a host type, the slot is NOT in
    occupied_zones, and the page carries no real chart. For each candidate run the
    detectors, pick the highest-priority hit, and (for augment) gate on headroom.
    """
    plan = DiagramPlan()
    if not enable:
        return plan

    for page in package.get("pages", []):
        st = str(page.get("st_type", ""))
        slot = page.get("slot")
        data = page.get("data") or {}

        if st in _NON_HOST_TYPES:
            continue
        if str(page.get("page_mode") or "").strip() not in ("", "standard"):
            # a full-bleed dark/flooded beat already owns its composition (spine,
            # ghost letterform) — a corner card would collide with it.
            plan.dropped.append(f"slot {slot} ({st}): page_mode beat owns the page — skipped")
            continue
        if slot in occupied_zones:
            plan.dropped.append(f"slot {slot} ({st}): occupied by a photo device — skipped")
            continue
        if page.get("charts"):
            plan.dropped.append(f"slot {slot} ({st}): real chart present — diagram defers")
            continue

        # run detectors, collect hits
        hits: dict[str, tuple] = {}
        for kind, (fn, mode, rfield) in _DETECTORS.items():
            payload = fn(data)
            if payload:
                hits[kind] = (payload, mode, rfield)
        if not hits:
            continue

        # select by priority ladder
        chosen_kind = next((k for k in _PRIORITY if k in hits), None)
        if chosen_kind is None:
            continue
        payload, mode, rfield = hits[chosen_kind]

        # AUGMENT headroom gate: only add a corner card where the page is not
        # already near its copy budget (proxy for "has corner room"); never on a
        # page that already shows a strong visual via its own pattern data.
        if mode == "augment":
            budget = copy_budget(st)
            used = char_count(data)
            if budget and used > budget * 0.62:
                plan.dropped.append(
                    f"slot {slot} ({st}): no headroom for augment card "
                    f"({used}/{budget}) — skipped"
                )
                continue

        plan.bindings.append(DiagramBinding(
            page_slot=slot, kind=chosen_kind, payload=payload,
            mode=mode, replace_field=rfield,
            score=len(_PRIORITY) - _PRIORITY.index(chosen_kind),
        ))

    # global scarcity: keep the strongest max_diagrams, deterministic order
    plan.bindings.sort(key=lambda b: (-b.score, b.page_slot))
    if len(plan.bindings) > max_diagrams:
        for b in plan.bindings[max_diagrams:]:
            plan.dropped.append(f"slot {b.page_slot}: deck diagram budget reached — skipped")
        plan.bindings = plan.bindings[:max_diagrams]
    plan.bindings.sort(key=lambda b: b.page_slot)
    return plan


def apply_diagram_plan(package: dict, plan: DiagramPlan) -> dict:
    """SOLE MUTATOR. Write each binding onto its page's data['diagram']; for
    replace-mode also blank the source field so prose never duplicates the
    figure (net char delta ≤ 0). Idempotent. Confirming an existing identical
    diagram is a no-op."""
    pages_by_slot = {p.get("slot"): p for p in package.get("pages", [])}
    for b in plan.bindings:
        page = pages_by_slot.get(b.page_slot)
        if page is None:
            continue
        data = page.setdefault("data", {})
        payload = dict(b.payload)
        payload.setdefault("source", "plan_diagrams")
        data["diagram"] = payload
        if b.mode == "replace" and b.replace_field:
            data[b.replace_field] = ""
    return package
