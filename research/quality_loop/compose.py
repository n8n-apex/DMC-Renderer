"""compose -- the package-merge step (Phase 3, compose-fixes).

The convergence loop renders each page's winning state into its own patched
package directory (``PageResult.best_artifacts['package_dir']``). Historically the
loop GRADED but the shipped deck stayed the pre-convergence render -- the loop's
own fixes were discarded (the deferred merge noted in ``stage_converge``).

``compose_converged_package`` closes that gap WITHOUT faking: it builds ONE merged
package that carries each page's winning PER-PAGE knob (``layout_variant``, e.g. a
case study flipped ``standard`` -> ``fill`` to resolve dead space), so re-rendering
the merged package ships the loop's fixes.

Scope (deliberate, honest):
  * PER-PAGE knobs (``layout_variant``) ARE merged -- they are independent and
    cannot regress another page.
  * The DECK-WIDE ``density`` axis is NOT merged from per-page winners: each page's
    density experiment changed the deck-wide axis and measured only that page, so
    composing per-page density winners is incoherent and could regress a page
    (the MONOTONE-BEST guard only protects a page in isolation). Choosing a single
    deck density is a separate deck-level optimization, left for later. The merged
    deck therefore keeps the ORIGINAL density and only gains the per-page layout
    fixes -- a strict, safe improvement over shipping the pre-convergence render.

Brand-agnostic: operates only on package data (st_type/layout_variant/axes), names
no client.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def compose_converged_package(
    original_package_dir: Path | str,
    deck_result: Any,
    merged_dir: Path | str,
) -> Path:
    """Build a merged package at ``merged_dir`` from the convergence result.

    Starts from a full copy of the original package (so assets/components/fonts are
    present and it is renderable), then overwrites each page's ``layout_variant``
    with that page's winning value read from its best-iteration patched package
    (``PageResult.best_artifacts['package_dir']``). The deck-wide ``axes`` are left
    as the original. Returns ``merged_dir``.
    """
    original = Path(original_package_dir)
    merged_dir = Path(merged_dir)
    if merged_dir.exists():
        shutil.rmtree(merged_dir)
    # Exclude the package's render-output tree from the copy. The merged dir
    # commonly lives UNDER original/out/converge/, so a full copy would copy the
    # merged dir INTO ITSELF recursively (converge/merged/out/converge/merged/...)
    # until ENAMETOOLONG, writing tens of GB on the way (2026-07-04 disk-full).
    # `out` is render OUTPUT, not package input; the package contract is
    # resolved_package.json + assets/ + components/ + fonts/.
    shutil.copytree(original, merged_dir,
                    ignore=shutil.ignore_patterns("out", "__pycache__"))

    manifest = json.loads((merged_dir / "resolved_package.json").read_text())
    pages = manifest.get("pages", [])

    for p in getattr(deck_result, "pages", []):
        art = getattr(p, "best_artifacts", None) or {}
        pkg_dir = art.get("package_dir")
        if not pkg_dir:
            continue  # error page / no render -> nothing to compose
        try:
            patched = json.loads(
                (Path(pkg_dir) / "resolved_package.json").read_text()
            )
        except OSError:
            continue  # patched package gone (volatile scratch dir) -> skip
        i = int(getattr(p, "page_index", -1))
        patched_pages = patched.get("pages", [])
        if 0 <= i < len(pages) and 0 <= i < len(patched_pages):
            winning_variant = patched_pages[i].get("layout_variant")
            if winning_variant is not None:
                pages[i]["layout_variant"] = winning_variant

    (merged_dir / "resolved_package.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return merged_dir
