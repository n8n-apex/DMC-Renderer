"""Phase-B proof: converge ONE real page through the closed quality loop.

This runnable script is the Phase-B proof artifact. It drives the live Apex
ST-07A case-study page (page_index 6) through the real ``converge_page`` loop --
the closed cycle of *perceive -> score-against-references -> fix -> re-render*,
guarded by the iteration-cap / monotone-best / oscillation terminators -- and
prints a clear human-readable report of what happened.

The point of the proof is NOT that the page clears (it honestly cannot). The
point is twofold:

  1. The loop *changes the render*: it detects the under-filled-sheet dead-space
     defect and steps the density knob, measurably driving dead_space down across
     iterations. The closed loop is real, not a no-op.

  2. The loop is HONEST about its limits. When it exhausts what it can fix
     in-renderer it does not rig a passing render -- it SHIPS the best version and
     emits explicit FLAGS naming the gaps it cannot close:
       * a missing client photo -> an ``asset_gen`` gap (needs an asset supplied),
       * a residual dead-space defect the density knob could not resolve -> a
         ``renderer`` capability gap (the renderer needs a fill-the-sheet
         case-study layout).
     These FLAGS are the system's own capability/asset-gap outputs -- the machine
     telling us what it cannot fix -- not human guesses.

The module exposes three pieces so the proof is testable and reusable:

  * ``run_proof(...)``     -- runs the loop and returns the ``PageResult``.
  * ``format_report(...)`` -- renders a ``PageResult`` to a human-readable string.
  * ``main(...)``          -- CLI entry: run the proof, print the report.

``package_dir`` / ``page_index`` are overridable (function args or argv) so the
proof generalizes to other pages later; they default to the real Apex case study.
Nothing here is brand-specific: all brand data comes from the package.

Run it:

    cd research/v7-renderer && source .venv/bin/activate && cd ../quality_loop && \
        PYTHONPATH=...:... python run_one_page.py
    # optional overrides:
    python run_one_page.py <package_dir> <page_index> [max_iterations]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from brain import PageResult, converge_page
from references import retrieve_references

# --------------------------------------------------------------------------- #
# Defaults: the real Apex ST-07A case study (the Phase-B proof target).
# --------------------------------------------------------------------------- #
RENDERER_ROOT = Path("/Users/utkarsh/Projects/richard/research/v7-renderer")
APEX_PKG = RENDERER_ROOT / "fixtures" / "apex"
CASE_STUDY_INDEX = 6  # ST-07A -- the under-filled case-study page (N08 fires).

# Default output root for proof renders (created on demand).
OUTPUT_ROOT = Path(__file__).resolve().parent / "output"


def run_proof(
    package_dir: Path | str = APEX_PKG,
    page_index: int = CASE_STUDY_INDEX,
    *,
    max_iterations: int = 4,
    out_root: Path | str | None = None,
    use_vis: bool = False,
    vis_client: object | None = None,
) -> PageResult:
    """Run the closed loop on one page and return its ``PageResult``.

    Calls the real ``converge_page`` with all real defaults (real perception,
    scoring, conductor, references and renderer). The brain copies the package
    before turning any knob, so the source ``package_dir`` is never mutated.

    Args:
        package_dir: path to the package holding ``resolved_package.json``
            (defaults to the real Apex case-study package).
        page_index: 0-based index of the target page (defaults to the ST-07A
            case-study page).
        max_iterations: the iteration-cap guard bound for the loop.
        out_root: directory each iteration renders into (an ``iter_{n}`` subdir
            per iteration). Defaults to a fresh dir under ``./output/``.
        use_vis: when True, construct a real ``VisionClient()`` and pass it to
            the brain so each iteration grounds its VIS rows against the
            retrieved reference pages via ONE real (cached) vision call. Default
            False so the offline / no-key path keeps working with no network.
        vis_client: an explicit vision client to use instead of building one
            (e.g. a ``FakeVisionClient`` in tests). Takes precedence over
            ``use_vis``; when given, ``use_vis`` is ignored.

    Returns:
        The ``PageResult`` describing the convergence: the iteration trajectory,
        fixes applied, ship state, best artifacts, and the honest capability/
        asset-gap flags.
    """
    if out_root is None:
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        out_root = OUTPUT_ROOT / f"page_{page_index}"
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    if vis_client is None and use_vis:
        # Lazy import: only pull in the real client (and its httpx/PIL deps) when
        # the live vision path is actually requested.
        from vis_client import VisionClient

        vis_client = VisionClient()

    return converge_page(
        str(package_dir),
        page_index,
        max_iterations=max_iterations,
        out_root=out_root,
        vis_client=vis_client,
    )


def _page_axes(result: PageResult, package_dir: Path | str = APEX_PKG) -> dict:
    """Reconstruct the axes that anchored the BEST iteration's judgment.

    The brain starts from the package's ``axes`` and only steps ``density`` up
    the ladder; every other axis is held constant. So the axes the reference
    retrieval saw for the best iteration are the package axes with ``density``
    overridden by that iteration's recorded value. This mirrors exactly what the
    brain passed to ``retrieve_references`` for that iteration, so the report's
    "which references anchored this" line matches what actually grounded VIS.
    """
    try:
        pkg = json.loads(
            (Path(package_dir) / "resolved_package.json").read_text()
        )
        axes = dict(pkg.get("axes", {}))
    except (OSError, ValueError):
        axes = {}
    best_it = next(
        (it for it in result.iterations if it.n == result.best_iteration), None
    )
    if best_it is not None and best_it.density is not None:
        axes["density"] = best_it.density
    return axes


def format_report(result: PageResult) -> str:
    """Render a ``PageResult`` to a human-readable proof report (a string).

    Sections, in order:
      * header  -- page index + st_type + cleared verdict;
      * trajectory table -- n | density | dead_space | reward | hard_fail |
        fired_defects | fix_applied;
      * fixes applied -- the knob steps the conductor made;
      * best -- best iteration + best_reward + shipped-best verdict;
      * "CAPABILITY / ASSET GAPS SURFACED BY THE SYSTEM" -- the flags, the whole
        point: what the loop cannot fix in-renderer.

    Args:
        result: the convergence outcome to format.

    Returns:
        The full report as a single string (newline-separated).
    """
    lines: list[str] = []
    bar = "=" * 78
    rule = "-" * 78

    # --- Header. ---------------------------------------------------------- #
    lines.append(bar)
    lines.append("PHASE-B PROOF -- closed quality loop converging ONE page")
    lines.append(bar)
    verdict = "CLEARED" if result.cleared else "NOT CLEARED (shipped best + flags)"
    lines.append(f"page_index : {result.page_index}")
    lines.append(f"st_type    : {result.st_type}")
    lines.append(f"verdict    : {verdict}")
    lines.append("")

    # --- Trajectory table. ------------------------------------------------ #
    lines.append("PER-ITERATION TRAJECTORY")
    lines.append(rule)
    header = (
        f"{'n':>2} | {'density':<9} | {'dead_space':>10} | {'reward':>7} | "
        f"{'hard_fail':>9} | {'fired_defects':<22} | fix_applied"
    )
    lines.append(header)
    lines.append(rule)
    for it in result.iterations:
        fired = ",".join(it.fired_defects) if it.fired_defects else "-"
        fix = it.fix_applied if it.fix_applied else "-"
        density = it.density if it.density is not None else "-"
        lines.append(
            f"{it.n:>2} | {density:<9} | {it.dead_space:>10.4f} | "
            f"{it.reward:>7.1f} | {str(it.hard_fail):>9} | {fired:<22} | {fix}"
        )
    lines.append(rule)
    lines.append("")

    # --- Fixes applied (knob steps). -------------------------------------- #
    lines.append("FIXES APPLIED (knob steps)")
    lines.append(rule)
    if result.fixes_applied:
        for i, fix in enumerate(result.fixes_applied, start=1):
            knob = getattr(fix, "knob", None) or "-"
            proposal = getattr(fix, "proposal", str(fix))
            defect_id = getattr(fix, "defect_id", "?")
            lines.append(f"{i}. [{defect_id}] knob={knob}: {proposal}")
    else:
        lines.append("(none)")
    lines.append("")

    # --- Best / ship verdict. --------------------------------------------- #
    lines.append("BEST STATE")
    lines.append(rule)
    lines.append(f"best_iteration : {result.best_iteration}")
    lines.append(f"best_reward    : {result.best_reward:.1f}")
    lines.append(f"shipped_best   : {result.shipped_best}")
    if result.best_artifacts:
        lines.append(f"best pdf       : {result.best_artifacts.get('pdf')}")
        lines.append(f"best png       : {result.best_artifacts.get('png')}")
    lines.append("")

    # --- Reference-grounded vision scores (the live VIS adjudication). ----- #
    lines.append("REFERENCE-GROUNDED VISION SCORES")
    lines.append(rule)
    # Which of Richard's expert reference pages anchored the judgment for this
    # page type -- the brand-agnostic anchor the page was compared against.
    axes = _page_axes(result)
    try:
        refs = retrieve_references(result.st_type, axes, k=3)
    except Exception:  # noqa: BLE001 -- never let report formatting hard-fail
        refs = []
    lines.append(f"anchored against (st_type={result.st_type}):")
    if refs:
        for r in refs:
            deck = r.get("deck", "?")
            page_no = r.get("page_no", "?")
            lines.append(f"  - {deck} p{page_no}")
    else:
        lines.append(
            f"  (no reference pages matched st_type={result.st_type})"
        )
    lines.append("")

    # The VIS scores from the BEST iteration: row_id | score(0-3) | rationale.
    best_it = next(
        (it for it in result.iterations if it.n == result.best_iteration), None
    )
    vis_results = best_it.vis_results if best_it is not None else None
    lines.append(f"VIS scores (best iteration n={result.best_iteration}):")
    if vis_results:
        for row_id in sorted(vis_results):
            entry = vis_results[row_id] or {}
            score = entry.get("score", "?")
            rationale = entry.get("rationale", "") or ""
            lines.append(f"  {row_id} | {score} | {rationale}")
    else:
        lines.append(
            "  (no VIS results -- run with --vis to ground VIS rows against "
            "the reference library via a live vision call)"
        )
    lines.append("")

    # --- Flags: the whole point. ------------------------------------------ #
    lines.append("CAPABILITY / ASSET GAPS SURFACED BY THE SYSTEM")
    lines.append(rule)
    lines.append(
        "(the loop's own outputs naming what it CANNOT fix in-renderer -- not "
        "human guesses)"
    )
    if result.flags:
        for flag in result.flags:
            lines.append(f"  - {flag}")
    else:
        lines.append("  (none -- the page cleared with no residual gaps)")
    lines.append(bar)

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: run the proof on the given (or default) page and print it.

    Usage:
        python run_one_page.py [--vis] [package_dir] [page_index] [max_iterations]

    ``--vis`` enables the real reference-grounded vision client (ONE live,
    cached vision call per iteration). It is OFF by default so the offline /
    no-key path runs with no network.

    Defaults to the real Apex ST-07A case study. Returns a process exit code
    (always 0 -- a non-cleared honest ship is a successful proof run, not an
    error; the FLAGS carry the verdict).
    """
    argv = list(sys.argv[1:] if argv is None else argv)

    # Pull the --vis flag out (position-independent); the rest are positional.
    use_vis = "--vis" in argv
    positional = [a for a in argv if a != "--vis"]

    package_dir: Path | str = APEX_PKG
    page_index = CASE_STUDY_INDEX
    max_iterations = 4

    if len(positional) >= 1:
        package_dir = positional[0]
    if len(positional) >= 2:
        page_index = int(positional[1])
    if len(positional) >= 3:
        max_iterations = int(positional[2])

    result = run_proof(
        package_dir,
        page_index,
        max_iterations=max_iterations,
        use_vis=use_vis,
    )
    print(format_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
