"""Deck-level proof: converge the WHOLE deck and report by owner.

Where ``run_one_page.py`` proves the closed quality loop on ONE page, this script
runs the proven per-page loop across EVERY page of a deck via the brain's
``converge_deck`` and renders a single deck-level report -- the system
adjudicating all pages at once, replacing the manual per-page knob-spray.

The report has two parts:

  1. A per-page table -- one row per page: page | st_type | cleared | best_reward
     | fixes | top-flag. A fast read of where each page landed.

  2. A "DECK FLAGS BY OWNER" section -- every page's honest capability/asset-gap
     flag, grouped under the OWNER who must fix it (renderer / preprocessor /
     asset_gen / other), each line tagged with the page it came from. This is the
     deliverable: across the whole deck, exactly what each owner needs to fix.

The flags are the loop's OWN outputs (what it could not fix in-renderer), not
human guesses. Nothing here is brand-specific: all page/brand data comes from the
package.

Run it:

    cd research/v7-renderer && source .venv/bin/activate && cd ../quality_loop && \
        PYTHONPATH=...:... python run_deck.py
    # --vis enables the live reference-grounded vision client (many live calls);
    # OFF by default so the offline / no-key path runs with no network.
"""
from __future__ import annotations

import sys
from pathlib import Path

from brain import DeckResult, converge_deck

# --------------------------------------------------------------------------- #
# Defaults: the real Apex package (the deck-level proof target).
# --------------------------------------------------------------------------- #
RENDERER_ROOT = Path("/Users/utkarsh/Projects/richard/research/v7-renderer")
APEX_PKG = RENDERER_ROOT / "fixtures" / "apex"

# Default output root for deck renders (created on demand).
OUTPUT_ROOT = Path(__file__).resolve().parent / "output" / "deck"

# The owners a flag can be attributed to (the fix-able subsystems). "other" is
# the catch-all for flags with no parseable owner (e.g. oscillation notes).
_OWNERS = ("renderer", "preprocessor", "asset_gen", "other")


def run_deck(
    package_dir: Path | str = APEX_PKG,
    *,
    out_root: Path | str | None = None,
    max_iterations: int = 4,
    use_vis: bool = False,
) -> DeckResult:
    """Converge an entire deck through the closed loop and return its DeckResult.

    Calls the real ``converge_deck`` with all real defaults (real per-page
    perceive / score / conductor / references / renderer). The brain copies each
    package before turning a knob, so the source ``package_dir`` is never mutated.

    Args:
        package_dir: path to the package holding ``resolved_package.json``
            (defaults to the real Apex package).
        out_root: deck-level output root; page ``i`` renders into
            ``out_root/page_{i}``. Defaults to a dir under ``./output/deck/``.
        max_iterations: the per-page iteration-cap guard bound.
        use_vis: when True, build a real ``VisionClient()`` and thread it into
            every page's loop (many live, cached vision calls). Default False so
            the offline / no-key path runs with no network.

    Returns:
        The ``DeckResult`` -- one PageResult per page plus the aggregated,
        owner-attributable flag ledger.
    """
    if out_root is None:
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        out_root = OUTPUT_ROOT
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    vis_client = None
    if use_vis:
        # Lazy import: only pull in the real client (httpx/PIL) when requested.
        from vis_client import VisionClient

        vis_client = VisionClient()

    return converge_deck(
        str(package_dir),
        out_root=out_root,
        max_iterations=max_iterations,
        vis_client=vis_client,
    )


def _owner_of(flag: str) -> str:
    """Parse the owning subsystem out of a flag string.

    The brain encodes the owner in the flag text: out-of-renderer gaps end with
    ``-> asset_gen`` / ``-> preprocessor``; a residual renderer gap ends with
    ``-> renderer capability gap``; the captured-error flag ends with ``-> error``.
    We match the most specific known owner; anything else (e.g. an oscillation /
    no-progress note, or a skipped-rows count) falls under "other" so nothing is
    silently dropped.
    """
    low = flag.lower()
    # Prefer the explicit "-> owner" suffix tail when present.
    tail = low.rsplit("->", 1)[-1].strip() if "->" in low else low
    if "asset_gen" in tail:
        return "asset_gen"
    if "preprocessor" in tail:
        return "preprocessor"
    if "renderer" in tail:
        return "renderer"
    # Fallbacks for non-suffix forms (still attribute when unambiguous).
    if "asset_gen" in low:
        return "asset_gen"
    if "preprocessor" in low:
        return "preprocessor"
    if "renderer" in low:
        return "renderer"
    return "other"


