"""Conductor -- the perceive->analyze->fix bridge (spec §5).

The conductor is the ONLY component permitted to mutate render inputs. Given a
``PageScore`` (from ``analysis.score``, scored against the spec §6 rubric) it
turns the top *fixable* defect into a ``Fix`` and routes it:

  * RENDERER-class fixes are APPLIED -- the conductor patches a COPY of the
    package (never the original fixture), steps the relevant render axis, and
    re-renders via ``assembler.render_package``. This is the live repair path.
  * ASSET_GEN / PREPROCESSOR fixes are FLAGGED -- they are out-of-renderer
    (a missing client photo must be supplied/generated; a placeholder leak is a
    preprocessor copy-fit failure). The conductor does NOT touch code for these;
    it surfaces them honestly as explicit capability/asset gaps. This is the
    anti-faking rule: the system reports what it cannot fix rather than rigging
    a render that papers over the gap.

Knob registry (constrained + brand-agnostic -- the conductor only reads defect
metadata and manipulates an *axis value*, never client hex / names / fonts):

  * ``DENSITY_LADDER`` -- the density axis values low->high. Stepping UP
    increases leading + spacing, spreading content taller to fill the sheet,
    which reduces N08 dead whitespace (empirically validated on the real Apex
    ST-07A page: dead_space_fraction compact 0.3943 > balanced 0.3860 >
    spacious 0.3812, a strict monotone decrease).
  * ``DEFECT_KNOBS`` -- maps a renderer defect id to the knob that addresses it.
    For this phase the single live knob is N08 -> density. More knobs (e.g. for
    N09 missing-header furniture, N05 contrast) are added here as the renderer
    grows the corresponding capability; an N-id absent from this map is simply
    not yet renderer-fixable and ``propose_fix`` will skip it.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# --------------------------------------------------------------------------- #
# Knob registry (data; constrained + brand-agnostic)
# --------------------------------------------------------------------------- #
DENSITY_LADDER: list[str] = ["compact", "balanced", "spacious"]

# The case-study layout-variant axis values, low->high fill. Stepping from
# "standard" to "fill" swaps the ST-07A case study to a full-height dark
# authority panel that FILLS the sheet, collapsing N08 dead space far more
# effectively than the density knob (empirically: page 6 dead_space_fraction
# 0.3943 standard -> 0.1116 fill, i.e. below the N08 0.30 threshold). The
# variant is held on the page (``pkg["pages"][i]["layout_variant"]``), not on a
# global axis, because it is a per-page render choice; "standard" is the default.
LAYOUT_LADDER: list[str] = ["standard", "fill"]

# The st_types that have a renderer "fill" layout variant the loop may select
# for N08 dead space. Brand-agnostic STRUCTURAL type ids (NOT client literals).
# Each of these patterns implements layout_variant="fill" in the renderer
# (st_07a/st_07b/st_22/st_fazit) — a full-fill composition grounded in DNA §C3.
# ST-31 is intentionally NOT here: its under-fill is an asset+content gap
# (no scene photo, no breather phrase), not a renderer layout gap, so the loop
# must flag it (asset_gen/content), never fabricate a fill.
# ST-07B is intentionally EXCLUDED: its "fill" variant is a large dark insight
# panel that the unified emptiness metric (N08, white-OR-dark voids) correctly
# scores as HOLLOW (~0.29) — it's a content-less dark void, not a real fix. So
# the loop must NOT apply it; ST-07B is flagged as needing real CONTENT (a chart,
# diagram, comparison, or device — Step B), not a dark panel. ST-07A/22/FAZIT
# fills genuinely clear the unified metric (~0.067/0.10/0.067 — packed), so they
# stay. This is the anti-gaming correction.
FILL_CAPABLE_ST_TYPES: frozenset[str] = frozenset(
    {"ST-07A", "ST-22", "ST-FAZIT"}
)
# Back-compat alias (some callers/tests referenced the original single id).
CASE_STUDY_ST_TYPE: str = "ST-07A"

# Renderer defect id -> the knob that addresses it. N08 -> density is the one
# live knob this phase; extend as renderer capabilities grow (see module doc).
# N08 on an ST-07A case study additionally has a more effective LAYOUT knob
# (see ``propose_fix``); the density knob remains the fallback once layout is
# already at "fill".
DEFECT_KNOBS: dict[str, str] = {"N08": "density"}


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
@dataclass
class Fix:
    """A proposed repair for one defect.

    ``knob`` is the render axis to turn (None for non-renderer fixes that have
    no in-renderer knob). ``exhausted`` is True when the knob has no remaining
    headroom (e.g. density already at the top of its ladder) -- the loop then
    flags a residual capability gap rather than re-rendering pointlessly.
    """

    defect_id: str
    knob_class: str
    knob: Optional[str]
    target: str
    proposal: str
    exhausted: bool = False


@dataclass
class RouteResult:
    """The outcome of routing a ``Fix``.

    ``status`` ∈ {"applied", "flagged", "exhausted"}. ``artifacts`` is
    ``{"pdf": Path, "png": Path, "package_dir": Path}`` when a renderer fix was
    APPLIED (the re-rendered outputs), else None.
    """

    status: str
    fix: Fix
    artifacts: Optional[dict[str, Any]]
    detail: str


# --------------------------------------------------------------------------- #
# 1. propose_fix
# --------------------------------------------------------------------------- #
def propose_fix(
    score,
    current_axes: dict[str, Any],
    *,
    st_type: str = "",
    current_layout_variant: str = "standard",
) -> Optional[Fix]:
    """Pick the top *renderer-fixable* defect and turn it into a ``Fix``.

    Walks ``score.defects`` in ranked order (hard-fails first; see
    ``analysis.score``) and returns the FIRST defect that is renderer-fixable:
    ``knob_class == "renderer"`` AND its id is in ``DEFECT_KNOBS``. Defects with
    knob_class ``asset_gen`` (e.g. N01 missing photo) or ``preprocessor`` (e.g.
    N14 placeholder leak) are NEVER proposed here -- they are out-of-renderer and
    are surfaced separately as flags (``route`` flags them when passed in
    explicitly; the brain/loop collects the rest). Returns None when no
    renderer-fixable defect exists.

    N08 (dead space) knob selection:
      * On an ST-07A case study whose ``current_layout_variant != "fill"`` the
        LAYOUT knob is preferred -- flipping standard->fill drops dead space far
        more than density ever could (see module doc). Returns a layout Fix
        (``knob="case_study_layout"``).
      * Otherwise (non-case-study, or layout already "fill") it falls back to the
        density knob: a concrete one-rung step Fix, or -- when density is already
        at the top of the ladder ("spacious") -- an ``exhausted=True`` Fix so the
        loop can flag the residual capability gap.

    The ``st_type`` / ``current_layout_variant`` kwargs are keyword-only with
    defaults, so legacy callers ``propose_fix(score, current_axes)`` keep working
    (they simply never get the layout knob).
    """
    for defect in score.defects:
        if defect.knob_class != "renderer":
            continue
        knob = DEFECT_KNOBS.get(defect.id)
        if knob is None:
            continue

        if knob == "density":
            # N08 on a case study: prefer the layout knob first (more effective).
            # EXCEPT the A3 casestudy_hero spread: forcing "fill" onto it is
            # DEGENERATE (the A4-fill render of an A3-designed page is hollow;
            # verified 2026-08-15 — the converge loop applied this knob and the
            # composed deck shipped 22 corrupt pages). The A3 spread's fix is
            # the scene/geometry work, not the layout knob.
            if (
                defect.id == "N08"
                and st_type in FILL_CAPABLE_ST_TYPES
                and current_layout_variant not in (
                    LAYOUT_LADDER[-1], "casestudy_hero",
                )
            ):
                return Fix(
                    defect_id="N08",
                    knob_class="renderer",
                    knob="case_study_layout",
                    target=defect.target,
                    proposal="set case_study_layout standard->fill",
                    exhausted=False,
                )

            cur = current_axes.get("density")
            if cur == DENSITY_LADDER[-1]:
                return Fix(
                    defect_id=defect.id,
                    knob_class="renderer",
                    knob="density",
                    target=defect.target,
                    proposal=(
                        "density knob exhausted at 'spacious'; residual dead "
                        "space needs a new layout capability"
                    ),
                    exhausted=True,
                )
            nxt = _next_density(cur)
            return Fix(
                defect_id=defect.id,
                knob_class="renderer",
                knob="density",
                target=defect.target,
                proposal=f"step density {cur}->{nxt}",
                exhausted=False,
            )

        # Defensive: a mapped knob we don't yet know how to step. Treat as a
        # renderer fix with no concrete ladder step (caller may extend).
        return Fix(
            defect_id=defect.id,
            knob_class="renderer",
            knob=knob,
            target=defect.target,
            proposal=f"apply renderer knob {knob}",
            exhausted=False,
        )

    return None


def _next_density(current: Optional[str]) -> str:
    """Next value UP the density ladder; clamps at the top.

    An unknown / missing current value is treated as the bottom rung so the
    ladder still steps forward deterministically.
    """
    try:
        idx = DENSITY_LADDER.index(current)  # type: ignore[arg-type]
    except ValueError:
        idx = 0
    return DENSITY_LADDER[min(idx + 1, len(DENSITY_LADDER) - 1)]


# --------------------------------------------------------------------------- #
# 2. apply_density_knob (the knob applier -- mutates a COPY only)
# --------------------------------------------------------------------------- #
def apply_density_knob(
    package_dir: Path | str,
    current_density: str,
    out_dir: Path | str,
) -> dict[str, Any]:
    """Copy the package, step density UP one rung, and re-render.

    Never mutates the original package: ``shutil.copytree`` clones the entire
    package into ``out_dir/patched_pkg`` first, then ``resolved_package.json``'s
    ``axes.density`` is rewritten to the next ladder value and the patched copy
    is re-rendered via ``assembler.render_package``.

    Returns ``{"pdf", "png_dir", "package_dir", "new_density"}``. PNGs land in
    ``out_dir`` as ``report-p{N}.png`` (N is 1-based); the caller maps a 0-based
    page_index N to ``report-p{N+1}.png``.
    """
    package_dir = Path(package_dir).resolve()
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    patched_pkg = out_dir / "patched_pkg"
    if patched_pkg.exists():
        shutil.rmtree(patched_pkg)
    shutil.copytree(package_dir, patched_pkg)

    new_density = _next_density(current_density)
    jpath = patched_pkg / "resolved_package.json"
    data = json.loads(jpath.read_text())
    data.setdefault("axes", {})["density"] = new_density
    jpath.write_text(json.dumps(data))

    # Imported lazily so the pure-logic tests don't pull in WeasyPrint/PyMuPDF.
    from assembler import render_package

    render_package(patched_pkg, out_dir)

    return {
        "pdf": out_dir / "report.pdf",
        "png_dir": out_dir,
        "package_dir": patched_pkg,
        "new_density": new_density,
    }


# --------------------------------------------------------------------------- #
# 2b. apply_layout_knob (the case-study layout applier -- mutates a COPY only)
# --------------------------------------------------------------------------- #
def apply_layout_knob(
    package_dir: Path | str,
    page_index: int,
    next_variant: str,
    out_dir: Path | str,
) -> dict[str, Any]:
    """Copy the package, set the target page's ``layout_variant``, and re-render.

    Never mutates the original package: ``shutil.copytree`` clones the entire
    package into ``out_dir/patched_pkg`` first, then ``resolved_package.json``'s
    ``pages[page_index]["layout_variant"]`` is rewritten to ``next_variant`` (e.g.
    "fill") and the patched copy is re-rendered via ``assembler.render_package``.

    Returns ``{"pdf", "png", "package_dir", "new_layout_variant"}``. The PNG is
    the target page's render (``report-p{page_index+1}.png``, 1-based file name).
    """
    package_dir = Path(package_dir).resolve()
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    patched_pkg = out_dir / "patched_pkg"
    if patched_pkg.exists():
        shutil.rmtree(patched_pkg)
    shutil.copytree(package_dir, patched_pkg)

    jpath = patched_pkg / "resolved_package.json"
    data = json.loads(jpath.read_text())
    data["pages"][page_index]["layout_variant"] = next_variant
    jpath.write_text(json.dumps(data))

    # Imported lazily so the pure-logic tests don't pull in WeasyPrint/PyMuPDF.
    from assembler import render_package

    render_package(patched_pkg, out_dir)

    return {
        "pdf": out_dir / "report.pdf",
        "png": out_dir / f"report-p{page_index + 1}.png",
        "package_dir": patched_pkg,
        "new_layout_variant": next_variant,
    }


# --------------------------------------------------------------------------- #
# 3. route
# --------------------------------------------------------------------------- #
def route(
    fix: Fix,
    package_dir: Path | str,
    current_axes: dict[str, Any],
    out_dir: Path | str,
    page_index: int = 0,
) -> RouteResult:
    """Route a ``Fix`` to APPLIED (renderer), FLAGGED (asset_gen/preprocessor),
    or EXHAUSTED.

    * Non-renderer fix -> ``status="flagged"``, ``artifacts=None``, NO render
      (the honest capability/asset-gap surface).
    * Exhausted renderer fix -> ``status="exhausted"``, ``artifacts=None``.
    * Renderer density fix -> apply the knob (re-render a patched copy) and
      return ``status="applied"`` with ``artifacts`` = the new pdf, the target
      page's png (``report-p{page_index+1}.png``), and the patched package dir.

    ``page_index`` is the 0-based index of the page the fix targets; it selects
    the right ``report-p{N}.png`` in the artifacts.
    """
    if fix.knob_class != "renderer":
        return RouteResult(
            status="flagged",
            fix=fix,
            artifacts=None,
            detail=(
                f"{fix.defect_id} is {fix.knob_class}-class -- out of renderer; "
                f"flagged as a capability/asset gap (no render): {fix.proposal}"
            ),
        )

    if fix.exhausted:
        return RouteResult(
            status="exhausted",
            fix=fix,
            artifacts=None,
            detail=f"{fix.defect_id} renderer knob exhausted: {fix.proposal}",
        )

    if fix.knob == "case_study_layout":
        applied = apply_layout_knob(
            package_dir, page_index, LAYOUT_LADDER[-1], out_dir
        )
        return RouteResult(
            status="applied",
            fix=fix,
            artifacts={
                "pdf": applied["pdf"],
                "png": applied["png"],
                "package_dir": applied["package_dir"],
                "new_layout_variant": applied["new_layout_variant"],
            },
            detail=(
                f"{fix.defect_id} applied: case_study_layout -> "
                f"{applied['new_layout_variant']} (re-rendered, target page "
                f"{page_index})"
            ),
        )

    if fix.knob == "density":
        applied = apply_density_knob(
            package_dir, current_axes.get("density"), out_dir
        )
        png = Path(applied["png_dir"]) / f"report-p{page_index + 1}.png"
        return RouteResult(
            status="applied",
            fix=fix,
            artifacts={
                "pdf": applied["pdf"],
                "png": png,
                "package_dir": applied["package_dir"],
            },
            detail=(
                f"{fix.defect_id} applied: density -> {applied['new_density']} "
                f"(re-rendered, target page {page_index})"
            ),
        )

    # A renderer fix whose knob we have no applier for yet -- be honest.
    return RouteResult(
        status="flagged",
        fix=fix,
        artifacts=None,
        detail=(
            f"{fix.defect_id} renderer knob '{fix.knob}' has no applier yet; "
            f"flagged: {fix.proposal}"
        ),
    )
