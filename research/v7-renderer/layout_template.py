"""LayoutTemplate — a brand-agnostic, reference-derived page layout (Phase 4).

A template captures a reference page's COMPOSITION as data: a grid, a set of
regions (each a role at a normalized x/y/w/h frame), type/colour ROLES, an
intentional whitespace target, and the source reference pages it was derived
from. It carries geometry and ROLE NAMES only — never client hex, names, or
font literals — so one template renders ANY brand by binding the roles to that
brand's tokens at render time.

The renderer consumes a LayoutTemplate to place the existing component macros
into absolutely-positioned region frames (patterns/_template_driven.py). The
VLM extraction (quality_loop/references/extract_templates.py) WRITES templates
conforming to this schema; ``from_dict`` validates them on the way in.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# The closed ROLE vocabularies (DATA, not client identity). A region's role
# selects which component macro renders it; type/colour roles bind to tokens.
REGION_ROLES: frozenset[str] = frozenset({
    "headline", "lede", "body", "kicker", "eyebrow", "portrait", "stat_rail",
    "stat", "viz", "chart", "footer", "ghost_numeral", "logo_wall", "quote",
    "cta", "qr", "image",
    # a background FILL (e.g. the case-study dark authority rail) drawn behind
    # the content regions it spans (lower z); carries no text of its own.
    "panel",
})
SCALE_ROLES: frozenset[str] = frozenset({
    "display-xl", "display", "hero", "h1", "h2", "h3", "lede", "body",
    "label", "eyebrow", "caption",
})
COLOR_ROLES: frozenset[str] = frozenset({
    "ground", "ink", "accent", "primary", "panel", "footer", "muted",
    "on_dark", "on_panel", "surface",
})

_EPS = 0.001  # geometry tolerance for x+w / y+h within the page


@dataclass(frozen=True)
class Region:
    """One placed element: a role at a normalized x/y/w/h frame (page fractions)."""
    role: str
    x: float
    y: float
    w: float
    h: float
    z: int = 0
    fit: str = "wrap"  # wrap | shrink | clamp


@dataclass(frozen=True)
class Grid:
    columns: int = 1
    margin_top: float = 0.0
    margin_right: float = 0.0
    margin_bottom: float = 0.0
    margin_left: float = 0.0
    gutter: float = 0.0


@dataclass(frozen=True)
class LayoutTemplate:
    st_type: str
    variant: str
    grid: Grid
    regions: tuple[Region, ...]
    type_roles: dict[str, str]
    color_roles: dict[str, str]
    whitespace_target: float
    source_refs: tuple[dict[str, Any], ...]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LayoutTemplate":
        """Build + VALIDATE a template from a plain dict (the extraction output)."""
        g = d.get("grid", {}) or {}
        m = g.get("margin", {}) or {}
        grid = Grid(
            columns=int(g.get("columns", 1)),
            margin_top=float(m.get("top", 0.0)),
            margin_right=float(m.get("right", 0.0)),
            margin_bottom=float(m.get("bottom", 0.0)),
            margin_left=float(m.get("left", 0.0)),
            gutter=float(g.get("gutter", 0.0)),
        )
        regions = tuple(
            Region(
                role=str(r.get("role", "")),
                x=float(r.get("x", 0.0)), y=float(r.get("y", 0.0)),
                w=float(r.get("w", 0.0)), h=float(r.get("h", 0.0)),
                z=int(r.get("z", 0)), fit=str(r.get("fit", "wrap")),
            )
            for r in d.get("regions", [])
        )
        tpl = cls(
            st_type=str(d.get("st_type", "")),
            variant=str(d.get("variant", "default")),
            grid=grid,
            regions=regions,
            type_roles=dict(d.get("type_roles", {})),
            color_roles=dict(d.get("color_roles", {})),
            whitespace_target=float(d.get("whitespace_target", 0.0)),
            source_refs=tuple(d.get("source_refs", [])),
        )
        tpl.validate()
        return tpl

    def validate(self) -> None:
        """Enforce the schema rules; raise ValueError with a precise message.

        Brand-agnostic guard: colour roles must be token ROLE names, never a hex
        or literal value (a client hex in a template is a brand leak).
        """
        if not self.st_type:
            raise ValueError("LayoutTemplate.st_type must be non-empty")
        if not self.source_refs:
            raise ValueError(f"{self.st_type}: source_refs must be non-empty")
        if not (0.0 <= self.whitespace_target <= 1.0):
            raise ValueError(
                f"{self.st_type}: whitespace_target {self.whitespace_target} not in [0,1]"
            )
        if not self.regions:
            raise ValueError(f"{self.st_type}: at least one region required")
        for r in self.regions:
            if r.role not in REGION_ROLES:
                raise ValueError(f"{self.st_type}: unknown region role {r.role!r}")
            for name, val in (("x", r.x), ("y", r.y), ("w", r.w), ("h", r.h)):
                if not (0.0 <= val <= 1.0):
                    raise ValueError(
                        f"{self.st_type}: region {r.role} {name}={val} not a 0..1 fraction"
                    )
            if r.x + r.w > 1.0 + _EPS or r.y + r.h > 1.0 + _EPS:
                raise ValueError(
                    f"{self.st_type}: region {r.role} extends past the page "
                    f"(x+w={r.x + r.w:.3f}, y+h={r.y + r.h:.3f})"
                )
            if r.fit not in ("wrap", "shrink", "clamp"):
                raise ValueError(f"{self.st_type}: region {r.role} bad fit {r.fit!r}")
        for k, v in self.type_roles.items():
            if v not in SCALE_ROLES:
                raise ValueError(
                    f"{self.st_type}: type_role {k}={v!r} not a known scale role"
                )
        for k, v in self.color_roles.items():
            if "#" in str(v) or v not in COLOR_ROLES:
                raise ValueError(
                    f"{self.st_type}: color_role {k}={v!r} must be a token ROLE "
                    f"(brand-agnostic), never a hex / literal value"
                )
