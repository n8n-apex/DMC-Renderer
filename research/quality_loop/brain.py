"""Brain -- the per-page convergence loop + its three guards (spec §5.2).

The brain is the controller that closes the quality loop for ONE page. It wires
the existing pieces -- perception (``perceive``), analysis (``score`` / ``cleared``),
the conductor (``propose_fix`` / ``route``) and the reference library
(``retrieve_references``) -- into an iterative perceive -> score -> fix -> re-render
cycle, and it decides when to STOP and what to SHIP.

It deliberately fixes NOTHING itself: the conductor is the only mutator. The
brain's job is convergence control, and that control is defined by three guards
(spec §5.2):

  1. ITERATION-CAP guard
     The loop never runs past ``max_iterations``. If it hits the cap without
     clearing, it stops and ships the best state seen.

  2. MONOTONE-BEST guard
     The loop tracks the BEST iteration and never ships a state worse than one it
     already rendered. A hard-failed state can never beat a non-hard-failed one;
     among equal hard-fail status the higher reward wins. This is the anti-
     regression rule: stepping a knob that happens to make a page worse cannot
     cause the loop to ship that worse page.

  3. OSCILLATION guard
     If the set of fired defect ids is unchanged across the last two iterations
     AND reward did not improve, the loop is making no progress -- re-applying the
     same fix will not change the outcome -- so it stops and flags a
     no-progress / oscillation gap. Combined with the conductor's ladder-
     exhaustion signal, this guarantees clean termination.

On any non-cleared stop the brain ships the best state and emits honest FLAGS:
asset_gen / preprocessor defects (out-of-renderer; e.g. N01 missing client photo)
and residual renderer defects that survived knob exhaustion (e.g. N08 dead space
the density knob could not resolve -> a renderer capability gap). This is the
anti-faking surface: the loop reports what it could not fix rather than rigging a
render that papers over the gap.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from analysis import PageScore, cleared, score as _score
from conductor import (
    DENSITY_LADDER,
    Fix,
    RouteResult,
    propose_fix as _propose_fix,
    route as _route,
)
from perception import PageFacts, perceive as _perceive
from references import retrieve_references as _retrieve_references
from rubric import RUBRIC

# The two non-renderer knob classes -- their defects are surfaced as flags, never
# fixed in-renderer (a missing photo must be supplied; a placeholder leak is a
# preprocessor copy-fit failure). See conductor module docstring.
_FLAG_KNOB_CLASSES = {"asset_gen", "preprocessor"}

# The quality_loop package root (the dir holding references/). Reference rows
# carry png_paths relative to this root; we resolve them against it for the
# vision client. Resolved at import time, robust to the caller's cwd.
_QL_ROOT = Path(__file__).resolve().parent

# Default top-k references used when grounding VIS rows -- mirrors the
# ``retrieve_references`` default so we pass the same set the scorer matched.
_RETRIEVE_K = 3


def _step_density(current: Optional[str]) -> str:
    """Next value UP the density ladder, clamped at the top.

    Used to advance ``current_axes["density"]`` after the conductor applies a
    density fix. The conductor's ``RouteResult.artifacts`` reports the re-rendered
    pdf/png/package_dir but not the stepped axis value, so the brain mirrors the
    one-rung step here (an unknown/missing current value steps from the bottom).
    """
    try:
        idx = DENSITY_LADDER.index(current)  # type: ignore[arg-type]
    except ValueError:
        idx = -1
    return DENSITY_LADDER[min(idx + 1, len(DENSITY_LADDER) - 1)]


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
@dataclass
class Iteration:
    """A single trip through the loop: the state observed + the fix that got here.

    ``fix_applied`` is the proposal string of the fix that was applied to REACH
    this state (None for iteration 0, the initial render).
    """

    n: int
    density: str
    dead_space: float
    reward: float
    hard_fail: bool
    fired_defects: list[str]
    fix_applied: Optional[str]
    # The reference-grounded vision scores used to adjudicate VIS rows this
    # iteration ({row_id: {"score": int, "rationale": str}}), or None when no
    # vision client was wired. Lightweight trace for the proof to print.
    vis_results: Optional[dict] = None


@dataclass
class PageResult:
    """The outcome of converging one page.

    ``shipped_best`` is True whenever the loop ships a state (always true here:
    either it cleared and ships the cleared state, or it could not clear and ships
    the best-scored state). ``best_artifacts`` is the render artifacts dict of the
    best iteration (None only for iteration 0 if the initial render produced no
    artifacts dict -- see ``converge_page``).
    """

    page_index: int
    st_type: str
    cleared: bool
    best_reward: float
    best_iteration: int
    iterations: list[Iteration]
    fixes_applied: list[Fix]
    flags: list[str]
    shipped_best: bool
    best_artifacts: Optional[dict[str, Any]]


# --------------------------------------------------------------------------- #
# Internal best-tracking
# --------------------------------------------------------------------------- #
@dataclass
class _Best:
    """Bookkeeping for the MONOTONE-BEST guard (spec §5.2, guard 2)."""

    n: int = -1
    reward: float = float("-inf")
    hard_fail: bool = True
    score: Optional[PageScore] = None
    artifacts: Optional[dict[str, Any]] = None

    def consider(self, n: int, s: PageScore, artifacts: Optional[dict]) -> None:
        """Update best iff this state is strictly better.

        Ordering (best wins): a non-hard-failed state always beats a hard-failed
        one; among equal hard-fail status, the higher reward wins. Ties keep the
        earlier iteration (we only replace on a strict improvement).
        """
        if self.n < 0:
            self._set(n, s, artifacts)
            return
        # A clean state beats a hard-failed incumbent.
        if self.hard_fail and not s.hard_fail:
            self._set(n, s, artifacts)
            return
        # A hard-failed candidate never beats a clean incumbent.
        if not self.hard_fail and s.hard_fail:
            return
        # Equal hard-fail status -> higher reward wins (strict improvement only).
        if s.reward > self.reward:
            self._set(n, s, artifacts)

    def _set(self, n: int, s: PageScore, artifacts: Optional[dict]) -> None:
        self.n = n
        self.reward = s.reward
        self.hard_fail = s.hard_fail
        self.score = s
        self.artifacts = artifacts


# --------------------------------------------------------------------------- #
# Flag construction
# --------------------------------------------------------------------------- #
def _build_flags(
    best_score: Optional[PageScore],
    exhausted_fix: Optional[Fix],
    oscillation: bool,
) -> list[str]:
    """Build the honest capability/asset-gap flags for a non-cleared stop.

    (a) Every best-score defect in an out-of-renderer knob class (asset_gen /
        preprocessor) -> "{id} {detail} -> {knob_class}".
    (b) A residual renderer defect that survived knob exhaustion -> a renderer
        capability-gap flag. (e.g. N08 still firing after density exhausted.)
    (c) A no-progress / oscillation note when the oscillation guard tripped.
    (d) A note of skipped-row counts for traceability.
    """
    flags: list[str] = []
    if best_score is not None:
        # (a) out-of-renderer asset/preprocessor gaps.
        for d in best_score.defects:
            if d.knob_class in _FLAG_KNOB_CLASSES:
                flags.append(f"{d.id} {d.detail} -> {d.knob_class}")

        # (b) residual renderer defect after the knob ladder exhausted.
        if exhausted_fix is not None:
            knob = exhausted_fix.knob or "knob"
            flags.append(
                f"{exhausted_fix.defect_id} residual after {knob} exhausted "
                f"-> renderer capability gap"
            )

        # (d) skipped-row counts (traceability; never silently dropped).
        if best_score.skipped_vis or best_score.skipped_fact:
            flags.append(
                f"skipped rows: needs_vision={len(best_score.skipped_vis)} "
                f"needs_fact={len(best_score.skipped_fact)}"
            )

    # (c) oscillation / no-progress.
    if oscillation:
        flags.append(
            "no-progress / oscillation: fired-defect set unchanged with no "
            "reward improvement -> stopped re-applying an ineffective fix"
        )
    return flags


# --------------------------------------------------------------------------- #
# The loop
# --------------------------------------------------------------------------- #
def converge_page(
    package_dir: Path | str,
    page_index: int,
    *,
    rubric: list = RUBRIC,
    max_iterations: int = 4,
    out_root: Path | str,
    perceive_fn: Callable = _perceive,
    score_fn: Callable = _score,
    propose_fix_fn: Callable = _propose_fix,
    route_fn: Callable = _route,
    render_fn: Callable = None,
    retrieve_fn: Callable = _retrieve_references,
    vis_client: Any = None,
) -> PageResult:
    """Converge one page: perceive -> score -> fix -> re-render, guarded (spec §5.2).

    Dependencies are injected as keyword args (defaulting to the real functions)
    so the three guard tests can pass fast, deterministic fakes. ``render_fn``
    defaults to ``assembler.render_package`` (imported lazily so the pure-logic
    guard tests never pull in WeasyPrint/PyMuPDF).

    Algorithm (spec §5.2):
      0. Load the package JSON -> page data, st_type, axes, brand.
      1. Initial render into ``out_root/iter_0`` (page png = report-p{N+1}.png).
      2. Loop up to ``max_iterations``: perceive, retrieve refs, score, record an
         Iteration, update the MONOTONE-BEST tracker, then:
           - cleared(score)        -> STOP success.
           - propose_fix is None   -> STOP (no renderer-fixable defect; flag).
           - fix.exhausted         -> STOP (ladder exhausted; capability-gap flag).
           - route != "applied"    -> STOP (flagged/exhausted; flag).
           - route == "applied"    -> advance package/axes/artifacts, loop.
         OSCILLATION guard: if the fired-defect set is unchanged across the last
         two iterations AND reward did not improve, STOP (no-progress flag).
      3. ITERATION-CAP guard: hitting ``max_iterations`` without clearing STOPs
         and ships best.
      On any non-cleared stop: ship best + build honest flags.

    Args:
        package_dir: path to the package (holds resolved_package.json).
        page_index: 0-based index of the target page.
        rubric: the scoring rubric (data; defaults to RUBRIC).
        max_iterations: the iteration-cap guard bound.
        out_root: root dir; each iteration renders into its own ``iter_{n}`` subdir.
        perceive_fn/score_fn/propose_fix_fn/route_fn/render_fn/retrieve_fn:
            injectable dependencies (default to the real functions).

    Returns:
        A ``PageResult`` with the iteration trajectory, fixes applied, ship state,
        best artifacts, and honest flags.
    """
    if render_fn is None:
        # Lazy import keeps the guard tests free of WeasyPrint/PyMuPDF.
        from assembler import render_package as render_fn  # type: ignore

    package_dir = Path(package_dir)
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    # --- 0. Load the package. --------------------------------------------- #
    pkg = json.loads((package_dir / "resolved_package.json").read_text())
    page_data = pkg["pages"][page_index]
    st_type = str(page_data.get("st_type", ""))
    brand = pkg.get("brand", {})
    current_axes = dict(pkg.get("axes", {}))
    current_package_dir = package_dir
    # Per-page layout variant -- the conductor's case-study layout knob steps
    # this "standard" -> "fill". Read the page's current value (default standard).
    current_layout_variant = str(page_data.get("layout_variant", "standard"))

    png_name = f"report-p{page_index + 1}.png"

    # --- 1. Initial render (iteration 0). --------------------------------- #
    iter0_dir = out_root / "iter_0"
    iter0_dir.mkdir(parents=True, exist_ok=True)
    render_fn(current_package_dir, iter0_dir)
    current_pdf = iter0_dir / "report.pdf"
    current_png = iter0_dir / png_name
    # Iteration 0 artifacts mirror the route "applied" artifacts shape.
    current_artifacts: dict[str, Any] = {
        "pdf": current_pdf,
        "png": current_png,
        "package_dir": current_package_dir,
    }

    iterations: list[Iteration] = []
    fixes_applied: list[Fix] = []
    best = _Best()
    did_clear = False
    exhausted_fix: Optional[Fix] = None
    oscillation = False
    pending_fix_proposal: Optional[str] = None

    # --- 2/3. The guarded loop. ------------------------------------------- #
    for n in range(max_iterations):
        # a. perceive
        facts = perceive_fn(
            current_pdf, page_index, current_png, page_data, current_axes, brand
        )
        # b. retrieve refs + (optionally) ground VIS rows via the vision client.
        refs = retrieve_fn(st_type, current_axes)
        if vis_client is not None:
            # VIS rows are those whose detect class mentions "VIS".
            vis_row_ids = [r.id for r in rubric if "VIS" in r.detect]
            # Resolve the matched refs' png_paths (relative to the quality_loop
            # package root) to absolute paths; take up to k (retrieve default).
            ref_pngs = [
                str((_QL_ROOT / r["png_path"]).resolve())
                for r in refs[:_RETRIEVE_K]
                if r.get("png_path")
            ]
            vis_results = vis_client.score_page(
                str(current_png), ref_pngs, vis_row_ids
            )
            s = score_fn(facts, refs, rubric, vis_results=vis_results)
        else:
            # No vision client -> preserve today's exact call shape (no kwarg).
            vis_results = None
            s = score_fn(facts, refs, rubric)

        fired = sorted(d.id for d in s.defects)

        # c. record the iteration (fix_applied is the fix that REACHED this state)
        iterations.append(Iteration(
            n=n,
            density=current_axes.get("density"),
            dead_space=float(getattr(facts, "dead_space_fraction", 0.0)),
            reward=float(s.reward),
            hard_fail=bool(s.hard_fail),
            fired_defects=fired,
            fix_applied=pending_fix_proposal,
            vis_results=vis_results,
        ))

        # d. MONOTONE-BEST guard: never let best regress.
        best.consider(n, s, current_artifacts)

        # e. cleared? -> success stop.
        if cleared(s):
            did_clear = True
            break

        # g. OSCILLATION guard: unchanged fired set + no reward improvement over
        #    the previous iteration -> no progress, stop. (Checked once we have a
        #    previous iteration to compare against.)
        if len(iterations) >= 2:
            prev = iterations[-2]
            cur = iterations[-1]
            if cur.fired_defects == prev.fired_defects and cur.reward <= prev.reward:
                oscillation = True
                break

        # f. propose a fix for the top renderer-fixable defect. Pass the page's
        #    st_type + current layout variant so the conductor can prefer the
        #    case-study layout knob for N08 on ST-07A pages. The default
        #    propose_fix accepts these keyword-only kwargs; injected fakes in
        #    tests accept **kwargs and ignore them.
        fix = propose_fix_fn(
            s, current_axes,
            st_type=st_type,
            current_layout_variant=current_layout_variant,
        )
        if fix is None:
            # No renderer-fixable defect -> nothing more to do; ship best + flag.
            break
        if fix.exhausted:
            # Knob ladder exhausted -> residual capability gap.
            exhausted_fix = fix
            break

        rr = route_fn(fix, current_package_dir, current_axes,
                      out_root / f"iter_{n + 1}", page_index)
        if rr.status != "applied":
            # flagged / exhausted at the router -> stop.
            if rr.status == "exhausted":
                exhausted_fix = fix
            break

        # Applied -> advance state for the next iteration.
        art = rr.artifacts or {}
        current_package_dir = Path(art["package_dir"])
        # Advance the axis the applied fix actually turned, threading the patched
        # package forward so the next iteration perceives the changed render.
        if "new_layout_variant" in art:
            # Layout knob: the case study flipped standard->fill. Density is held.
            current_layout_variant = art["new_layout_variant"]
        elif fix.knob == "density":
            # Density knob: prefer the reported stepped value, else mirror the
            # one-rung ladder step the conductor made.
            current_axes["density"] = art.get(
                "new_density", _step_density(current_axes.get("density"))
            )
        current_pdf = Path(art["pdf"])
        current_png = Path(art["png"])
        current_artifacts = {
            "pdf": current_pdf,
            "png": current_png,
            "package_dir": current_package_dir,
        }
        fixes_applied.append(fix)
        pending_fix_proposal = fix.proposal

    # --- Build the result. ------------------------------------------------ #
    if did_clear:
        flags: list[str] = []
    else:
        # If the best renderer defect is still firing (N08) and we did not get an
        # explicit exhausted_fix (e.g. we stopped on the iteration cap while the
        # ladder was still nominally moving), synthesize the capability-gap flag
        # from the best score's residual renderer defects.
        if exhausted_fix is None and best.score is not None:
            residual_renderer = [
                d for d in best.score.defects
                if d.knob_class == "renderer"
            ]
            if residual_renderer:
                top = residual_renderer[0]
                exhausted_fix = Fix(
                    defect_id=top.id, knob_class="renderer", knob="density",
                    target=top.target,
                    proposal="residual renderer defect after iteration cap",
                    exhausted=True,
                )
        flags = _build_flags(best.score, exhausted_fix, oscillation)

    return PageResult(
        page_index=page_index,
        st_type=st_type,
        cleared=did_clear,
        best_reward=best.reward if best.n >= 0 else 0.0,
        best_iteration=best.n,
        iterations=iterations,
        fixes_applied=fixes_applied,
        flags=flags,
        shipped_best=True,
        best_artifacts=best.artifacts,
    )


# --------------------------------------------------------------------------- #
# Deck-level convergence: run the loop across the WHOLE deck + aggregate.
# --------------------------------------------------------------------------- #
@dataclass
class DeckResult:
    """The outcome of converging an entire deck.

    ``pages`` is one ``PageResult`` per adjudicated page index (in run order).
    ``deck_flags`` is the aggregated, de-duplicated flag ledger: one entry per
    distinct ``(page_index, flag)`` pair, each tagged with the page's ``st_type``
    (so a deck-level report can group what every owner must fix). ``cleared_count``
    / ``total`` are convenience counters over ``pages``.
    """

    pages: list[PageResult]
    deck_flags: list[dict[str, Any]]
    cleared_count: int
    total: int


def converge_deck(
    package_dir: Path | str,
    *,
    out_root: Path | str,
    rubric: list = RUBRIC,
    max_iterations: int = 4,
    vis_client: Any = None,
    page_indices: Optional[list[int]] = None,
    converge_page_fn: Callable = converge_page,
) -> DeckResult:
    """Converge every page of a deck and aggregate a deck-level flag ledger.

    Runs the proven per-page loop (``converge_page_fn``, default the real
    ``converge_page``) across all pages -- the system adjudicating the whole deck
    rather than a human spraying per-page knobs -- then aggregates each page's
    honest flags into a single de-duplicated, owner-attributable ledger.

    Each page renders into its OWN ``out_root/page_{i}`` subdir (``converge_page``
    nests further by iteration), so per-page artifacts never collide.

    Robustness: a single page's convergence raising must NOT kill the deck. We
    catch any exception from ``converge_page_fn`` and capture it as a non-cleared
    error ``PageResult`` carrying an explicit error flag (so the failure is loud
    in both the page record and the aggregated deck_flags), then continue.

    Args:
        package_dir: path to the package holding ``resolved_package.json`` (used
            to read the page count / per-page st_type).
        out_root: deck-level output root; page ``i`` renders into
            ``out_root/page_{i}``.
        rubric: the scoring rubric (data; passed through to each page).
        max_iterations: the per-page iteration-cap guard bound.
        vis_client: optional vision client threaded into each page's loop.
        page_indices: explicit page indices to run; ``None`` runs ALL pages
            (0..N-1) read from the package.
        converge_page_fn: injectable per-page convergence function (default the
            real ``converge_page``) so tests can pass a fast fake.

    Returns:
        A ``DeckResult`` with one PageResult per page, the aggregated deck_flags,
        and the cleared/total counters.
    """
    package_dir = Path(package_dir)
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    pkg = json.loads((package_dir / "resolved_package.json").read_text())
    pages_meta = pkg.get("pages", [])
    if page_indices is None:
        indices = list(range(len(pages_meta)))
    else:
        indices = list(page_indices)

    pages: list[PageResult] = []
    for i in indices:
        page_out = out_root / f"page_{i}"
        st_type = ""
        if 0 <= i < len(pages_meta):
            st_type = str(pages_meta[i].get("st_type", ""))
        try:
            res = converge_page_fn(
                package_dir,
                i,
                rubric=rubric,
                max_iterations=max_iterations,
                out_root=page_out,
                vis_client=vis_client,
            )
        except Exception as exc:  # noqa: BLE001 -- one bad page must not kill the deck
            # Capture the failure as a non-cleared error PageResult. The error is
            # surfaced as a flag (loud, not silent) and aggregated into deck_flags.
            res = PageResult(
                page_index=i,
                st_type=st_type,
                cleared=False,
                best_reward=0.0,
                best_iteration=-1,
                iterations=[],
                fixes_applied=[],
                flags=[f"convergence error: {type(exc).__name__}: {exc} -> error"],
                shipped_best=False,
                best_artifacts=None,
            )
        pages.append(res)

    # Aggregate flags: one entry per distinct (page_index, flag), tagged st_type.
    deck_flags: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for p in pages:
        for flag in p.flags:
            key = (p.page_index, flag)
            if key in seen:
                continue
            seen.add(key)
            deck_flags.append(
                {"page_index": p.page_index, "st_type": p.st_type, "flag": flag}
            )

    return DeckResult(
        pages=pages,
        deck_flags=deck_flags,
        cleared_count=sum(1 for p in pages if p.cleared),
        total=len(pages),
    )
