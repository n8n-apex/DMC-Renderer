"""Stage 8 — package assembly.

Takes the outputs of Stages 1-7 and writes a self-contained directory
structure that the renderer can consume:

    output_dir/
    ├── resolved_package.json    ← the master manifest
    ├── assets/                  ← downloaded images
    │   ├── 1_cover_hero.png
    │   └── …
    ├── components/              ← SVG strings as files
    │   ├── 4_component_0.svg
    │   └── …
    └── fonts/                   ← copies of resolved font files
        ├── Montserrat[wght].ttf
        └── SourceSans3[wght].ttf

Design contract:
  - All paths inside `resolved_package.json` are RELATIVE to
    `output_dir` (so the directory is portable — move it, it still
    works).
  - SVG strings are written as files, NOT embedded in the JSON (they
    can be 50-100KB each and would bloat the response).
  - `cover_validation` appears on the cover page object AND in the
    top-level `validation` section (the renderer needs the
    `headline_size_class` per page).
  - Validation warnings are non-blocking — the package always
    assembles. QA reviews the warnings out of band.
  - Stubbed assets carry `path: null` in the manifest; the renderer
    must handle null gracefully.

The full manifest dict is built by `_build_manifest()` and written
once via `json.dump`. Stage 8 never mutates upstream stage outputs.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from models import (
    CopyWarning,
    CoverValidation,
    FontConfig,
)
from models_package import ResolvedPackageManifest
from stages.generate_assets import AssetPlan, AssetResult
from stages.plan_layout import LayoutPlan, PlannedPage
from stages.resolve_axes import ResolvedAxes


PACKAGE_SCHEMA_VERSION = "2.0"

# The transitional 4-field block the not-yet-upgraded renderer reads
# (`package_loader` whitelists exactly these). Derived from the canonical
# 7-field `axes` so theming keeps working in the 4a→4b gap.
_BRAND_AXES_KEYS = ("headline_type", "ground_mode", "texture", "accent_mechanic")


def _stable_generated_at(record_id: str) -> str:
    """A deterministic ISO instant derived from the record id (G10).

    Same input must yield identical package bytes. A wall-clock timestamp
    breaks that, so the instant is hashed from the record id into a fixed
    anchor date offset. The result is a stable, readable ISO-8601 string that
    identifies the build without claiming to be wall-clock time.
    """
    digest = hashlib.sha256(str(record_id).encode("utf-8")).digest()
    anchor_seconds = 1_700_000_000  # 2023-11-14T22:13:20Z
    offset = int.from_bytes(digest[:4], "big") % (365 * 24 * 3600)
    from datetime import datetime, timezone

    instant = datetime.fromtimestamp(anchor_seconds + offset, tz=timezone.utc)
    return instant.isoformat().replace("+00:00", "Z")


# ─────────────────────────────────────────────────────────────────────────────
# Output dataclass
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ResolvedPackage:
    """In-memory return value from `assemble_package`. The actual data
    lives on disk under `output_dir`; this is the handle.
    """

    package_path: Path
    output_dir: Path
    page_count: int
    total_warnings: int
    asset_summary: dict = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Manifest builders
# ─────────────────────────────────────────────────────────────────────────────


def _font_block(
    name: str, abs_path: Optional[str], source: str, output_dir: Path,
) -> dict:
    """Build a font entry. `abs_path` is the on-disk source font; the
    block records the path RELATIVE to the package.
    """
    if abs_path is None:
        return {"name": name, "path": None, "source": source}
    p = Path(abs_path)
    if not p.exists():
        return {"name": name, "path": None, "source": source}
    return {"name": name, "path": f"fonts/{p.name}", "source": source}


def _copy_fonts(font_config: FontConfig, output_dir: Path) -> None:
    """Copy the heading + body font files into `output_dir/fonts/`.

    Skips if no source path or source missing on disk. Skips if the
    destination already exists (idempotent for re-runs).
    """
    fonts_dir = output_dir / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    for abs_path in (font_config.font_heading_path, font_config.font_body_path):
        if not abs_path:
            continue
        src = Path(abs_path)
        if not src.exists():
            continue
        dst = fonts_dir / src.name
        if dst.exists():
            continue
        shutil.copy2(src, dst)


def _write_components(
    components: dict[int, list[str]], output_dir: Path,
) -> dict[int, list[str]]:
    """Write every SVG string to a file under `output_dir/components/`.

    Returns `{slot: [relative_path, ...]}` — relative to `output_dir`.
    """
    comp_dir = output_dir / "components"
    comp_dir.mkdir(parents=True, exist_ok=True)
    out: dict[int, list[str]] = {}
    for slot, svgs in components.items():
        rel_paths: list[str] = []
        for i, svg in enumerate(svgs):
            fname = f"{slot}_component_{i}.svg"
            (comp_dir / fname).write_text(svg, encoding="utf-8")
            rel_paths.append(f"components/{fname}")
        out[slot] = rel_paths
    return out


def _asset_manifest_entry(asset: AssetResult, output_dir: Path) -> dict:
    """One asset's view inside `pages[].assets[]` of the manifest."""
    if asset.path is None:
        rel = None
    else:
        try:
            rel = f"assets/{asset.path.name}"
        except AttributeError:
            rel = None
    return {
        "slot_id": asset.slot_id,
        "image_type": asset.image_type,
        "path": rel,
        "status": asset.status,
        "message": asset.message,
        "prompt": asset.prompt,
        "negative_prompt": asset.negative_prompt,
    }


