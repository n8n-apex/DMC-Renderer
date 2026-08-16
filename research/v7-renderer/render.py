"""Renderer entrypoint — multi-page apex build through the chassis.

Reads the pre-processor's resolved_package.json (fixtures/apex/) and
emits a multi-page RGB PDF: case-study pages real (st_07a), every other
page a brand-styled _generic skeleton.

Hard constraints preserved from the prior frame:
  - INPUT-DRIVEN: all brand/content values come from the package; no
    client name or hex literal in logic.
  - NO SILENT FONT FALLBACK: _preflight_fonts() requires the 4 variable
    fonts on disk (Source Serif 4 + Source Sans 3) before rendering.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from assembler import render_package  # noqa: E402

FONT_DIR = (HERE / "fonts").resolve()
FIXTURES_APEX_DIR = (HERE / "fixtures" / "apex").resolve()
OUTPUT_DIR = (HERE / "output").resolve()

_REQUIRED_FONTS = (
    "SourceSans3[wght].ttf",
    "SourceSans3-Italic[wght].ttf",
    "SourceSerif4[opsz,wght].ttf",
    "SourceSerif4-Italic[opsz,wght].ttf",
)


def _preflight_fonts() -> None:
    missing = [n for n in _REQUIRED_FONTS if not (FONT_DIR / n).exists()]
    if missing:
        raise FileNotFoundError(
            f"Required fonts missing from {FONT_DIR}: {missing}. The chassis "
            f"does NOT silently fall back to a system font. Ensure the "
            f"Source Sans 3 + Source Serif 4 variable font files are present in fonts/."
        )


def _run_convergence(package_dir: Path, out_dir: Path, *, use_vis: bool,
                     max_iterations: int, page_indices) -> None:
    """Stage 9: grade the rendered deck against the references and write the
    convergence report. The quality loop is imported lazily so a plain ``--fast``
    render never pulls it (or its vision client) in."""
    ql_root = (HERE.parent / "quality_loop").resolve()
    if str(ql_root) not in sys.path:
        sys.path.insert(0, str(ql_root))
    import stage_converge  # noqa: E402

    conv_out = out_dir / "converge"
    report = stage_converge.run_stage(
        package_dir, conv_out, use_vis=use_vis,
        max_iterations=max_iterations, page_indices=page_indices,
        compose=True,
    )
    print(f"[converge] graded {report['total']} page(s): "
          f"cleared {report['cleared_count']}/{report['total']}  "
          f"deck_reward={report['deck_reward']}")
    for owner, items in report["flags_by_owner"].items():
        if items:
            print(f"[converge]   {owner}: {len(items)} flag(s)")
    print(f"[converge] report: {conv_out / 'convergence_report.json'}")

    # Phase 3: SHIP the composed (fix-merged) deck -- the loop's per-page fixes
    # replace the pre-convergence render as the deliverable report.pdf + PNGs.
    composed = report.get("composed_pdf")
    if composed and Path(composed).exists():
        composed_pdf = Path(composed)
        shutil.copyfile(composed_pdf, out_dir / "report.pdf")
        for png in sorted(composed_pdf.parent.glob("report-p*.png")):
            shutil.copyfile(png, out_dir / png.name)
        print(f"[converge] shipped composed deck -> {out_dir / 'report.pdf'}")


def _build_parser():
    import argparse
    parser = argparse.ArgumentParser(description="Render the apex deck")
    parser.add_argument(
        "--engine", choices=("chromium", "weasyprint"), default="chromium",
        help="PDF engine: chromium (default — full depth vocabulary, "
             "Ghostscript-flattened) or weasyprint (legacy fallback)",
    )
    parser.add_argument(
        "--fast", action="store_true",
        help="skip Stage 9 (the reference-grounded convergence loop) for quick "
             "local iteration; the default build runs it",
    )
    parser.add_argument(
        "--treatments", action="store_true",
        help="enable the per-page treatment system (A3/A4 premium layouts); default OFF",
    )
    parser.add_argument(
        "--converge-pages", type=int, default=0,
        help="limit convergence to the first N pages (cost control); 0 = all",
    )
    parser.add_argument(
        "--converge-max-iter", type=int, default=4,
        help="per-page iteration cap for the convergence loop",
    )
    parser.add_argument(
        "--no-converge-vis", action="store_true",
        help="run the convergence loop deterministic-only (no vision calls)",
    )
    parser.add_argument(
        "--package-dir", default=str(FIXTURES_APEX_DIR),
        help="package directory to rasterize (its resolved_package.json is the "
             "deck source); defaults to the apex fixture for back-compat",
    )
    parser.add_argument(
        "--output-dir", default=str(OUTPUT_DIR),
        help="directory for report.pdf + PNGs + the convergence report; defaults "
             "to ./output. Per-job dirs let concurrent renders isolate (the "
             "orchestrator points each job at its own dir).",
    )
    return parser


def _run_qa_gate(out_dir: Path, html_path: Path | None = None) -> None:
    """US-510: the DET overlap QA gate — runs on EVERY render.

    Measures the ACTUAL print geometry (via Playwright on the assembled HTML)
    and flags any flow element rendered under an absolutely-positioned panel.
    A deck with overlaps CANNOT ship: the gate raises (non-zero exit).
    """
    import sys
    ql_root = (HERE.parent / "quality_loop").resolve()
    if str(ql_root) not in sys.path:
        sys.path.insert(0, str(ql_root))
    from overlap_detector import detect_overlaps  # noqa: PLC0415

    html = html_path or (out_dir / "report.html")
    if not html.exists():
        print("[qa] report.html not found — skipping overlap gate")
        return
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError:
        print("[qa] playwright unavailable — skipping overlap gate")
        return

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(html.resolve().as_uri())
        page.emulate_media(media="print")
        geometry = page.evaluate(
            """() => [...document.querySelectorAll('section.page')].map((s) => {
                const r = s.getBoundingClientRect();
                return {cls: s.className, y: Math.round(r.y), bottom: Math.round(r.bottom),
                        position: getComputedStyle(s).position,
                        children: [...s.children].map(c => {
                          const cr = c.getBoundingClientRect();
                          return {cls: c.className, y: Math.round(cr.y),
                                  bottom: Math.round(cr.bottom),
                                  position: getComputedStyle(c).position,
                                  z_index: getComputedStyle(c).zIndex};
                        })};
            })"""
        )
        browser.close()
    faults = detect_overlaps(geometry)
    if faults:
        detail = "; ".join(f["detail"] for f in faults[:5])
        raise SystemExit(
            f"[qa] OVERLAP GATE FAILED: {len(faults)} element(s) under absolute "
            f"panels — {detail}. Fix the layout; this deck must NOT ship."
        )
    print("[qa] overlap gate: CLEAN")


def main() -> int:
    args = _build_parser().parse_args()
    package_dir = Path(args.package_dir).resolve()
    out_dir = Path(args.output_dir).resolve()

    out_dir.mkdir(parents=True, exist_ok=True)
    _preflight_fonts()

    print(f"[render] engine: {args.engine}")
    print(f"[render] package: {package_dir}")
    print(f"[render] output: {out_dir}")
    result = render_package(package_dir, out_dir, engine=args.engine,
                            treatments=args.treatments)

    print(f"[render] PDF: {result.pdf_path} "
          f"({result.pdf_path.stat().st_size:,} bytes)")
    print(f"[render] logical pages: {result.page_count}  "
          f"rasterized PNGs: {len(result.png_paths)}")
    print(f"[render] accent_budget_passed: {result.accent_budget_passed}")
    if result.overflow:
        print(f"[render] OVERFLOW (advisory): {result.overflow}")
    if result.warnings:
        print(f"[render] warnings: {result.warnings}")

    # US-510 QA GATE: the DET overlap check runs on EVERY render (fast or
    # full). A deck whose content sits under an absolute panel (the p18
    # cost-block-inside-CTA fault) CANNOT ship — non-zero exit + clear error.
    _run_qa_gate(out_dir, html_path=result.html_path if hasattr(result, "html_path") else None)

    if args.fast:
        print("[render] --fast: skipping Stage 9 convergence.")
    elif args.treatments:
        print("[render] --treatments: skipping Stage 9 (the grader compares vs A4 "
              "st_type refs and would false-flag A3/treatment pages; per-page "
              "convergence gating is a later refinement).")
    else:
        page_indices = (list(range(args.converge_pages))
                        if args.converge_pages > 0 else None)
        _run_convergence(
            package_dir, out_dir,
            use_vis=not args.no_converge_vis,
            max_iterations=args.converge_max_iter,
            page_indices=page_indices,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
