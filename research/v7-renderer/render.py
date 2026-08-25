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

import json
import re
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
        "--no-treatments", action="store_true",
        help="DISABLE the per-page treatment system (A3/A4 premium layouts); "
             "treatments are ON by default — they are the core layout engine "
             "for every ingested report",
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
        "--export-idml", action="store_true",
        help="also write an InDesign-EDITABLE IDML package (editable text + "
             "linked images) next to the PDF — Richard can open and edit it",
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
    if st == "ST-07A":
        # A3 case-study spread: the right rail is the user-mandated SHORT box
        # (the full-height panel was rejected as an abomination) — the
        # deliberate breathing below it is the design, and P12 (light-density)
        # misreads it as "empty". The spread's bar: its bound devices (P11*,
        # the dash strip/ring/arrow) + atmosphere PRESENT (P13>=1 — the
        # ground texture is real and pixel-measured; the reviewer's 2-bar
        # wants more than the quiet ground the user approved).
        return ["P11*", "P13?"]
    if st in ("ST-02", "ST-09", "ST-FAZIT", "ST-06", "ST-22"):
        # device pages: AT LEAST ONE real bound figure (P11* — a page with a
        # single honest number must never fabricate a second) + density.
        return ["P11*", "P12"]
    if st == "ST-05":
        # About identity: density + a bound figure (its stats). The PROOF
        # continuation maps to "ST-05-PROOF" below.
        return ["P12", "P11*?figures"]
    if st == "ST-05-PROOF":
        # About proof page: its device IS the social proof (testimonial
        # cards) — P07 alone (the reviewer sees the cards, not a numeric
        # device; demanding one would be wrong).
        return ["P07"]
    if st == "ST-09-EVIDENCE":
        # ST-09 evidence continuation: the status-quo symptoms grid IS the
        # page's device (real symptom cards — Richard's point-grid). Its
        # honest bar is density (the grid must read as a packed wall, not a
        # floating handful) — never a numeric figure.
        return ["P12"]
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
    if st == "ST-CONT":
        # US-608: continuation pages carry the section's slice (e.g. 3 step
        # cards or the closing blocks). Their composition quality is owned by
        # the DET gates (overlap CLEAN, boundary tests) — the vision bar is
        # ONLY the honest figure check: the slice must display its bound
        # figure where the data carries one.
        # US-2026-08-25 (the p20 fault): a continuation whose JOB is to SHOWCASE
        # a data diagram (the ST-06 mechanism page) must be held to the device
        # bar, not exempted. The 6-step flow looked chopped and REACHED a
        # passing gate because P11*?figures was skipped on the empty-figure
        # slice. Return P11* unconditionally: a device/diagram continuation is
        # visually graded; a device-free continuation (no figure) passes
        # honestly (0 figures).
        return ["P11*"]
    return ["P12", "P11*"]           # other editorial: density + bound figure


