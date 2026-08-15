"""Stage 9 -- the inline CONVERGE stage (spec Part 2).

After the renderer produces the deck PDF + page PNGs, this stage runs the
reference-grounded quality loop over the deck: it perceives each page, grades it
against same-type reference pages (vision ON by default), applies the conductor's
in-renderer fixes, and writes a machine-readable ``convergence_report.json`` (the
verification artifact that replaces eyeballing) plus a human-readable
``convergence_report.txt``.

Brand-agnostic: all page/brand data comes from the package. The vision key is
read from .env by the client and is never printed.

NOTE: producing a single MERGED auto-fixed deck PDF (composing each page's chosen
knobs into one render) is deferred until the conductor's knob set is richer
(Phase 3) and a package-merge step exists. Today the per-page convergence drives
the GRADE plus the honest by-owner defect report; the shipped deck PDF is the
renderer's initial render, and the report says what still needs fixing. This is
the anti-faking rule: report what the loop could not fix rather than rig a render.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

from brain import DeckResult, converge_deck as _converge_deck
from run_deck import _owner_of, format_deck_report
from compose import compose_converged_package

# The fix-able subsystems a residual defect can be attributed to (mirrors
# run_deck._OWNERS). "other" catches notes with no parseable owner.
_OWNERS = ("renderer", "preprocessor", "asset_gen", "other")


def build_report(result: DeckResult) -> dict:
    """Pure: turn a ``DeckResult`` into the JSON-serializable ConvergenceReport.

    Per page: the verdict (cleared), best reward, the fixes the loop APPLIED, and
    the residual defects grouped by the owner who must fix them. Deck level: the
    cleared/total counters, the summed reward, and every flag grouped by owner.
    """
    pages: list[dict] = []
    deck_reward = 0.0
    for p in result.pages:
        deck_reward += float(p.best_reward)
        residual: dict[str, list[str]] = {o: [] for o in _OWNERS}
        for flag in p.flags:
            residual[_owner_of(flag)].append(flag)
        pages.append(
            {
                "page_index": p.page_index,
                "st_type": p.st_type,
                "cleared": bool(p.cleared),
                "reward": round(float(p.best_reward), 2),
                "fixes_applied": [
                    {"defect_id": f.defect_id, "knob": f.knob, "proposal": f.proposal}
                    for f in p.fixes_applied
                ],
                "residual_by_owner": residual,
            }
        )

    flags_by_owner: dict[str, list[dict]] = {o: [] for o in _OWNERS}
    for entry in result.deck_flags:
        flags_by_owner[_owner_of(entry["flag"])].append(
            {
                "page_index": entry["page_index"],
                "st_type": entry["st_type"],
                "flag": entry["flag"],
            }
        )

    return {
        "deck_cleared": result.total > 0 and result.cleared_count == result.total,
        "cleared_count": result.cleared_count,
        "total": result.total,
        "deck_reward": round(deck_reward, 2),
        "pages": pages,
        "flags_by_owner": flags_by_owner,
    }


def run_stage(
    package_dir: Path | str,
    out_dir: Path | str,
    *,
    use_vis: bool = True,
    max_iterations: int = 4,
    page_indices: Optional[list[int]] = None,
    vis_client: Any = None,
    converge_deck_fn: Callable = _converge_deck,
    compose: bool = False,
    render_fn: Optional[Callable] = None,
    engine: str = "chromium",
) -> dict:
    """Run Stage 9 and write ``convergence_report.{json,txt}`` into ``out_dir``.

    Args:
        package_dir: the package holding ``resolved_package.json``.
        out_dir: where the report files are written; per-page renders nest under
            ``out_dir/pages/page_{i}``.
        use_vis: when True (default) build a real ``VisionClient`` and grade
            against the references; when False the loop is deterministic-only.
        max_iterations: per-page iteration cap.
        page_indices: explicit page subset (cost control); None runs all pages.
        vis_client: an explicit client (e.g. a fake in tests); overrides use_vis.
        converge_deck_fn: injectable convergence fn (tests pass a fake returning a
            canned ``DeckResult`` so wiring is provable with no render/network).

    Returns:
        The report dict (also written to disk).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if vis_client is None and use_vis:
        from vis_client import VisionClient  # lazy: only on the live path

        vis_client = VisionClient()

    result = converge_deck_fn(
        str(package_dir),
        out_root=out_dir / "pages",
        max_iterations=max_iterations,
        vis_client=vis_client,
        page_indices=page_indices,
    )

    report = build_report(result)

    # Phase 3 (compose-fixes): build a merged package carrying each page's winning
    # per-page knob and RE-RENDER it as the shipped deck, so the loop's fixes ship
    # instead of being discarded. Off by default (no regression to the grade-only
    # path). The deck-wide density axis is left original (see compose docstring).
    if compose:
        if render_fn is None:
            from assembler import render_package as render_fn  # lazy: renderer dep
        # SAFE-SHIP guard: only compose the fix-merged deck when the loop
        # ACTUALLY applied fixes. When the reviewer cannot run (e.g. a
        # credit-limited VIS key -> per-page convergence errors), no page has
        # fixes; shipping the merged package then re-renders from a broken
        # intermediate and produces a corrupt deck (blank/spill sheets).
        # Without fixes the caller ships its own clean original render.
        applied = sum(
            len(getattr(page, "fixes_applied", None) or ())
            for page in result.pages
        )
        if applied > 0:
            merged_dir = compose_converged_package(
                package_dir, result, out_dir / "merged"
            )
            composed_out = out_dir / "composed"
            # Pin the SHIP engine to chromium: render_package's function default is
            # weasyprint (legacy), which silently produces a DIFFERENT deck (addition
            # A). The convergence grades weasyprint DET facts; the ship is chromium.
            render_fn(merged_dir, composed_out, engine=engine)
            composed_pdf = Path(composed_out) / "report.pdf"
            # PAGINATION-SAFE guard: the merged re-render must keep the SAME
            # logical page count as the original package. A density/layout knob
            # can shift a page's rendered metrics enough that Chromium's mixed
            # A3/A4 pagination doubles a sheet (verified 2026-08-15: an ST-06
            # stat-size change + density knob shipped a 22-page deck from a
            # 20-page original). If the composed deck's physical page count
            # exceeds the logical count, it is CORRUPT — ship the caller's
            # original clean render instead.
            try:
                import fitz

                with fitz.open(str(composed_pdf)) as composed_doc:
                    composed_physical = len(composed_doc)
                logical = getattr(result, "total", 0) or len(result.pages)
                if composed_physical > logical:
                    report["composed_pdf"] = None
                    report["compose_rejected"] = (
                        f"composed deck {composed_physical} pages > logical "
                        f"{logical}; shipped the original clean render"
                    )
                else:
                    report["composed_pdf"] = str(composed_pdf)
            except Exception as exc:  # noqa: BLE001 -- never fail the build on the guard
                report["composed_pdf"] = None
                report["compose_rejected"] = f"compose guard error: {exc}"
        else:
            report["composed_pdf"] = None

    (out_dir / "convergence_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "convergence_report.txt").write_text(
        format_deck_report(result), encoding="utf-8"
    )
    return report
