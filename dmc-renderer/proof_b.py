"""Proof B — reproduce the apex deck through the full v3 wake-up loop.

The USER's framing: the full system reads report.json, picks the reference,
understands page layouts, creates a direction, generates imagery, then builds
each page and QA-corrects it before the next. That loop EXISTS as three wired
halves (v2 preprocessor, v2 renderer Stage 9 convergence, and the v3
build_and_render_v3 pipeline). Proof B proves the v3 half now consumes a real
apex report end-to-end, and surfaces HONESTLY whatever it cannot yet do.

This harness is that proof, runnable:

    python dmc-renderer/proof_b.py [--out /tmp/proof_b]

It drives the REAL apex payload (``fixtures/apex_consulting_payload.json``)
through ``build_and_render_v3`` and writes an honest, machine-readable
``proof_b_report.json``:

    {
      "verdict": "precomposition_cleared" | "blocked",
      "page_count_target": 20,
      "profile": {"derived": true, "source": "legacy_report_to_editorial_brief"},
      "evidence": {"claims_derived": true, "ungrounded_numeric": <n>},
      "blockers": [{"code": str, "owner": "asset_gen"|"preprocessor"|...}],
      "deterministic": {"run1": <hash>, "run2": <hash>},
      "reference": {"selection": "supabase_sql"|"legacy_index", "st_type_pages": {...}}
    }

BRAND-AGNOSTIC: the harness takes an envelope path; apex is a default FIXTURE
argument, never a literal in logic. GUARDS: no fabricated figure/person/photo;
a missing case portrait is a real asset_gen flag, never a fake; the reference
selection never fakes a match.
"""

from __future__ import annotations

import argparse
import json
import hashlib
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
# v3 imports need the research roots (mirrors build_v3's dependency roots).
_RESEARCH = HERE.parent / "research"
for _root in (_RESEARCH, _RESEARCH / "preprocessor", _RESEARCH / "v7-renderer"):
    s = str(_root.resolve())
    if s not in sys.path:
        sys.path.insert(0, s)


def _profiles() -> None:
    os.environ.setdefault("FAL_KEY", "must-not-be-used")
    os.environ.setdefault("OPENROUTER_API_KEY", "must-not-be-used")


def _stable_hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]


def _normalize_failures(exc: Exception) -> list[dict]:
    failures = getattr(exc, "failures", ()) or ()
    out = []
    for f in failures:
        out.append(
            {
                "code": getattr(f, "code", None) or "",
                "owner": getattr(f, "owner_stage", "other"),
                "detail": str(getattr(f, "detail", ""))[:140],
            }
        )
    return out


def run_stage9_qa(
    package_dir: Path,
    *,
    out_dir: Path,
    use_vis: bool = True,
    max_iterations: int = 4,
    page_indices: list[int] | None = None,
) -> dict:
    """Stage 9 (the v2 QA half): reference-grounded per-page convergence loop.

    Grading against the references (vision ON by default), applying the
    conductor's in-renderer knobs, composing the fix-merged deck, and writing
    ``convergence_report.{json,txt}``. This is the SAME stage render.py runs
    by default (we usually skip it with ``--fast``); the harness calls it
    explicitly so Proof B exercises the wake-up loop as its QA half.
    """
    ql_root = _RESEARCH / "quality_loop"
    for _root in (ql_root,):
        s = str(_root.resolve())
        if s not in sys.path:
            sys.path.insert(0, s)
    # The renderer transitioned to chromium which (via WeasyPrint/ImageMagick
    # deps) needs the Homebrew fallback lib path on macOS; the harness process
    # often lacks it (only render.py's shell exports it). Set it here too so
    # the in-process Stage 9 renders identically to the CLI.
    os.environ.setdefault("DYLD_FALLBACK_LIBRARY_PATH", "/opt/homebrew/lib:/usr/local/lib")
    from stage_converge import run_stage  # noqa: PLC0415

    return run_stage(
        str(package_dir),
        out_dir,
        use_vis=use_vis,
        max_iterations=max_iterations,
        page_indices=page_indices,
        compose=True,
    )


