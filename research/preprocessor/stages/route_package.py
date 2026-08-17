"""Shared brand-agnostic post-assemble routing used by BOTH the fixture builder
(fixtures/apex/build_package.py) and the live /render endpoint (main.py), so the
two stop diverging. Extracted verbatim from build_package.py's routing block:
social placement -> dark-divider cadence -> optional LLM restructure -> diagram
proof layer. Mutates `pkg` in place. NO client literals; every social home is
derived from pkg data. See docs/superpowers/plans/2026-06-17-bake-in-generative-pipeline.md.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from stages.plan_social import plan_social, apply_social_plan
from stages.plan_diagrams import plan_diagrams, apply_diagram_plan, _NON_HOST_TYPES
from stages.validate_copyfit import ST_COPY_BUDGET_CHARS
from stages.validate_copy import _collect_all_strings
from stages.restructure_page import restructure_page, apply_restructure


@dataclass
class RouteReport:
    bindings: list = field(default_factory=list)
    dropped: list = field(default_factory=list)
    restructured: list = field(default_factory=list)


async def route_package(
    pkg: dict,
    *,
    manifest=None,
    social_root: Path,
    assets_dir: Path,
    enable_profile_grid: bool = False,
    openrouter_key: str = "",
    restructure_model: str = "",
    restructure_cache_dir: Path | None = None,
    dark_divider_types: frozenset = frozenset({"ST-07B"}),
) -> RouteReport:
    report = RouteReport()
    social_plan = None

    # ---- social asset routing (only with a classified manifest) ----
    if manifest is not None:
        case_clients: dict[int, str] = {}
        breather_slots: list[int] = []
        about_slot = None
        fazit_slot = None
        founder_name = ""
        founder_role = ""
        for p in pkg["pages"]:
            d = p.get("data") or {}
            st = p["st_type"]
            slot = p["slot"]
            if st == "ST-07A":
                kunde = d.get("kunde") if isinstance(d.get("kunde"), dict) else {}
                name = (kunde or {}).get("name") or ""
                if name:
                    case_clients[slot] = name
            elif st == "ST-31":
                breather_slots.append(slot)
            elif st == "ST-05" and about_slot is None:
                about_slot = slot
            elif st == "ST-FAZIT" and fazit_slot is None:
                fazit_slot = slot
            elif st == "ST-01":
                author = d.get("author") if isinstance(d.get("author"), dict) else {}
                founder_name = (author or {}).get("name") or ""
                founder_role = (author or {}).get("role") or ""
        breather_slots.sort()

        def _exists(rel: str) -> bool:
            return (social_root / rel).exists()

        social_plan = plan_social(
            manifest,
            case_clients=case_clients,
            breather_slots=breather_slots,
            about_slot=about_slot,
            fazit_slot=fazit_slot,
            founder_name=founder_name,
            founder_role=founder_role,
            asset_exists=_exists,
            enable_profile_grid=enable_profile_grid,
        )
        apply_social_plan(pkg, social_plan, assets_dir=assets_dir, source_root=social_root)
        report.bindings = list(social_plan.bindings)
        report.dropped = list(social_plan.dropped)

    # ---- light/dark cadence: dark dividers on the configured ST types ----
    for p in pkg["pages"]:
        if p.get("st_type") in dark_divider_types:
            p["page_mode"] = "dark_divider"

    # ---- optional LLM restructure of over-budget host pages ----
    if openrouter_key:
        def _pchars(d) -> int:
            return sum(len(s) for s in _collect_all_strings(d or {}))

        flagged = [
            p for p in pkg["pages"]
            if p.get("st_type") not in _NON_HOST_TYPES
            and str(p.get("page_mode") or "").strip() in ("", "standard")
            and (ST_COPY_BUDGET_CHARS.get(p["st_type"]) or 0)
            and _pchars(p.get("data")) > (ST_COPY_BUDGET_CHARS[p["st_type"]] * 0.9)
        ]
        if flagged:
            results = await asyncio.gather(*[
                restructure_page(
                    st_type=p["st_type"], page_data=p.get("data") or {},
                    copy_budget=ST_COPY_BUDGET_CHARS.get(p["st_type"]),
                    api_key=openrouter_key, model=restructure_model,
                    cache_dir=restructure_cache_dir,
                )
                for p in flagged
            ])
            apply_restructure(flagged, results)
            report.restructured = [p["slot"] for p, r in zip(flagged, results) if r is not None]

    # ---- diagram proof layer (data-driven; always runs) ----
    occupied = frozenset(
        b.page_slot for b in (social_plan.bindings if social_plan else [])
        if b.page_slot is not None
    )
    diagram_plan = plan_diagrams(
        pkg,
        occupied_zones=occupied,
        char_count=lambda d: sum(len(s) for s in _collect_all_strings(d)),
        copy_budget=lambda st: ST_COPY_BUDGET_CHARS.get(st),
    )
    apply_diagram_plan(pkg, diagram_plan)
    return report