def _drive_slot_entry(
    slot, page_slot: int, client_dir: Path, output_dir: Path,
) -> dict:
    """Render one drive-sourced ResolvedSlot into its package `slots[]` dict,
    copying the resolved file into `output_dir/assets/` with a deterministic
    name. NEVER raises: a copy failure degrades to status="failed" + warning.

    - resolved → copy `client_dir/slot.path` → `assets/<dest>`; emit the slot
      with `path` rewritten to the package-relative `assets/<dest>`.
    - missing_required / absent → emit with `path=None` (its status/expected
      stay so QA sees the exact file to add, DNA §7.3).
    """
    entry = slot.model_dump()
    if slot.status != "resolved" or not slot.path:
        entry["path"] = None
        return entry

    suffix = Path(slot.path).suffix
    idx = f"_{slot.index}" if slot.index is not None else ""
    dest = f"{page_slot}_{slot.slot_id}{idx}{suffix}"
    src = Path(client_dir) / slot.path
    dst = Path(output_dir) / "assets" / dest
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    except OSError as exc:
        entry["status"] = "failed"
        entry["path"] = None
        warns = list(entry.get("warnings") or [])
        warns.append(f"failed to copy drive photo {slot.path!r} for slot {page_slot}: {exc!r}")
        entry["warnings"] = warns
        return entry
    entry["path"] = f"assets/{dest}"
    return entry


def _write_page_identity(page_dict: dict, pp) -> None:
    """US-602: write the section/physical-page identity fields onto a page
    dict ONLY when the plan set them (a section that expanded across physical
    pages). Single-page sections carry none — back-compat with the flat
    one-slot-one-sheet package (no key, no behaviour change)."""
    for _key in (
        "section_id", "page_id", "continuation_index",
        "continuation_role", "section_page_count",
    ):
        _val = getattr(pp, _key, None)
        if _val is not None:
            page_dict[_key] = _val


def _build_page_slot_dicts(
    page_slots: dict[int, list], page_slot: int, client_dir: Path, output_dir: Path,
) -> list[dict]:
    """The per-page `slots[]`: ONLY the `source=="drive"` ResolvedSlots
    (generate/composite slots are represented in `assets[]`, not here).
    Copies each resolved drive photo into the package as a side effect.
    """
    slots = page_slots.get(page_slot, []) if page_slots else []
    return [
        _drive_slot_entry(s, page_slot, client_dir, output_dir)
        for s in slots
        if getattr(s, "source", None) == "drive"
    ]


