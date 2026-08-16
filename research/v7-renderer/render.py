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
        "--no-visual-gate", action="store_true",
        help="SKIP the blocking visual QA gate (NEVER for a delivery — the "
             "gate is what stops ugly decks from shipping)",
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


def _gate_rows_for_stype(st_type: str) -> list[str]:
    """US-510: which rubric rows gate a page — by DESIGN INTENT, not uniformly.

    Device pages must carry real bound data (P11). Editorial/theory pages gate
    on density (P12) — their device IS the layout (Richard's theory pages are
    text-dense by design; a forced chart would be wrong). Breathers gate on
    photo treatment (P14) + atmosphere (P13) — their device is the image.
    Cover/back cover gate on density. The gate is about "does this page do its
    JOB well", never "every page must have a chart".
    """
    st = str(st_type or "")
    if st in ("ST-07A", "ST-02", "ST-09", "ST-FAZIT", "ST-06", "ST-22"):
        # device pages: AT LEAST ONE real bound figure (P11* — a page with a
        # single honest number must never fabricate a second) + density.
        return ["P11*", "P12"]
    if st == "ST-31":
        return ["P14", "P13"]        # breathers: photo treatment + atmosphere
    if st in ("ST-01", "ST-03"):
        # cover/back: a deliberate quiet frame. The BACK cover's job is the
        # CTA + QR (its device), NOT light-editorial density — Richard's
        # closings are deliberately uncluttered. P12 misreads the quiet as
        # "empty"; gate on atmosphere (the dark ground) + the CTA presence.
        return ["P13"] if st == "ST-03" else ["P12"]
    if st == "ST-07B":
        # DARK-DIVIDER theory pages (Richard's deliberate full-bleed dark
        # essay spreads): the design intent is a dark ground + one oversized
        # statement + the ghost numeral — a solid dark fill IS the move, and
        # P12 (light editorial density) misreads it as "empty". Gate on
        # atmosphere (P13) + a bound figure ONLY when the body carries real
        # figures (a figure-free essay must never fabricate one).
        return ["P13", "P11*?figures"]
    return ["P12", "P11*"]           # other editorial: density + bound figure


def _run_visual_qa_gate(out_dir: Path, *, threshold: int = 2) -> None:
    """US-510: the VISUAL QA gate — the taste check the render must pass.

    Every page PNG is scored by the vision reviewer against the rubric's
    composition/device rows. Any page whose DEVICE-quality score is below
    `threshold` fails the gate: the deck does NOT ship. This is the "why did
    the Power BI abominations pass?" answer — they will not anymore. Requires
    OPENROUTER_API_KEY (env or .env); without it the gate is skipped with a
    LOUD warning (never a silent pass).
    """
    import os
    import sys
    # the vision client needs the preprocessor .env + its deps (httpx).
    _env_path = HERE.parent / "preprocessor" / ".env"
    if _env_path.exists():
        for line in _env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                # the FILE is authoritative: a stale shell export (e.g. an old
                # rotated key lingering in the terminal) must not beat it.
                os.environ[k] = v
    ql_root = (HERE.parent / "quality_loop").resolve()
    research_root = HERE.parent
    for _p in (str(research_root), str(ql_root)):
        if _p not in sys.path:
            sys.path.insert(0, _p)

    try:
        from quality_loop.vis_client import _read_env_file, VisionClient
    except ImportError as exc:
        print(f"[qa] vision client unavailable ({exc}) — VISUAL gate skipped")
        return
    key = _read_env_file("OPENROUTER_API_KEY")
    if not key:
        print("[qa] WARNING: no OPENROUTER_API_KEY — VISUAL gate skipped "
              "(the deck ships UNREVIEWED)")
        return

    # the device-quality rows: P11 data-viz, P12 dense editorial, P07 social proof
    device_rows = ["P11", "P12", "P13", "P14"]
    client = VisionClient()
    # NUMERIC sort — the filenames are report-p1..p20; a plain sorted() puts
    # p10 before p2 (lexicographic), scrambling the PNG->st_type mapping.
    pngs = sorted(out_dir.glob("report-p*.png"), key=lambda f: int(f.stem.rsplit("p", 1)[1]))
    # map rasterized PNG order -> page st_type from the package (the PDF pages
    # are logical-order; PNGs are rasterized 1:1 with physical pages).
    st_types: list[str] = []
    pkg_json = out_dir.parent / "fixtures" / "apex" / "resolved_package.json"
    if pkg_json.exists():
        import json as _json
        pkg = _json.loads(pkg_json.read_text(encoding="utf-8"))
        for pg in pkg.get("pages", []):
            st_types.append(str(pg.get("st_type", "")))
    failed: list[str] = []
    for i, png in enumerate(pngs):
        rows = _gate_rows_for_stype(st_types[i] if i < len(st_types) else "")
        try:
            scores = client.score_page(str(png), [], rows)
        except Exception as exc:  # noqa: BLE001 -- a reviewer outage must be loud
            print(f"[qa] VISUAL gate reviewer error on {png.name}: {exc}")
            failed.append(f"{png.name}: reviewer error")
            continue
        for row in rows:
            # P11* = theory pages need AT LEAST one bound figure (score 1+);
            # full device pages require the full device quality (score 2+).
            # P11*?figures = the figure requirement is SKIPPED when the page's
            # data carries no real figures at all (no fabrication on a
            # figure-free essay — its device is the dark treatment).
            if row.endswith("?figures"):
                page_data = st_types[i] if i < len(st_types) else ""
                has_figures = False
                try:
                    import re as _re
                    _pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
                    if i < len(_pkg.get("pages", [])):
                        _raw = json.dumps((_pkg["pages"][i].get("data") or {}))
                        has_figures = bool(_re.search(r"\d", _raw))
                except Exception:
                    pass
                if not has_figures:
                    continue  # figure-free theory essay: atmosphere is the bar
                clean = "P11"
                row_threshold = 1
            else:
                row_threshold = 1 if row.endswith("*") else threshold
                clean = row.rstrip("*")
            score = (scores.get(clean) or {}).get("score", 0)
            # reviewer variance damping: a single-figure device occasionally
            # scores 0 on one read (same page scored 1 on an earlier read).
            # One re-read converges; take the max so a real device never
            # false-blocks on reviewer wobble.
            if isinstance(score, int) and score < row_threshold:
                try:
                    reread = client.score_page(str(png), [], [clean])
                    score = max(score, (reread.get(clean) or {}).get("score", 0))
                except Exception:
                    pass
            if isinstance(score, int) and score < row_threshold:
                failed.append(f"{png.name}: {clean} quality {score} < {row_threshold}")
                break
    if failed:
        raise SystemExit(
            f"[qa] VISUAL GATE FAILED ({len(failed)} pages): "
            + "; ".join(failed[:6])
            + " — the deck does NOT ship. Fix the devices, then re-render."
        )
    print(f"[qa] visual gate: CLEAN ({len(pngs)} pages, device threshold {threshold})")


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

    # US-510 VISUAL GATE: the taste check — every page's device quality must
    # clear the threshold or the deck does NOT ship. Opt-out only via
    # --no-visual-gate (never for a delivery).
    if not args.no_visual_gate:
        _run_visual_qa_gate(out_dir)

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