def run_proof_b(
    envelope_path: Path,
    *,
    out_root: Path,
    client_assets_root: Path | None = None,
    hermetic: bool = True,
    v2_package_dir: Path | None = None,
    stage9_use_vis: bool = False,
    stage9_max_iter: int = 2,
    stage9_pages: list[int] | None = None,
) -> dict:
    """Drive the real apex envelope through v3; return an honest report."""
    _profiles()
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    if client_assets_root is not None:
        os.environ["DMC_CLIENT_ASSETS_DIR"] = str(client_assets_root)

    from build_v3 import ReleaseContextV3, build_and_render_v3

    out_root.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "envelope": str(envelope_path),
        "page_count_target": (envelope.get("payload") or {}).get("meta", {}).get(
            "page_count_target"
        ),
        "images_present": len(envelope.get("images") or {}),
        "claims_in_envelope": len(envelope.get("claims") or ()),
        "sources_in_envelope": len(envelope.get("sources") or ()),
    }

    # Evidence seam: a raw live envelope carries no claims; the precomposition
    # must derive them from the report's own copy (verbatim spans). Prove it.
    from stages.derive_claims_v3 import derive_evidence
    from stages.build_source_ledger import build_source_ledger

    derived = derive_evidence(
        {"report_json": envelope.get("payload")},
        captured_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        language=str((envelope.get("payload") or {}).get("meta", {}).get("lang", "de")),
    )
    ledger = build_source_ledger(
        {
            "report_json": envelope.get("payload"),
            "sources": tuple(derived.sources),
            "claims": tuple(derived.claims),
        }
    )
    ungrounded = [
        f for f in ledger.grounding_failures
        if getattr(f, "code", "") == "ungrounded_numeric_candidate"
    ]
    report["evidence"] = {
        "claims_derived": len(derived.claims),
        "sources_derived": len(derived.sources),
        "devices_derived": len(derived.devices),
        "ungrounded_numeric": len(ungrounded),
    }

    # Reference selection seam: deterministic per-slot st_type (never vision,
    # never fake). Uses the legacy index when no Supabase DSN (hermetic).
    try:
        from stages.director import select_references  # async

        dsn = os.environ.get("SUPABASE_POOLER_URL")
        import asyncio

        picked = asyncio.run(select_references(dsn, "ST-07A", k=1))
        report["reference"] = {
            "selection": "supabase_sql" if dsn else "legacy_index",
            "sample_reference_count": len(picked),
        }
    except Exception as exc:  # noqa: BLE001 - reference pick is best-effort
        report["reference"] = {"selection": "not_applicable", "detail": str(exc)[:120]}

    # The v3 build itself. Deterministic when hermetic (no external gen).
    # G2 (bank unification): derive the v2 banker's per-face decisions and
    # pass them as the composition_plan_override so the v3 plan IS the bank
    # plan (the seam Proof A left off). Proven by a deterministic hash.
    hashes = []
    release_state = None
    verdict = "blocked"
    blockers: list[dict] = []
    override = None
    override_hash = None
    from stages.plan_editorial_v3 import legacy_report_to_editorial_brief  # noqa: PLC0415
    from bank_override import bank_to_v3_override, override_stable_hash  # noqa: PLC0415

    brief = legacy_report_to_editorial_brief(envelope.get("payload"))
    faces = brief["faces"]
    override = bank_to_v3_override(envelope.get("payload", {}).get("pages") or [], faces)
    override_hash = override_stable_hash(override)
    report["bank_unification"] = {
        "override_hash": override_hash,
        "pages": len(envelope.get("payload", {}).get("pages") or []),
        "faces": len(faces),
        "decisions": len(override["decisions"]),
    }

    runs_dir = out_root / "runs"
    for attempt in (1, 2) if hermetic else (1,):
        run_dir = runs_dir / f"run-{attempt}"
        try:
            result = build_and_render_v3(
                envelope,
                output_dir=run_dir,
                cleanup=False,
                release_context=ReleaseContextV3(allow_synthetic_assets=hermetic),
                composition_plan_override=override,
            )
        except Exception as exc:  # noqa: BLE001 - blocked is the honest outcome
            failures = _normalize_failures(exc)
            hashes.append(_stable_hash(failures))
            if attempt == 1:
                blockers = failures or [
                    {"code": type(exc).__name__, "owner": "other", "detail": str(exc)[:140]}
                ]
            continue
        pdf = result.get("pdf_path")
        if pdf and Path(pdf).exists():
            hashes.append(
                hashlib.sha256(Path(pdf).read_bytes()).hexdigest()[:16]
            )
        release_state = result.get("release_state")
        blockers = [{"code": str(f)[:140], "owner": "gate"} for f in result.get("failures", ())]
        verdict = "reproduced" if release_state else "blocked"

    report["verdict"] = verdict
    report["release_state"] = release_state
    report["blockers"] = blockers
    report["deterministic"] = {
        "runs": len(hashes),
        "same_hash": len(set(hashes)) <= 1,
        "hashes": hashes,
    }

    # Stage 9 (the QA half): run the reference-grounded per-page convergence
    # loop over a v2 package (the shipped deck) and fold its report in. This
    # is the "review each page until correct" the full loop is supposed to do.
    if v2_package_dir is not None:
        stage9_out = out_root / "stage9"
        try:
            stage9 = run_stage9_qa(
                v2_package_dir,
                out_dir=stage9_out,
                use_vis=stage9_use_vis,
                max_iterations=stage9_max_iter,
                page_indices=stage9_pages,
            )
            report["stage9"] = {
                "ran": True,
                "cleared": stage9.get("cleared_count"),
                "total": stage9.get("total"),
                "deck_cleared": stage9.get("deck_cleared"),
                "deck_reward": round(stage9.get("deck_reward", 0.0), 2),
                "flags_by_owner": stage9.get("flags_by_owner"),
                "composed_pdf": stage9.get("composed_pdf"),
                "compose_rejected": stage9.get("compose_rejected"),
                "report": str(stage9_out / "convergence_report.json"),
            }
        except Exception as exc:  # noqa: BLE001 - QA is best-effort, never crash
            report["stage9"] = {"ran": False, "detail": str(exc)[:160]}

    (out_root / "proof_b_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Proof B v3 full-loop harness")
    parser.add_argument("--envelope", default=str(HERE / "fixtures" / "apex_consulting_payload.json"))
    parser.add_argument("--out", default="/tmp/proof_b")
    parser.add_argument("--client-assets", default=None)
    parser.add_argument("--no-hermetic", action="store_true")
    parser.add_argument("--v2-package", default=None,
                        help="run Stage 9 (per-page converge) over this v2 deck package")
    parser.add_argument("--stage9-vis", action="store_true",
                        help="Stage 9 uses the real vision client (default: deterministic)")
    parser.add_argument("--stage9-max-iter", type=int, default=2)
    parser.add_argument("--stage9-pages", type=str, default=None,
                        help="comma list of page indices for Stage 9 (default: all)")
    args = parser.parse_args()
    report = run_proof_b(
        Path(args.envelope),
        out_root=Path(args.out),
        client_assets_root=Path(args.client_assets) if args.client_assets else None,
        hermetic=not args.no_hermetic,
        v2_package_dir=Path(args.v2_package) if args.v2_package else None,
        stage9_use_vis=args.stage9_vis,
        stage9_max_iter=args.stage9_max_iter,
        stage9_pages=[int(x) for x in args.stage9_pages.split(",")] if args.stage9_pages else None,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()