def _top_flag(flags: list[str]) -> str:
    """The single most informative flag for the per-page table cell.

    Prefers a hard-fail-ish asset_gen gap, then a renderer capability gap, then a
    preprocessor gap, then whatever is first; "-" when there are no flags.
    """
    if not flags:
        return "-"
    for owner in ("asset_gen", "renderer", "preprocessor"):
        for f in flags:
            if _owner_of(f) == owner:
                return f
    return flags[0]


def format_deck_report(result: DeckResult) -> str:
    """Render a ``DeckResult`` to a human-readable deck report (a string).

    Sections:
      * header  -- deck size + cleared count;
      * per-page table -- page | st_type | cleared | best_reward | fixes |
        top-flag;
      * "DECK FLAGS BY OWNER" -- every flag grouped under renderer / preprocessor
        / asset_gen / other, each line tagged with its page index + st_type.

    Args:
        result: the deck convergence outcome to format.

    Returns:
        The full report as a single newline-separated string.
    """
    lines: list[str] = []
    bar = "=" * 92
    rule = "-" * 92

    # --- Header. ---------------------------------------------------------- #
    lines.append(bar)
    lines.append("DECK PROOF -- closed quality loop adjudicating the WHOLE deck")
    lines.append(bar)
    lines.append(
        f"pages adjudicated : {result.total}    "
        f"cleared : {result.cleared_count}/{result.total}"
    )
    lines.append("")

    # --- Per-page table. -------------------------------------------------- #
    lines.append("PER-PAGE OUTCOME")
    lines.append(rule)
    header = (
        f"{'page':>4} | {'st_type':<9} | {'cleared':<7} | {'best_reward':>11} | "
        f"{'fixes':>5} | top-flag"
    )
    lines.append(header)
    lines.append(rule)
    for p in result.pages:
        fixes = len(p.fixes_applied)
        top = _top_flag(p.flags)
        lines.append(
            f"{p.page_index:>4} | {p.st_type:<9} | {str(p.cleared):<7} | "
            f"{p.best_reward:>11.0f} | {fixes:>5} | {top}"
        )
    lines.append(rule)
    lines.append("")

    # --- Flags grouped by owner. ------------------------------------------ #
    lines.append("DECK FLAGS BY OWNER")
    lines.append(rule)
    lines.append(
        "(the loop's own outputs -- what each subsystem must fix across the deck)"
    )
    by_owner: dict[str, list[dict]] = {o: [] for o in _OWNERS}
    for entry in result.deck_flags:
        by_owner[_owner_of(entry["flag"])].append(entry)

    for owner in _OWNERS:
        entries = by_owner[owner]
        lines.append("")
        lines.append(f"[{owner}] ({len(entries)})")
        if not entries:
            lines.append("  (none)")
            continue
        for e in entries:
            lines.append(
                f"  - p{e['page_index']:<2} {e['st_type']:<8} {e['flag']}"
            )
    lines.append(bar)

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: converge the (default Apex) deck and print the report.

    Usage:
        python run_deck.py [--vis] [package_dir] [max_iterations]

    ``--vis`` enables the live reference-grounded vision client (many live,
    cached vision calls -- one per VIS-bearing iteration per page). It is OFF by
    default so the offline / no-key path runs with no network.

    Returns a process exit code (always 0 -- a deck of honest ship-best-with-flags
    pages is a successful run, not an error; the report carries the verdict).
    """
    argv = list(sys.argv[1:] if argv is None else argv)

    use_vis = "--vis" in argv
    positional = [a for a in argv if a != "--vis"]

    package_dir: Path | str = APEX_PKG
    max_iterations = 4
    if len(positional) >= 1:
        package_dir = positional[0]
    if len(positional) >= 2:
        max_iterations = int(positional[1])

    result = run_deck(
        package_dir, max_iterations=max_iterations, use_vis=use_vis
    )
    print(format_deck_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
