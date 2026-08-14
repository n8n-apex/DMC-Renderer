"""Tests for the autonomy-spine orchestrator core (Phase 4).

The orchestrator is the Brain scoped to production: the preprocessor stages have
already produced a package; ``run_report_job`` runs the renderer + convergence via
an injectable ``RenderRunner`` (a subprocess to the renderer env in production, a
fake here), applies the quality GATE against Richard's references, and returns a
ship-or-escalate ``JobOutcome``. Pure logic -> fully unit-testable with no render.
"""
from __future__ import annotations

from pathlib import Path

from orchestrator import (
    GateDecision,
    JobOutcome,
    RenderResult,
    evaluate_gate,
    run_report_job,
)


def _report(*, cleared, total, asset_gen=None, preprocessor=None, renderer=None):
    return {
        "deck_cleared": cleared == total,
        "cleared_count": cleared,
        "total": total,
        "deck_reward": 0.0,
        "pages": [],
        "flags_by_owner": {
            "renderer": renderer or [],
            "preprocessor": preprocessor or [],
            "asset_gen": asset_gen or [],
            "other": [],
        },
    }


def test_gate_ships_when_all_cleared_no_blockers():
    d = evaluate_gate(_report(cleared=20, total=20))
    assert d.ship is True
    assert d.clear_ratio == 1.0
    assert d.punch_list == {}


def test_gate_escalates_on_human_owned_blocker_even_if_cleared():
    # A cleared deck with an outstanding asset/content gap a HUMAN must supply
    # still escalates (autonomous by default, human by exception).
    rep = _report(cleared=20, total=20, asset_gen=[{"flag": "N01 missing photo"}])
    d = evaluate_gate(rep)
    assert d.ship is False
    assert d.punch_list["asset_gen"]


def test_gate_escalates_when_not_all_cleared():
    d = evaluate_gate(_report(cleared=18, total=20))
    assert d.ship is False
    assert d.clear_ratio == 0.9


class _FakeRunner:
    def __init__(self, report, pdf):
        self._report = report
        self._pdf = pdf
        self.calls: list[tuple[Path, Path]] = []

    def run(self, package_dir, out_dir):
        self.calls.append((Path(package_dir), Path(out_dir)))
        return RenderResult(pdf_path=Path(self._pdf), convergence_report=self._report)


def test_run_report_job_ships(tmp_path):
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF")
    runner = _FakeRunner(_report(cleared=20, total=20), pdf)
    out = run_report_job(tmp_path / "pkg", tmp_path / "out", runner=runner)
    assert isinstance(out, JobOutcome)
    assert out.status == "shipped"
    assert out.pdf_path == pdf
    assert runner.calls == [(tmp_path / "pkg", tmp_path / "out")]


def test_run_report_job_escalates_with_punch_list(tmp_path):
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF")
    rep = _report(cleared=17, total=20,
                  asset_gen=[{"flag": "N01"}], preprocessor=[{"flag": "N15"}])
    runner = _FakeRunner(rep, pdf)
    out = run_report_job(tmp_path / "pkg", tmp_path / "out", runner=runner)
    assert out.status == "escalated"
    assert out.gate.punch_list["asset_gen"]
    assert out.gate.punch_list["preprocessor"]


def test_run_report_job_fires_callback_with_outcome(tmp_path):
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF")
    runner = _FakeRunner(_report(cleared=20, total=20), pdf)
    seen: list[JobOutcome] = []
    out = run_report_job(tmp_path / "pkg", tmp_path / "out",
                         runner=runner, callback=seen.append)
    assert seen == [out]
    assert seen[0].status == "shipped"


def test_subprocess_runner_builds_pinned_chromium_command(tmp_path):
    from orchestrator import SubprocessRenderRunner
    r = SubprocessRenderRunner(use_vis=False, converge_pages=2)
    cmd = r._build_cmd(tmp_path / "pkg", tmp_path / "out")
    assert cmd[1].endswith("render.py")
    assert "--package-dir" in cmd and str(tmp_path / "pkg") in cmd
    assert "--output-dir" in cmd and str(tmp_path / "out") in cmd
    # The ship engine is pinned to chromium (addition A), never the weasyprint default.
    assert "--engine" in cmd and "chromium" in cmd
    assert "--no-converge-vis" in cmd  # use_vis=False
    assert "--converge-pages" in cmd and "2" in cmd


# --- delivery (the webhook side, kept here so it is testable with no FastAPI) -- #
def test_outcome_payload_shape(tmp_path):
    from orchestrator import outcome_payload
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(b"%PDF")
    runner = _FakeRunner(_report(cleared=18, total=20,
                                 asset_gen=[{"flag": "N01 missing photo"}]), pdf)
    out = run_report_job(tmp_path / "pkg", tmp_path / "out", runner=runner)
    p = outcome_payload(out, "job-123")
    assert p["job_id"] == "job-123"
    assert p["status"] == "escalated"
    assert p["clear_ratio"] == 0.9
    assert p["pdf_path"] == str(pdf)
    assert p["punch_list"]["asset_gen"]


def test_deliver_outcome_posts_payload(tmp_path):
    from orchestrator import deliver_outcome
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(b"%PDF")
    runner = _FakeRunner(_report(cleared=20, total=20), pdf)
    out = run_report_job(tmp_path / "pkg", tmp_path / "out", runner=runner)
    posted: list[tuple] = []
    deliver_outcome(out, "http://hook", "job-1",
                    post_fn=lambda url, payload: posted.append((url, payload)))
    assert posted and posted[0][0] == "http://hook"
    assert posted[0][1]["status"] == "shipped"


def test_deliver_outcome_no_webhook_is_noop(tmp_path):
    from orchestrator import deliver_outcome
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(b"%PDF")
    runner = _FakeRunner(_report(cleared=20, total=20), pdf)
    out = run_report_job(tmp_path / "pkg", tmp_path / "out", runner=runner)
    posted: list = []
    deliver_outcome(out, None, "job-1", post_fn=lambda url, payload: posted.append(1))
    assert posted == []


def test_run_and_deliver_runs_then_delivers(tmp_path):
    from orchestrator import run_and_deliver
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(b"%PDF")
    runner = _FakeRunner(_report(cleared=20, total=20), pdf)
    posted: list = []
    out = run_and_deliver(tmp_path / "pkg", tmp_path / "out", "http://hook", "job-9",
                          runner=runner, post_fn=lambda u, p: posted.append(p))
    assert out.status == "shipped"
    assert posted and posted[0]["job_id"] == "job-9"