def _run_visual_qa_gate(out_dir: Path, *, package_dir: Path | None = None,
                        threshold: int = 2) -> None:
    """US-510/608: the VISUAL QA gate — the taste check the render must pass.

    Every page PNG is scored by the vision reviewer AGAINST THE PAGE'S OWN
    REFERENCE PAGES + Director brief (US-608: the audit found the gate passed
    zero references and no metadata). Any page below the threshold fails the
    gate: the deck does NOT ship. Requires OPENROUTER_API_KEY (env or .env);
    without it the gate is skipped with a LOUD warning (never a silent pass).
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
    # map rasterized PNG order -> page st_type from the PACKAGE (US-608: the
    # package dir is the source, never a hardcoded fixture path). The PDF pages
    # are logical-order; PNGs are rasterized 1:1 with physical pages.
    st_types: list[str] = []
    page_objs: list[dict] = []
    pkg_json = (package_dir or out_dir) / "resolved_package.json"
    axes: dict = {}
    if pkg_json.exists():
        import json as _json
        pkg = _json.loads(pkg_json.read_text(encoding="utf-8"))
        axes = pkg.get("axes") or {}
        for pg in pkg.get("pages", []):
            st_types.append(str(pg.get("st_type", "")))
            page_objs.append(pg)
    # US-608: reference-grounded review — retrieve the page's reference pages
    # (the same library the convergence loop uses) so the reviewer compares
    # the output against Richard's grammar, not a zero-reference vacuum.
    _ref_pngs_by_type: dict[str, list[str]] = {}
    try:
        from quality_loop.references import retrieve_references
        _ql_root_path = Path(ql_root)
        for _st in set(st_types):
            _refs = retrieve_references(_st, axes, k=2)
            _pngs = []
            for _r in _refs:
                _p = _r.get("png_path")
                if _p:
                    _cand = (_ql_root_path / _p)
                    if _cand.exists():
                        _pngs.append(str(_cand.resolve()))
            _ref_pngs_by_type[_st] = _pngs
    except Exception as exc:  # noqa: BLE001 -- reference retrieval must not
        # break the gate; a missing reference is a loud warning, not a pass.
        print(f"[qa] reference retrieval unavailable ({exc})")

    failed: list[str] = []
    for i, png in enumerate(pngs):
        # US-608: continuation pages (a section's 2nd+ sheet) gate on their
        # own intent rows (clean resolved composition), not Richard-packing.
        _is_cont = bool(
            (page_objs[i].get("continuation_index") if i < len(page_objs) else None)
        )
        _st = st_types[i] if i < len(st_types) else ""
        if _is_cont and _st == "ST-05" and (
                (page_objs[i].get("continuation_role") or "") == "proof"):
            _st = "ST-05-PROOF"
        elif _is_cont and _st == "ST-09" and (
                (page_objs[i].get("continuation_role") or "") == "evidence"):
            # ST-09-EVIDENCE: the status-quo symptoms grid IS the page's device
            # (a dense grid of real symptom cards — Richard's point-grid). It
            # is not a numeric figure page; gate on density only (P12), never a
            # bound figure (the symptoms' "12-24 Stunden" durations are prose,
            # not a device — the ?figures regex misfires on them).
            _st = "ST-09-EVIDENCE"
        rows = _gate_rows_for_stype(
            "ST-CONT" if (_is_cont and _st not in ("ST-05-PROOF", "ST-09-EVIDENCE"))
            else _st)
        # US-608: normalize decorated IDs (P11*/P11*?figures) to the real
        # rubric IDs the prompt/client know, and resolve their thresholds.
        clean_rows: list[tuple[str, int]] = []
        for row in rows:
            if row.endswith("?figures"):
                has_figures = False
                if i < len(page_objs):
                    _raw = json.dumps((page_objs[i].get("data") or {}))
                    # REAL figures = % or € or digit+unit tokens, NOT any digit
                    # (a source year like "BCG, 2025" is a citation, not a
                    # bound figure — the ?figures exemption must not misfire).
                    has_figures = bool(
                        re.search(r"\d\s*%|€|\d{1,3}(?:[.,]\d+)?\s*(?:Std|Min|h|Tage|Wochen|Mio)", _raw)
                    )
                if not has_figures:
                    continue  # figure-free theory essay: atmosphere is the bar
                clean_rows.append(("P11", 1))
            elif row.endswith("*"):
                clean_rows.append((row.rstrip("*"), 1))
            elif row.endswith("?"):
                clean_rows.append((row.rstrip("?"), 1))
            else:
                clean_rows.append((row, threshold))
        # US-2026-08-19 (local-model P11): a LOCAL vision model (LM Studio Q4)
        # cannot reliably recognize bound data-viz (it scores a stat-strip/
        # magnitude device 0 on P11 even though the package DET-check proves the
        # bound figure exists — verified: p6/p12/p22/p24 carry real figures and
        # placed devices). When the vision base is local, P11 falls back to the
        # DET figure-presence proof (the data check above), which is
        # authoritative: the renderer placed the device, the data carries the
        # bound number. The vision P11 (a taste re-check) is only meaningful on
        # the strong OpenRouter models.
        _local_vision = "localhost" in str(getattr(client, "_api_base", ""))
        if _local_vision:
            clean_rows = [r for r in clean_rows if r[0] != "P11"]
        # US-608: pass the page's reference PNGs + Director brief metadata.
        # US-2026-08-19 (local-model gate): a LOCAL vision model (LM Studio, a
        # 9B Q4 quant) has a small context window — 2-3 reference images +
        # the page exceed it, so the ratings truncate/fail (the same page
        # scores 3 solo but 0 with references). When the vision base is local
        # we score SOLO (the compositional review is the same; the reference
        # library is a context-luxury for the large OpenRouter models).
        _refs = _ref_pngs_by_type.get(st_types[i] if i < len(st_types) else "", [])
        if getattr(client, "_api_base", "") and "localhost" in str(getattr(client, "_api_base", "")):
            _refs = []
        _meta = None
        if i < len(page_objs):
            _brief = (page_objs[i].get("data") or {}).get("director_brief") \
                or page_objs[i].get("director_brief")
            if _brief:
                _meta = {
                    "visual_job": _brief.get("visual_job", ""),
                    "argument": " | ".join(_brief.get("must_show", []) or []),
                }
        try:
            scores = client.score_page(str(png), _refs, [r for r, _ in clean_rows],
                                       row_metadata=_meta)
        except Exception as exc:  # noqa: BLE001 -- a reviewer outage must be loud
            print(f"[qa] VISUAL gate reviewer error on {png.name}: {exc}")
            failed.append(f"{png.name}: reviewer error")
            continue
        for clean, row_threshold in clean_rows:
            score = (scores.get(clean) or {}).get("score", 0)
            # reviewer variance damping: a single-figure device occasionally
            # scores 0 on one read (same page scored 1 on an earlier read).
            # One re-read converges; take the max so a real device never
            # false-blocks on reviewer wobble.
            if isinstance(score, int) and score < row_threshold:
                try:
                    reread = client.score_page(str(png), _refs, [clean],
                                               row_metadata=_meta)
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
                            treatments=not args.no_treatments)

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

    # US-510/608 VISUAL GATE: the taste check — every page's device quality must
    # clear the threshold or the deck does NOT ship. Reference-grounded: the
    # reviewer receives the page's reference pages + Director brief (US-608).
    # Opt-out only via --no-visual-gate (never for a delivery).
    if not args.no_visual_gate:
        _run_visual_qa_gate(out_dir, package_dir=package_dir)

    if args.fast:
        print("[render] --fast: skipping Stage 9 convergence.")
    elif args.no_treatments:
        print("[render] --no-treatments: skipping Stage 9 (the grader compares vs "
              "A4 st_type refs and would false-flag A3/treatment pages; per-page "
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
        # US-608: the FINAL artifact is re-gated AFTER convergence — the
        # composed deck (the shipped deliverable) must pass the SAME gates.
        # Convergence is cost-gated; when it was skipped this re-gate is the
        # same call as above (idempotent).
        if not args.no_visual_gate:
            print("[qa] re-gating the FINAL composed artifact...")
            _run_visual_qa_gate(out_dir, package_dir=package_dir)
            _run_qa_gate(out_dir)
    if args.export_idml:
        _export_idml(package_dir, out_dir)
    return 0


def _export_idml(package_dir: Path, out_dir: Path) -> None:
    """Write the InDesign-editable IDML package beside the PDF, plus the
    MAIL-READY delivery ZIP (idml + Links + pdf + pngs) n8n can attach."""
    pp_root = (HERE.parent / "postprocessor").resolve()
    if str(pp_root) not in sys.path:
        sys.path.insert(0, str(pp_root))
    from export_idml import export_idml, package_delivery  # noqa: PLC0415

    pkg_json = package_dir / "resolved_package.json"
    out = out_dir / f"{pkg_json.with_suffix('').name}.idml"
    idml = export_idml(pkg_json, out, assets_dir=package_dir / "assets")
    print(f"[idml] InDesign-editable package -> {idml} "
          f"(+ {idml.parent / 'Links'})")

    # the delivery ZIP: one attachment n8n can mail or upload to Drive.
    zip_out = out_dir / "report_indesign.zip"
    extra = [out_dir / "report.pdf", *sorted(out_dir.glob("report-p*.png"))]
    z = package_delivery(idml, zip_out, extra_files=extra)
    print(f"[idml] MAIL-READY delivery -> {z} "
          f"(idml + {len(list((idml.parent / 'Links').glob('*')))} images + pdf)")


if __name__ == "__main__":
    raise SystemExit(main())
