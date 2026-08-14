"""Tests for compose.py -- the package-merge step (Phase 3, compose-fixes).

The convergence loop renders each page's winning state into its own patched
package_dir (PageResult.best_artifacts['package_dir']). compose builds ONE merged
package carrying each page's winning PER-PAGE knob (layout_variant), so the loop's
fixes actually SHIP instead of being discarded. The deck-wide ``density`` axis is
intentionally left at the original (per-page density winners are incoherent to
merge and merging them could regress a page; that is a separate deck-level pass).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from brain import DeckResult, PageResult

from compose import compose_converged_package
from stage_converge import run_stage


def _write_pkg(d: Path, *, density: str, variants: list[str]) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "assets").mkdir(exist_ok=True)  # a real package has sibling asset dirs
    manifest = {
        "version": "2.0",
        "axes": {"density": density},
        "brand": {},
        "pages": [
            {"slot": i + 1, "st_type": "ST-07A", "layout_variant": v}
            for i, v in enumerate(variants)
        ],
    }
    (d / "resolved_package.json").write_text(json.dumps(manifest), encoding="utf-8")
    return d


def _page_result(idx: int, pkg_dir: Path) -> PageResult:
    return PageResult(
        page_index=idx, st_type="ST-07A", cleared=False, best_reward=0.0,
        best_iteration=0, iterations=[], fixes_applied=[], flags=[],
        shipped_best=True, best_artifacts={"package_dir": pkg_dir},
    )


def test_compose_applies_per_page_layout_winner_keeps_deck_density(tmp_path):
    original = _write_pkg(tmp_path / "orig", density="balanced",
                          variants=["standard", "standard"])
    # Page 0's best iteration won the layout knob (standard -> fill) AND happened
    # to step the deck-wide density; page 1 never changed.
    patched0 = _write_pkg(tmp_path / "p0", density="spacious",
                          variants=["fill", "standard"])
    patched1 = original  # page 1 best iteration is the unchanged original

    deck = DeckResult(
        pages=[_page_result(0, patched0), _page_result(1, patched1)],
        deck_flags=[], cleared_count=0, total=2,
    )

    merged = compose_converged_package(original, deck, tmp_path / "merged")
    manifest = json.loads((merged / "resolved_package.json").read_text())

    # Per-page layout winner composed:
    assert manifest["pages"][0]["layout_variant"] == "fill"
    # Untouched page keeps its original variant:
    assert manifest["pages"][1]["layout_variant"] == "standard"
    # Deck-wide density axis is NOT merged from a per-page winner (stays original):
    assert manifest["axes"]["density"] == "balanced"
    # The merged dir is a complete, renderable package (manifest + assets copied):
    assert (merged / "resolved_package.json").exists()
    assert (merged / "assets").is_dir()


def test_compose_ignores_pages_without_artifacts(tmp_path):
    original = _write_pkg(tmp_path / "orig", density="balanced",
                          variants=["standard", "standard"])
    p0 = PageResult(
        page_index=0, st_type="ST-07A", cleared=False, best_reward=0.0,
        best_iteration=-1, iterations=[], fixes_applied=[], flags=[],
        shipped_best=False, best_artifacts=None,  # error page: no artifacts
    )
    deck = DeckResult(pages=[p0], deck_flags=[], cleared_count=0, total=1)
    merged = compose_converged_package(original, deck, tmp_path / "merged")
    manifest = json.loads((merged / "resolved_package.json").read_text())
    # No artifacts -> nothing to compose; the original variant is preserved.
    assert manifest["pages"][0]["layout_variant"] == "standard"


def test_run_stage_composes_and_renders_merged_deck(tmp_path):
    """run_stage(compose=True) must build the merged package and RE-RENDER it as
    the shipped deck, handing the renderer the page-0 'fill' winner."""
    orig = _write_pkg(tmp_path / "pkg", density="balanced",
                      variants=["standard", "standard"])
    patched0 = _write_pkg(tmp_path / "p0", density="balanced",
                          variants=["fill", "standard"])

    def fake_converge(pkg, **kw):
        return DeckResult(
            pages=[_page_result(0, patched0), _page_result(1, orig)],
            deck_flags=[], cleared_count=0, total=2,
        )

    rendered: list[tuple[Path, dict]] = []

    def fake_render(package_dir, out_dir, **kw):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "report.pdf").write_bytes(b"%PDF-merged")
        rendered.append((Path(package_dir), kw))

    report = run_stage(
        orig, tmp_path / "out", use_vis=False, compose=True,
        converge_deck_fn=fake_converge, render_fn=fake_render,
    )

    # The composed PDF was produced and its path returned in the report.
    assert "composed_pdf" in report
    assert Path(report["composed_pdf"]).read_bytes() == b"%PDF-merged"
    # The renderer was handed the MERGED package (page 0 flipped to 'fill').
    merged_pkg, render_kw = rendered[-1]
    merged_manifest = json.loads((merged_pkg / "resolved_package.json").read_text())
    assert merged_manifest["pages"][0]["layout_variant"] == "fill"
    # The SHIP render MUST be pinned to chromium (addition A: render_package's
    # function default is weasyprint, which silently produces a different deck).
    assert render_kw.get("engine") == "chromium"


def test_run_stage_without_compose_is_unchanged(tmp_path):
    """Default (compose=False) never renders a merged deck -> no regression."""
    orig = _write_pkg(tmp_path / "pkg", density="balanced", variants=["standard"])

    def fake_converge(pkg, **kw):
        return DeckResult(pages=[_page_result(0, orig)], deck_flags=[],
                          cleared_count=0, total=1)

    called: list[Path] = []

    def fake_render(package_dir, out_dir, **kw):
        called.append(Path(package_dir))

    report = run_stage(orig, tmp_path / "out", use_vis=False,
                       converge_deck_fn=fake_converge, render_fn=fake_render)
    assert "composed_pdf" not in report
    assert called == []  # no merged re-render on the default path
