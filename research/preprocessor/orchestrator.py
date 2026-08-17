"""Orchestrator -- the autonomy-spine core (Phase 4).

The preprocessor stages have already produced a package directory. This module
runs the rest of the spine: invoke the renderer + convergence loop via an
injectable ``RenderRunner`` (a subprocess to the renderer environment in
production; a fake in tests), apply the quality GATE against Richard's
references, and return a ship-or-escalate ``JobOutcome`` (optionally firing a
callback, e.g. the n8n webhook).

It is the Brain scoped to production. Deterministic, brand-agnostic, and
runner-agnostic: the ``RenderRunner`` protocol lets a job-queue worker replace
the subprocess later with no change here.

Policy (the user's decision): autonomous by default, human by exception. The deck
SHIPS only when it clears the bar AND there is no outstanding HUMAN-owned blocker
(an asset/content gap the renderer cannot fix). Otherwise it ESCALATES with the
by-owner punch-list so a human supplies the missing input.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Protocol


@dataclass
class RenderResult:
    """What a RenderRunner returns: the shipped PDF and the convergence report."""

    pdf_path: Path
    convergence_report: dict


class RenderRunner(Protocol):
    """Render + grade a package, returning the PDF + convergence report.

    The production implementation shells out to the renderer environment
    (chromium + Ghostscript + the quality loop); tests pass a fake.
    """

    def run(self, package_dir: Path, out_dir: Path) -> RenderResult:
        ...


@dataclass
class GateDecision:
    """The quality-gate verdict for a graded deck."""

    ship: bool
    clear_ratio: float
    punch_list: dict  # flags_by_owner when escalating; {} when shipping


# The owner classes whose flags require a HUMAN to act (the renderer cannot fix
# them): a missing/weak asset, or a content/copy gap. A residual *renderer* flag
# is a capability backlog item, not a ship blocker on its own.
_HUMAN_OWNERS = ("asset_gen", "preprocessor")


def evaluate_gate(report: dict, *, min_clear_ratio: float = 1.0) -> GateDecision:
    """Decide ship vs escalate from a convergence report.

    Ships iff the cleared ratio meets ``min_clear_ratio`` (default: every page
    cleared) AND there is no outstanding human-owned blocker (asset_gen /
    preprocessor flag). Both bars are config values so strictness is tunable
    without code changes. On escalation the punch-list is the full by-owner flag
    set so the human sees exactly what to supply.
    """
    total = int(report.get("total", 0) or 0)
    cleared = int(report.get("cleared_count", 0) or 0)
    clear_ratio = (cleared / total) if total else 0.0

    flags_by_owner = report.get("flags_by_owner", {}) or {}
    human_blockers: list = []
    for owner in _HUMAN_OWNERS:
        human_blockers.extend(flags_by_owner.get(owner) or [])

    ship = (clear_ratio >= min_clear_ratio) and not human_blockers
    return GateDecision(
        ship=ship,
        clear_ratio=clear_ratio,
        punch_list={} if ship else flags_by_owner,
    )


@dataclass
class JobOutcome:
    """The result of a report job: shipped (with the PDF) or escalated (punch-list)."""

    status: str  # 'shipped' | 'escalated'
    pdf_path: Optional[Path]
    gate: GateDecision
    report: dict


def run_report_job(
    package_dir: Path | str,
    out_dir: Path | str,
    *,
    runner: RenderRunner,
    min_clear_ratio: float = 1.0,
    callback: Optional[Callable[[JobOutcome], Any]] = None,
) -> JobOutcome:
    """Render+grade the already-built package, gate it, and return the outcome.

    ``callback`` (e.g. the n8n webhook poster) is invoked with the JobOutcome when
    provided -- the single place the result leaves the system.
    """
    package_dir = Path(package_dir)
    out_dir = Path(out_dir)

    result = runner.run(package_dir, out_dir)
    decision = evaluate_gate(result.convergence_report, min_clear_ratio=min_clear_ratio)

    outcome = JobOutcome(
        status="shipped" if decision.ship else "escalated",
        pdf_path=result.pdf_path,
        gate=decision,
        report=result.convergence_report,
    )
    if callback is not None:
        callback(outcome)
    return outcome


# --------------------------------------------------------------------------- #
# Delivery (the webhook side -- kept here so it is testable with no FastAPI).
# --------------------------------------------------------------------------- #
def outcome_payload(outcome: JobOutcome, job_id: str) -> dict:
    """The JSON payload delivered to the webhook (n8n) describing a finished job."""
    return {
        "job_id": job_id,
        "status": outcome.status,
        "clear_ratio": outcome.gate.clear_ratio,
        "pdf_path": str(outcome.pdf_path) if outcome.pdf_path else None,
        "punch_list": outcome.gate.punch_list,
        "deck_reward": outcome.report.get("deck_reward"),
        "cleared_count": outcome.report.get("cleared_count"),
        "total": outcome.report.get("total"),
    }


def deliver_outcome(
    outcome: JobOutcome,
    webhook: Optional[str],
    job_id: str,
    *,
    post_fn: Callable[[str, dict], Any],
) -> None:
    """POST the outcome payload to the webhook (n8n) via ``post_fn``. No-op when no
    webhook is configured (the caller persists/handles it otherwise)."""
    if not webhook:
        return
    post_fn(webhook, outcome_payload(outcome, job_id))


def run_and_deliver(
    package_dir: Path | str,
    out_dir: Path | str,
    webhook: Optional[str],
    job_id: str,
    *,
    runner: RenderRunner,
    post_fn: Callable[[str, dict], Any],
    min_clear_ratio: float = 1.0,
) -> JobOutcome:
    """Run the job and deliver its outcome to the webhook -- the single call the
    background task makes. Returns the JobOutcome (also delivered)."""
    return run_report_job(
        package_dir, out_dir, runner=runner, min_clear_ratio=min_clear_ratio,
        callback=lambda o: deliver_outcome(o, webhook, job_id, post_fn=post_fn),
    )


# Renderer environment: the v7-renderer subprocess (its own venv + Chromium +
# Ghostscript + the quality loop). Resolved relative to this file.
_RENDERER_DIR = Path(__file__).resolve().parents[1] / "v7-renderer"
_RENDERER_PY = _RENDERER_DIR / ".venv" / "bin" / "python"


@dataclass
class SubprocessRenderRunner:
    """Production RenderRunner: shells out to the renderer environment to render +
    grade + compose a package, then reads back the shipped PDF + convergence
    report. A hard timeout + one retry means a renderer crash ESCALATES cleanly
    (raises) rather than hanging -- the long-process crash guardrail. The ship
    engine is pinned to chromium (the weasyprint function default is a footgun,
    addition A).
    """

    use_vis: bool = True
    converge_pages: int = 0  # 0 = all pages
    timeout_s: float = 1800.0
    renderer_dir: Path = _RENDERER_DIR
    python_bin: Path = _RENDERER_PY

    def _build_cmd(self, package_dir: Path, out_dir: Path) -> list[str]:
        cmd = [
            str(self.python_bin), str(self.renderer_dir / "render.py"),
            "--package-dir", str(package_dir),
            "--output-dir", str(out_dir),
            "--engine", "chromium",
        ]
        if not self.use_vis:
            cmd.append("--no-converge-vis")
        if self.converge_pages > 0:
            cmd += ["--converge-pages", str(self.converge_pages)]
        return cmd

    def run(self, package_dir: Path, out_dir: Path) -> RenderResult:
        package_dir = Path(package_dir)
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd = self._build_cmd(package_dir, out_dir)
        # weasyprint (the legacy engine import) needs the homebrew libs on macOS;
        # inherit the caller's value if set, else the conventional default.
        env = dict(os.environ)
        env.setdefault("DYLD_FALLBACK_LIBRARY_PATH", "/opt/homebrew/lib")

        last_err: Optional[Exception] = None
        for _ in range(2):  # one retry: a transient crash must not fail silently
            try:
                subprocess.run(
                    cmd, cwd=str(self.renderer_dir), env=env,
                    timeout=self.timeout_s, check=True,
                    capture_output=True, text=True,
                )
                last_err = None
                break
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                last_err = exc
        if last_err is not None:
            raise RuntimeError(f"renderer subprocess failed after retry: {last_err}")

        pdf_path = out_dir / "report.pdf"
        report_path = out_dir / "converge" / "convergence_report.json"
        report = (
            json.loads(report_path.read_text(encoding="utf-8"))
            if report_path.exists() else {}
        )
        return RenderResult(pdf_path=pdf_path, convergence_report=report)
