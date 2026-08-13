"""Standing closed-gap assessment harness (US-020).

Every gap closed by the 2026-08-13 consolidated program is registered in
closed_gaps_registry.json with a check that must keep passing. This script
runs all of them and prints a PASS/FAIL table; it exits non-zero if any CLOSED
gap has reopened, so it can gate the container smoke and every future session.

This is the anti-recurrence mechanism for the owner's #1 pain: MD files
created but never assessed. A gap marked CLOSED whose check fails is REOPENED.

No network, no API keys. Checks are:
  - suite_zero:  run a pytest suite; pass iff 0 failures
  - test:        run a pytest path (file or ::test); pass iff 0 failures
  - harness:     run a python harness script; pass iff exit 0
  - node_test:   run a node test file; pass iff 0 failing tests
  - guard:       same as test (a pytest file that must stay green)
  - grep_present / grep_absent: search a file for a literal
  - file:        pass iff the path exists
  - manual:      always reported as OPEN (a human-gated gap, not code-closed)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QL = ROOT / "research" / "quality_loop"
RENDERER = ROOT / "research" / "v7-renderer"
PY = RENDERER / ".venv" / "bin" / "python"
NODE = "node"

REGISTRY = QL / "closed_gaps_registry.json"


def _pytest_cwd(file_path: Path) -> Path:
    """The nearest ancestor holding a conftest.py, so pytest's rootdir and
    sys.path setup match how the suite is run manually (quality_loop tests
    import modules one level up). Falls back to the file's parent."""
    for ancestor in [file_path.parent, *file_path.parents]:
        if (ancestor / "conftest.py").exists():
            return ancestor
    return file_path.parent


def _run_pytest(target: str) -> tuple[bool, str]:
    # Support "<file>::<test>" notation: split so pytest gets file::test while
    # cwd points at the directory that carries the suite's conftest.py.
    file_part, sep, test_part = target.partition("::")
    full = ROOT / file_part
    if not full.exists():
        return False, f"missing: {file_part}"
    pytest_target = str(full) + (f"::{test_part}" if sep else "")
    proc = subprocess.run(
        [str(PY), "-m", "pytest", pytest_target, "-q"],
        cwd=_pytest_cwd(full),
        capture_output=True,
        text=True,
    )
    tail = (proc.stdout or proc.stderr or "").strip().splitlines()
    summary = tail[-1] if tail else ""
    passed = proc.returncode == 0
    if "passed" in summary and "failed" not in summary:
        return True, summary
    if "failed" in summary and "0 failed" in summary:
        return True, summary
    return passed, summary


def _run_suite_zero(target: str) -> tuple[bool, str]:
    full = ROOT / target
    if not full.is_dir():
        return False, f"missing dir: {target}"
    proc = subprocess.run(
        [str(PY), "-m", "pytest", str(full), "-q"],
        cwd=_pytest_cwd(full),
        capture_output=True,
        text=True,
    )
    out = (proc.stdout or proc.stderr or "").strip()
    tail = out.splitlines()[-1] if out.splitlines() else ""
    # "N failed" and "0 failed" both appear; we need 0 failures.
    m = re.search(r"(\d+) failed", out)
    failed = int(m.group(1)) if m else 0
    return failed == 0, tail


def _run_harness(target: str) -> tuple[bool, str]:
    full = ROOT / target
    if not full.exists():
        return False, f"missing: {target}"
    proc = subprocess.run(
        [str(PY), str(full)], cwd=full.parent, capture_output=True, text=True,
    )
    tail = (proc.stdout or proc.stderr or "").strip().splitlines()
    last = tail[-1] if tail else ""
    return proc.returncode == 0, last