def _cover_validation_to_dict(cv: CoverValidation) -> dict:
    """Compact view of CoverValidation for the page manifest."""
    return {
        "headline_type": cv.headline_type,
        "headline_size_class": cv.headline_size_class,
        "awareness_level": cv.awareness_level,
        "h_score": cv.h_score,
        "s_score": cv.s_score,
        "b_score": cv.b_score,
        "disqualifications": list(cv.disqualifications),
        "warnings": list(cv.warnings),
        "overall": cv.overall,
    }


def _copy_warning_to_dict(w: CopyWarning) -> dict:
    return {
        "page_slot": w.page_slot,
        "page_type": w.page_type,
        "field_name": w.field_name,
        "rule": w.rule,
        "detail": w.detail,
        "severity": w.severity,
    }


def _build_manifest(
    *,
    record_id: str,
    brand_tokens: dict,
    font_config: FontConfig,
    copy_warnings: list[CopyWarning],
    cover_validation: Optional[CoverValidation],
    asset_plan: AssetPlan,
    layout_plan: LayoutPlan,
    component_rel_paths: dict[int, list[str]],
    report_json: dict,
    output_dir: Path,
    axes: ResolvedAxes,
    axes_provenance: dict,
    structured,
    page_slots: dict[int, list],
    client_dir: Path,
) -> dict:
    """Assemble the master manifest dict (the resolved_package.json v2.0)."""
    pages_manifest: list[dict] = []

    original_data_by_slot: dict[int, dict] = {}
    for p in report_json.get("pages", []):
        if isinstance(p, dict):
            slot = int(p.get("slot", 0))
            original_data_by_slot[slot] = p.get("data") or {}

    # Group assets by page_slot for fast lookup
    assets_by_slot: dict[Optional[int], list[AssetResult]] = {}
    for a in asset_plan.assets:
        assets_by_slot.setdefault(a.page_slot, []).append(a)

    # Typed structured view keyed by slot (data / charts / social_proof).
    structured_by_slot = {
        sp.slot: sp for sp in getattr(structured, "pages", []) if sp.slot is not None
    }

    for pp in layout_plan.pages:
        page_assets = assets_by_slot.get(pp.slot, [])
        sp = structured_by_slot.get(pp.slot)
        # US-603: a CONTINUATION page carries its own SLICED data (pp.data —
        # the section-pagination split). The structured view is the FULL source
        # section; using it on a continuation would duplicate the whole section
        # on every physical page. Single-page sections keep the structured view
        # exactly as before (back-compat).
        is_continuation = (
            pp.continuation_index is not None and pp.section_page_count is not None
        )
        if is_continuation:
            data_block = dict(pp.data)
            charts_block = []
            social_block = None
        elif sp is not None:
            data_block = sp.data.model_dump()
            charts_block = [c.model_dump() for c in sp.charts]
            social_block = sp.social_proof.model_dump() if sp.social_proof else None
        else:
            data_block = original_data_by_slot.get(pp.slot, pp.data)
            charts_block = []
            social_block = None
        # Per-page drive-photo slots (copies resolved files into the package).
        slot_dicts = _build_page_slot_dicts(page_slots, pp.slot, client_dir, output_dir)
        page_dict = {
            "slot": pp.slot,
            "st_type": pp.st_type,
            "css_template": pp.css_template,
            "has_cta": pp.has_cta,
            "page_numbers": pp.page_numbers,
            "data": data_block,
            "charts": charts_block,
            "social_proof": social_block,
            "slots": slot_dicts,
            "assets": [_asset_manifest_entry(a, output_dir) for a in page_assets],
            "components": (
                # US-603: a section's chart/devices live on its RESULT page
                # (the continuation carrying the outcome data); the intro page
                # carries none (its data slice has no chart).
                (component_rel_paths.get(pp.slot, [])
                 if is_continuation and pp.continuation_role == "result"
                 else ([] if is_continuation
                       else component_rel_paths.get(pp.slot, [])))
            ),
            "cover_validation": (
                _cover_validation_to_dict(cover_validation)
                if cover_validation and pp.st_type == "ST-01"
                else None
            ),
        }
        # Per-page layout-variant hint for the renderer (ResolvedPageV2 is
        # extra="allow", so this surfaces verbatim on the package page dict).
        # Only written when Stage 7 resolved one (ST-07A default "fill", or an
        # explicit page hint); absent otherwise so the renderer keeps its own
        # default — back-compat for every other ST type.
        if pp.layout_variant is not None:
            page_dict["layout_variant"] = pp.layout_variant
        # Per-page sheet format: spread variants ("casestudy_hero") are
        # A3-designed → "a3"; everything else stays A4 (renderer default).
        if pp.page_format is not None:
            page_dict["page_format"] = pp.page_format
        # ---- US-602 section/physical-page identity: written ONLY when the
        # plan sets them (a section expanded to multiple physical pages). A
        # single-page section carries none — exactly today's flat package
        # (back-compat; no key, no behaviour change).
        _write_page_identity(page_dict, pp)
        pages_manifest.append(page_dict)

    # Report-level assets (page_slot is None — e.g. background_texture /
    # atmospheric_gradient) and any asset whose slot has no matching page
    # would otherwise be dropped from the manifest. Collect them into a
    # top-level array so NOTHING generated is lost from the package.
    planned_slots = {pp.slot for pp in layout_plan.pages}
    report_assets = [
        _asset_manifest_entry(a, output_dir)
        for a in asset_plan.assets
        if a.page_slot is None or a.page_slot not in planned_slots
    ]

    axes_dump = axes.model_dump()
    brand_axes = {k: axes_dump[k] for k in _BRAND_AXES_KEYS}
    slot_summary = _build_slot_summary(pages_manifest)

    # G10 (determinism): a wall-clock generated_at made identical inputs
    # produce different package bytes. Derive a STABLE pseudo-timestamp from
    # the record_id hash instead, so re-rendering the same input yields
    # identical bytes while the field stays a readable ISO instant. (The
    # timestamp no longer claims wall-clock time; it is a deterministic
    # build identity.)
    _generated_at = _stable_generated_at(record_id)

    return {
        "version": PACKAGE_SCHEMA_VERSION,
        "generated_at": _generated_at,
        "record_id": record_id,
        "brand": dict(brand_tokens),
        "axes": axes_dump,
        "brand_axes": brand_axes,
        "provenance": dict(axes_provenance or {}),
        "fonts": {
            "heading": _font_block(
                font_config.font_heading_name,
                font_config.font_heading_path,
                font_config.source,
                output_dir,
            ),
            "body": _font_block(
                font_config.font_body_name,
                font_config.font_body_path,
                font_config.source,
                output_dir,
            ),
        },
        "pages": pages_manifest,
        "report_assets": report_assets,
        "slot_summary": slot_summary,
        "validation": {
            "copy_warnings": [_copy_warning_to_dict(w) for w in copy_warnings],
            "layout_warnings": list(layout_plan.warnings),
            "cover_overall": cover_validation.overall if cover_validation else None,
            "total_warnings": len(copy_warnings) + len(layout_plan.warnings),
        },
        "asset_summary": {
            "total_required": asset_plan.total_required,
            "total_downloaded": asset_plan.total_downloaded,
            "total_stubbed": asset_plan.total_stubbed,
            "total_client_upload_needed": asset_plan.total_client_upload_needed,
            "total_failed": asset_plan.total_failed,
            "total_generated": asset_plan.total_generated,
        },
        "asset_warnings": list(asset_plan.warnings),
    }


