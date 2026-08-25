"""Template BANK - the unified, browseable-by-context catalog of the DMC system.

THE ONE VOCABULARY (replaces the pattern/treatment/device confusion):

    TEMPLATE = a page composition (the sheet skeleton). Rendered on the v2
               path by treatment_engine.render(page, ctx, treatment_name).
    MODULE   = a reusable mid-level BLOCK inside a template (rail, callout,
               ladder, wall...). Some exist as template fragments.
    DEVICE   = an atomic data-viz / content primitive (the viz presets).

The bank is one registry over this hierarchy, seeded from:
  - the v3 composition registry (composition_registry/): the CONTEXT layer with
    the authoritative rolenames + per-region capacity/contract, and
  - the LIVE renderer treatment catalog (treatment_catalog.py): the actual
    template entries that render, and
  - the LIVE device presets (components/viz*.jinja).

"Browse by context" = query by ROLE (the v3 RoleName) + data contract. The
pre-processor planner uses this same catalog to choose a template per page; the
renderer fills the chosen template's devices with the page's data.

Brand-agnostic: no client name, no hex, no font literal. This module only joins
structural metadata (names, roles, contracts); it carries no client data.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

_HERE = Path(__file__).resolve().parent          # research/v7-renderer
_RESEARCH = _HERE.parent                          # research/
_COMPONENTS = _HERE / "components"
_REGISTRY_PATH = _RESEARCH / "composition_registry" / "families" / "dmc-v1.json"
_ATLAS_PATH = _RESEARCH / "reference-atlas" / "reference-atlas.json"


@dataclass
class TemplateEntry:
    """A TEMPLATE (page composition) in the bank."""

    name: str
    archetype: str
    formats: tuple[str, ...]
    required_fields: tuple[str, ...]
    needs_image: bool
    built: bool


@dataclass
class ModuleEntry:
    """A MODULE (reusable block) in the bank."""

    name: str
    kind: str = "block"
    instances: list[str] = field(default_factory=list)


@dataclass
class DeviceEntry:
    """A DEVICE (atomic data-viz primitive) in the bank."""

    name: str
    module: str = "viz"
    story_tag: str = "comparison"


@dataclass
class ContextEntry:
    """A CONTEXT (v3 role-scoped composition, the metadata spine)."""

    name: str
    roles: list[str]
    regions: list[dict]
    evidence_bounds: dict


_ALLOWS = None  # placeholder for an explicit role->allowed-templates map (set by the planner seeding)


# --------------------------------------------------------------------------- #
# DEVICE level: introspect the viz component macros
# --------------------------------------------------------------------------- #
_DEVICE_RE = re.compile(r"{%\s*macro\s+([a-z_][a-z0-9_]*)")


def _device_entries() -> list[DeviceEntry]:
    names: set[str] = set()
    if _COMPONENTS.exists():
        for fp in sorted(_COMPONENTS.glob("viz*.jinja")):
            try:
                names.update(_DEVICE_RE.findall(fp.read_text(encoding="utf-8")))
            except OSError:
                continue
    names.discard("viz")
    tag = _STORY_TAG  # the mapping is declared below; the reference is lazy
    return [DeviceEntry(name=n, story_tag=tag.get(n, "comparison"))
            for n in sorted(names)]


_STORY_TAG: dict[str, str] = {
    "ba_bars": "comparison",
    "bar_compare": "comparison",
    "grouped_bars": "comparison",
    "stacked_bar_100": "part_to_whole",
    "entity_bars": "ranking",
    "column_chart": "comparison",
    "transform_arrow": "change",
    "completion_ring": "part_to_whole",
    "donut": "part_to_whole",
    "split_bar": "part_to_whole",
    "gauge": "magnitude",
    "radial_cluster": "part_to_whole",
    "icon_array": "magnitude",
    "stat_strip": "magnitude",
    "money_bar": "magnitude",
    "mega_numeral": "magnitude",
    "kpi_card": "magnitude",
    "ranked_bars": "ranking",
    "phase_timeline": "flow",
    "step_cascade": "flow",
    "formula_ladder": "flow",
    "icon_stat_row": "magnitude",
}


# --------------------------------------------------------------------------- #
# TEMPLATE level: the live renderer treatments
# --------------------------------------------------------------------------- #
def _template_entries() -> list[TemplateEntry]:
    try:
        from treatment_catalog import register_all  # type: ignore
        from treatment_engine import TREATMENTS, treatment_is_built  # type: ignore
        register_all()
    except Exception:  # noqa: BLE001 - renderer deps not present
        return []
    out: list[TemplateEntry] = []
    for name, t in TREATMENTS.items():
        out.append(TemplateEntry(
            name=name,
            archetype=t.archetype,
            formats=tuple(sorted(t.formats)),
            required_fields=tuple(t.required_fields),
            needs_image=t.needs_image,
            built=_built(t, treatment_is_built),
        ))
    return sorted(out, key=lambda e: e.name)


def _built(t, is_built) -> bool:
    try:
        return is_built(t.name)
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------- #
# MODULE level: named structural blocks (seeded; extend as templates grow)
# --------------------------------------------------------------------------- #
_MODULE_NAMES: tuple[str, ...] = (
    "hero band", "headline + kicker", "body prose", "numbered list",
    "dark stat rail", "stat stack", "callout block", "quote block",
    "step spine", "comparison band", "proportion row", "classification grid",
    "search test", "founder ident", "footer cta list", "logo/credential wall",
)


def _module_entries() -> list[ModuleEntry]:
    return [ModuleEntry(name=n) for n in _MODULE_NAMES]


# --------------------------------------------------------------------------- #
# CONTEXT level: the v3 composition families (the metadata spine)
# --------------------------------------------------------------------------- #
def _context_entries() -> list[ContextEntry]:
    rp = Path(_REGISTRY_PATH)
    if not rp.exists():
        return []
    try:
        raw = json.loads(rp.read_text(encoding="utf-8"))
        families = raw.get("families", [])
    except Exception:  # noqa: BLE001
        return []
    out: list[ContextEntry] = []
    for fam in families:
        regions = []
        for r in (fam.get("regions") or []):
            caps = r.get("capacities") or []
            regions.append({
                "region": r.get("region_id"),
                "purpose": r.get("semantic_purpose"),
                "min_words": caps[0].get("min_words", 0) if caps else 0,
                "max_words": caps[0].get("max_words", 0) if caps else 0,
            })
        out.append(ContextEntry(
            name=fam.get("family_id", ""),
            roles=list(fam.get("supported_roles") or []),
            regions=regions,
            evidence_bounds=fam.get("evidence_bounds") or {},
        ))
    return out


# --------------------------------------------------------------------------- #
# The unified catalog: browse by ROLE (context) + template + device
# --------------------------------------------------------------------------- #
def catalog() -> dict:
    """The full bank: contexts (role->composition), templates, modules, devices.

    This is what a human opens ("browse by context") and what the planner
    queries. Deterministic, brand-agnostic.
    """
    return {
        "contexts": [c.__dict__ for c in _context_entries()],
        "templates": [t.__dict__ for t in _template_entries()],
        "modules": [m.__dict__ for m in _module_entries()],
        "devices": [d.__dict__ for d in _device_entries()],
    }


def browse_by_role(role: str) -> dict:
    """Templates (and their context) that serve the given ROLE.

    ROLE names come from the v3 vocabulary: cover, outlook, about, status_quo,
    false_beliefs, case_study, theory, mechanism, trust_proof, summary,
    objections, collaboration, cta, brand_breather. The preprocessor planner
    calls this to shortlist templates for a page before applying the data
    contract + adjacency rules.

    Also returns the CANDIDATE DEVICES for the role: every device whose story
    tag the role's contexts favour. Conservative: all devices tagged for the
    role's story families are candidates; the template decides at render which
    it actually hosts via data.viz.
    """
    contexts = [c.__dict__ for c in _context_entries() if role in c.roles]
    templates = [t.__dict__ for t in _template_entries() if _template_roles(t.name, role)]
    # candidate devices for the role: the full device set (the template decides
    # at render which it actually hosts via page.data.viz; the catalog keeps
    # them all so a human browse sees every available mark).
    devices = [d.__dict__ for d in _device_entries()]
    return {"role": role, "contexts": contexts, "templates": templates,
            "devices": devices}


def _template_roles(name: str, role: str) -> bool:
    """A brand-agnostic heuristic: which template name plausibly serves a role.

    KEYED ONLY on the structural name/archetype - the catalog is the join point,
    and the planner's final word is the data contract + adjacency (treatment_
    stylist). A missed tag here only changes what BROWSE shows; the assignment
    is unaffected. Unknown roles fall back to False (not shown) so the catalog
    stays conservative.
    """
    role_keywords = {
        "cover": {"cover", "hero", "stacked"},
        "outlook": {"editorial", "two_stack", "quote", "dashboard"},
        "about": {"editorial", "side_rail", "portrait", "metric"},
        "status_quo": {"dashboard", "editorial", "two_stack", "metric"},
        "false_beliefs": {"stack", "two_stack"},
        "case_study": {"case_study", "metric"},
        "theory": {"dark_divider", "editorial"},
        "mechanism": {"timeline", "process", "dashboard"},
        "trust_proof": {"side_rail", "metric"},
        "summary": {"stacked_hero", "two_stack", "editorial"},
        "objections": {"quote"},
        "collaboration": {"timeline"},
        "cta": {"stacked_hero", "editorial"},
        "brand_breather": {"dark_divider"},
    }
    kw = role_keywords.get(role, set())
    if not kw:
        return False
    n = name.lower()
    return any(k in n for k in kw)


def catalog_json() -> str:
    return json.dumps(catalog(), ensure_ascii=False, indent=2)


def main() -> int:
    import sys
    role = sys.argv[1] if len(sys.argv) > 1 else ""
    if role:
        print(json.dumps(browse_by_role(role), ensure_ascii=False, indent=2))
    else:
        print(repr(catalog()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())