"""Exact tuple dispatch for v3 composition-family renderers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from families.dmc_v1 import FAMILY_IDS, render_case_narrative, render_dmc_family


FamilyKey = tuple[str, str]
FamilyRenderer = Callable[..., str]


class FamilyRendererRegistry:
    def __init__(self) -> None:
        self._renderers: dict[FamilyKey, FamilyRenderer] = {}

    def register(
        self,
        key: FamilyKey,
        renderer: FamilyRenderer,
        *,
        replace: bool = False,
    ) -> None:
        if key in self._renderers and not replace:
            raise ValueError(f"family renderer already registered: {key}")
        self._renderers[key] = renderer

    def resolve(self, key: FamilyKey) -> FamilyRenderer:
        try:
            return self._renderers[key]
        except KeyError as error:
            raise KeyError(f"family renderer is not registered: {key}") from error

    def render(
        self,
        key: FamilyKey,
        fragment: Any,
        bundle: Any,
        *,
        rendered_family_id: str | None = None,
    ) -> str:
        return self.resolve(key)(
            fragment,
            bundle,
            rendered_family_id=rendered_family_id,
        )


_FAMILY_RENDERERS = {
    "case_narrative": render_case_narrative,
}


# Versions frozen into contracts built before the composition registry was
# readable from here. A contract keeps rendering at the version it froze.
_HISTORICAL_VERSIONS = ("1.0.0", "1.1.0")


def _declared_versions() -> dict[str, tuple[str, ...]]:
    """Versions each family currently declares in the composition registry.

    Read rather than pinned: a family version bump is a registry decision,
    and a renderer that has to be edited to keep up will silently fall out
    of step with it.
    """
    from pathlib import Path
    import json

    path = (
        Path(__file__).resolve().parents[2]
        / "composition_registry"
        / "families"
        / "dmc-v1.json"
    )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    declared: dict[str, tuple[str, ...]] = {}
    for family in raw.get("families", ()):
        family_id = family.get("family_id")
        version = family.get("version")
        if family_id and version:
            declared[family_id] = (version,)
    return declared


def default_registry() -> FamilyRendererRegistry:
    registry = FamilyRendererRegistry()
    declared = _declared_versions()
    for family_id in FAMILY_IDS:
        renderer = _FAMILY_RENDERERS.get(family_id, render_dmc_family)
        versions = set(_HISTORICAL_VERSIONS) | set(declared.get(family_id, ()))
        for version in sorted(versions):
            registry.register((family_id, version), renderer, replace=True)
    return registry