def _build_slot_summary(pages_manifest: list[dict]) -> dict:
    """Counts across ALL pages' drive `slots[]` plus a per-`missing_required`
    named list so QA sees the exact files to add (PRD §7.3 / DNA §7.3)."""
    resolved = missing_required = absent = total = 0
    missing: list[dict] = []
    for page in pages_manifest:
        for slot in page.get("slots", []):
            total += 1
            status = slot.get("status")
            if status == "resolved":
                resolved += 1
            elif status == "missing_required":
                missing_required += 1
                missing.append({
                    "page_slot": page.get("slot"),
                    "slot_id": slot.get("slot_id"),
                    "expected": slot.get("expected"),
                })
            elif status == "absent":
                absent += 1
    return {
        "resolved": resolved,
        "missing_required": missing_required,
        "absent": absent,
        "total": total,
        "missing": missing,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


async def assemble_package(
    *,
    brand_tokens: dict,
    font_config: FontConfig,
    copy_warnings: list[CopyWarning],
    cover_validation: Optional[CoverValidation],
    asset_plan: AssetPlan,
    components: dict[int, list[str]],
    layout_plan: LayoutPlan,
    report_json: dict,
    output_dir: Path,
    axes: ResolvedAxes,
    axes_provenance: dict,
    structured,
    page_slots: dict[int, list],
    client_dir: Path,
) -> ResolvedPackage:
    """Write the resolved package (v2.0) to disk and return a handle.

    `output_dir` is created if missing; this stage is destructive in
    the sense that it overwrites existing `resolved_package.json` and
    rewrites any SVG / font file at its path.

    The manifest is VALIDATED against `ResolvedPackageManifest` before it
    is written — a renderer-relevant typo in a top-level key fails loudly
    here at assembly time, not silently downstream in the renderer.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "assets").mkdir(exist_ok=True)
    (output_dir / "components").mkdir(exist_ok=True)
    (output_dir / "fonts").mkdir(exist_ok=True)

    # Font copies + SVG dump in parallel-ish (both are local I/O; offload
    # the blocking copies to threads so we don't block the event loop).
    await asyncio.gather(
        asyncio.to_thread(_copy_fonts, font_config, output_dir),
        asyncio.to_thread(_write_components_dummy_for_thread,
                          components, output_dir),
    )

    # Now read back the component path map (the thread wrote files,
    # but we need the rel-path mapping for the manifest)
    component_rel_paths = _component_path_map(components)

    record_id = (
        report_json.get("meta", {}).get("report_id", "")
        if isinstance(report_json, dict)
        else ""
    )

    manifest = _build_manifest(
        record_id=record_id,
        brand_tokens=brand_tokens,
        font_config=font_config,
        copy_warnings=copy_warnings,
        cover_validation=cover_validation,
        asset_plan=asset_plan,
        layout_plan=layout_plan,
        component_rel_paths=component_rel_paths,
        report_json=report_json,
        output_dir=output_dir,
        axes=axes,
        axes_provenance=axes_provenance,
        structured=structured,
        page_slots=page_slots,
        client_dir=client_dir,
    )

    # Validate-then-dump: a contract typo now fails loudly here.
    validated = ResolvedPackageManifest.model_validate(manifest)

    # US-602: identity fields are optional — a single-page section must NOT
    # carry null keys (back-compat with the flat package). The model accepts
    # them; the dump strips the None identity keys so only genuinely expanded
    # sections surface section_id/page_id/continuation_*.
    _IDENTITY_KEYS = frozenset({
        "section_id", "page_id", "continuation_index",
        "continuation_role", "section_page_count",
    })

    def _strip_none_identity(page: dict) -> dict:
        return {k: v for k, v in page.items() if k not in _IDENTITY_KEYS or v is not None}

    dumped = validated.model_dump(mode="json")
    dumped["pages"] = [_strip_none_identity(p) for p in dumped.get("pages", [])]

    package_path = output_dir / "resolved_package.json"
    package_path.write_text(
        json.dumps(dumped, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return ResolvedPackage(
        package_path=package_path,
        output_dir=output_dir,
        page_count=len(manifest["pages"]),
        total_warnings=manifest["validation"]["total_warnings"],
        asset_summary=manifest["asset_summary"],
    )


def _write_components_dummy_for_thread(
    components: dict[int, list[str]], output_dir: Path,
) -> None:
    """Wrapper so the `to_thread` call can target this without needing
    the return value (the path mapping is recomputed deterministically
    elsewhere).
    """
    _write_components(components, output_dir)


def _component_path_map(components: dict[int, list[str]]) -> dict[int, list[str]]:
    """Deterministic path mapping: {slot: ['components/{slot}_component_{i}.svg', ...]}.
    Used to populate the manifest; matches the names `_write_components`
    emits.
    """
    return {
        slot: [f"components/{slot}_component_{i}.svg" for i in range(len(svgs))]
        for slot, svgs in components.items()
    }