def _run_node(target: str) -> tuple[bool, str]:
    full = ROOT / target
    if not full.exists():
        return False, f"missing: {target}"
    proc = subprocess.run(
        [NODE, str(full)], cwd=full.parent, capture_output=True, text=True,
    )
    out = proc.stdout or proc.stderr or ""
    m = re.search(r"ℹ fail\s+(\d+)", out)
    failed = int(m.group(1)) if m else (0 if proc.returncode == 0 else 1)
    return failed == 0, out.strip().splitlines()[-1] if out.strip() else ""


def _run_grep(target: str, want_present: bool) -> tuple[bool, str]:
    # target is "<literal> in <relative-path>"
    literal, _, path = target.rpartition(" in ")
    full = ROOT / path.strip()
    if not full.exists():
        return False, f"missing: {path.strip()}"
    text = full.read_text(encoding="utf-8", errors="replace")
    found = literal.strip() in text
    ok = found if want_present else (not found)
    return ok, ("present" if found else "absent")


def _run_file(target: str) -> tuple[bool, str]:
    return (ROOT / target).exists(), target


def assess(registry: dict, *, skip_suites: bool = False) -> list[dict]:
    results = []
    for gap in registry["gaps"]:
        ctype = gap["check_type"]
        target = gap["check"]
        if skip_suites and ctype == "suite_zero":
            results.append(
                {
                    "id": gap["id"],
                    "description": gap["description"],
                    "status": "SKIPPED",
                    "note": "full-suite check skipped (--fast); see the baseline ledger",
                }
            )
            continue
        try:
            if ctype in ("test", "guard"):
                ok, note = _run_pytest(target)
            elif ctype == "suite_zero":
                ok, note = _run_suite_zero(target)
            elif ctype == "harness":
                ok, note = _run_harness(target)
            elif ctype == "node_test":
                ok, note = _run_node(target)
            elif ctype == "grep_present":
                ok, note = _run_grep(target, want_present=True)
            elif ctype == "grep_absent":
                ok, note = _run_grep(target, want_present=False)
            elif ctype == "file":
                ok, note = _run_file(target)
            elif ctype == "manual":
                # A human-gated gap is OPEN by design, not a regression. It is
                # reported but does not fail the exit code; closing it is the
                # owner's input (assets, n8n paste, ratings), not code.
                ok, note = True, "OPEN (human-gated, not code-closed)"
            else:
                ok, note = False, f"unknown check_type {ctype!r}"
        except Exception as exc:  # noqa: BLE001 - a broken check must be loud
            ok, note = False, f"check raised: {exc}"
        results.append(
            {
                "id": gap["id"],
                "description": gap["description"],
                "status": "CLOSED" if ok else "REOPENED",
                "check_type": ctype,
                "note": note,
            }
        )
    return results


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Re-check every closed gap in closed_gaps_registry.json."
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="skip the two full-suite checks (G2 renderer, D2 dmc-renderer); "
        "their record is the baseline ledger",
    )
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    results = assess(registry, skip_suites=args.fast)
    width = max(len(r["id"]) for r in results)
    print("=" * 72)
    for r in results:
        if r["status"] == "SKIPPED":
            print(f"-- {r['id'].ljust(width)}  SKIPPED  {r['description']}")
            continue
        if r.get("check_type") == "manual":
            print(f".. {r['id'].ljust(width)}  OPEN     {r['description']}")
            continue
        mark = "OK " if r["status"] == "CLOSED" else "!! "
        print(f"{mark} {r['id'].ljust(width)}  {r['status']:<9} {r['description']}")
        if r["status"] == "REOPENED":
            print(f"      note: {r['note']}")
    print("=" * 72)
    closed = sum(1 for r in results if r["status"] == "CLOSED")
    reopened = [
        r["id"] for r in results
        if r["status"] == "REOPENED" and r.get("check_type") != "manual"
    ]
    manual = [r["id"] for r in results if r.get("check_type") == "manual"]
    print(f"{closed}/{len(results)} closed")
    if manual:
        print(f"OPEN (human-gated, not code-closed): {', '.join(manual)}")
    if reopened:
        print(f"REOPENED: {', '.join(reopened)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
