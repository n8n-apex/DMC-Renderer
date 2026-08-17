"""Pattern interface (R1 keystone).

Every pattern module exposes EXACTLY:

    def render(page: dict, ctx: RenderContext) -> PageFragment: ...

`page` is one package page dict from resolved_package.json:
  {slot, st_type, css_template, has_cta, page_numbers, data, assets,
   components, cover_validation}

A pattern returns a PageFragment: `html` is the page's body markup (the
assembler wraps it in one <section class="page st-XX">), `css` is
pattern-scoped CSS the assembler collects ONCE into the shared <head>.
Patterns own their CSS; they must NOT emit <html>/<head>/<style>/@page/
@font-face/:root — those belong to the shared head (assembler.py).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Allow flat imports from the chassis package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brand_tokens import BrandConfig  # noqa: E402
from grammar_loader import Grammar  # noqa: E402

# Sentinel that every chart SVG carries (added in charts_svg._frame). The
# renderer selects chart components by this marker rather than by their position
# in page["components"], so the contract survives a non-chart component being
# appended after a chart. Keep in sync with charts_svg.CHART_SVG_MARKER.
CHART_SVG_MARKER = "dmc:chart"


def _select_chart_svgs(resolved: list[Optional[str]], n: int) -> list[str]:
    """Pick the chart SVGs out of a page's resolved component strings.

    `resolved` is the resolved component list (each entry the SVG string, or
    None when the component file is absent), aligned with page["components"].
    `n` is the page's chart-SPEC count (a defensive cap).

    Prefers EXPLICIT marker selection: any component whose SVG carries the
    `CHART_SVG_MARKER` sentinel is a chart, in package order — robust to a
    non-chart component being appended after a chart. Falls back to the legacy
    tail-slice (last n that resolve) only when NO component is marked, so
    packages built before the marker existed still render unchanged.
    """
    if n <= 0:
        return []
    marked = [s for s in resolved if s and CHART_SVG_MARKER in s]
    if marked:
        return marked[:n]
    tail = resolved[-n:]
    return [s for s in tail if s]


@dataclass(frozen=True)
class PageFragment:
    """One rendered page. `html` = body markup; `css` = pattern-scoped CSS."""

    html: str
    css: str


@dataclass(frozen=True)
class RenderContext:
    """Read-only render context handed to every pattern.

    `resolve_asset` / `resolve_component` turn a package-relative path
    (as stored in the manifest) into an absolute Path / SVG string, or
    None when the file is absent OR the path resolves outside the package
    dir (containment); patterns degrade gracefully on None.

    `report_assets` is the package-level asset list (resolved_package.json
    `report_assets`): the atmospheric gradient / background texture / geometric
    square|wide images that belong to the WHOLE report rather than one page. A
    page-level pattern (e.g. ST-22's banner, a breathing page's ground) can fall
    back to one of these when its own `page["assets"]` carries no image. Each
    entry is a dict with at least {slot_id, image_type, path}; `resolve_report_asset`
    picks the first matching entry's resolved file URI (or None).
    """

    brand: BrandConfig
    grammar: Grammar
    package_dir: Path
    report_assets: list[dict] = field(default_factory=list)

    def resolve_asset(self, rel: Optional[str]) -> Optional[Path]:
        if not rel:
            return None
        root = Path(self.package_dir).resolve()
        try:
            p = (root / rel).resolve()
            # CONTAINMENT: a package-relative path must resolve INSIDE the
            # package dir. is_relative_to, not a string prefix match (a bare
            # prefix let "../pkg-v2/x" escape into a sibling dir whose name
            # shares the package dir as a prefix; symlinks are resolved above).
            # Every caller (slots, components, report assets, legacy patterns)
            # inherits this single check.
            if not p.is_relative_to(root):
                return None
            return p if p.exists() else None
        except (OSError, ValueError):
            # OSError: an unresolvable path. ValueError: e.g. an embedded NUL
            # byte. Both mean "no such asset" for the graceful-None contract.
            return None

    def resolve_component(self, rel: Optional[str]) -> Optional[str]:
        p = self.resolve_asset(rel)
        if p is None:
            return None
        try:
            return p.read_text(encoding="utf-8")
        except (OSError, ValueError):
            # ValueError covers UnicodeDecodeError (its subclass) on a
            # non-UTF-8 file; patterns degrade gracefully on None.
            return None

    def chart_svgs(self, page: dict) -> list[str]:
        """Resolve a page's DATA-DRIVEN chart component SVGs to inline strings.

        The pre-processor extracts chart SPECS onto `page["charts"]` (provenance)
        and renders each one to a brand-themed SVG that it APPENDS — last,
        deterministically — to that slot's `page["components"]` list (see the
        pre-processor's generate_components: ST/extra components first, then one
        chart SVG per spec, in order). Every chart SVG carries an explicit
        `dmc:chart` sentinel (added in charts_svg._frame, the single wrapper all
        chart renderers return through), so the renderer selects chart components
        BY MARKER rather than by their position in `components`. That stays
        correct even if a non-chart component is later appended after a chart
        (the old tail-slice silently broke on any such reorder — infection #14).

        Backward-compatible: packages built before the marker existed carry no
        sentinel, so selection falls back to the legacy tail-slice (last N).

        Returns the inline `<svg>…</svg>` strings (read via resolve_component),
        in package order. Graceful: returns [] when the page has no `charts`, no
        `components`, or none of the chart components resolve — so a chart-host
        pattern embeds the chart(s) when present and renders its non-chart layout
        unchanged when not.
        """
        charts = page.get("charts") or []
        n = len(charts) if isinstance(charts, list) else 0
        if n <= 0:
            return []
        comps = page.get("components") or []
        if not isinstance(comps, list) or not comps:
            return []
        resolved = [self.resolve_component(rel) for rel in comps]
        return _select_chart_svgs(resolved, n)

    def slot_uri(self, page: dict, slot_id: str) -> Optional[str]:
        """Resolve a v2.0 human-photo SLOT to a file:// URI (or None).

        The package v2.0 carries a `slots[]` list on each page — resolved human
        photos (founder / client portrait / team) copied into the package
        `assets/`. Each entry is a dict with at least
        `{slot_id, status, path}`. This finds the FIRST entry whose `slot_id`
        matches AND whose `status == "resolved"`, then resolves its
        package-relative `path` through `resolve_asset` to an absolute file URI.

        Graceful (the contract ALL photo patterns rely on): returns None when
        the page has no `slots`, no matching slot_id, the slot is not resolved
        (`absent` / `missing_required`), or the file is gone — so a caller can
        cleanly fall back to a token treatment or a generated scene and never
        crash or render a broken image. This is the primitive every later 4b
        photo pattern (cover founder, case-study portrait, about/team) uses.
        """
        for s in (page.get("slots") or []):
            if not isinstance(s, dict):
                continue
            if s.get("slot_id") == slot_id and s.get("status") == "resolved":
                p = self.resolve_asset(s.get("path"))
                if p is not None:
                    return p.as_uri()
        return None

    def slot_uris(self, page: dict, slot_id: str) -> list[str]:
        """ALL resolved file:// URIs for a MANY-photo v2.0 slot, in package order.

        The plural of `slot_uri`: where a slot_id can appear MORE THAN ONCE on a
        page (the ST-05 `proof` credibility photos; a `press_logo` / `client_logo`
        wall), this collects EVERY matching entry whose `status == "resolved"`
        and whose package-relative `path` resolves to an existing file, in the
        order they appear in `page["slots"]`. Unresolved (`absent` /
        `missing_required`), non-matching, and missing-file entries are skipped.

        Graceful: returns [] (never None) when the page has no `slots`, no
        matching slot_id, or none of the matches resolve — so a caller renders a
        gallery / logo wall when photos exist and cleanly renders nothing (or a
        text fallback) when they don't. Companion to `slot_uri` (the single-slot
        primitive); both back the 4b photo patterns.
        """
        uris: list[str] = []
        for s in (page.get("slots") or []):
            if not isinstance(s, dict):
                continue
            if s.get("slot_id") == slot_id and s.get("status") == "resolved":
                p = self.resolve_asset(s.get("path"))
                if p is not None:
                    uris.append(p.as_uri())
        return uris

    def resolve_report_asset(
        self,
        slot_ids: tuple[str, ...] = (),
        image_types: tuple[str, ...] = (),
    ) -> Optional[str]:
        """Resolve a package-level report asset to a file:// URI (or None).

        Tries `slot_ids` in order first (exact slot match), then any entry whose
        `image_type` is in `image_types`. Returns the first existing file's URI.
        Graceful: returns None when nothing matches or the file is absent, so the
        caller falls back to a token treatment (never crashes, never renders a
        broken image).
        """
        def _uri_for(entry: dict) -> Optional[str]:
            p = self.resolve_asset(entry.get("path"))
            return p.as_uri() if p is not None else None

        for sid in slot_ids:
            for a in self.report_assets:
                if a.get("slot_id") == sid:
                    uri = _uri_for(a)
                    if uri:
                        return uri
        for it in image_types:
            for a in self.report_assets:
                if a.get("image_type") == it:
                    uri = _uri_for(a)
                    if uri:
                        return uri
        return None
