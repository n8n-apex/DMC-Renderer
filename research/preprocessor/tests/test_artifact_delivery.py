"""Tests for the n8n outtake artifact delivery (US-2026-08-19).

The ship path uploads the finished PDF + editable IDML ZIP to a shared file
host and delivers their public URLs in the webhook payload, so n8n can
populate an Airtable row or email the files. Best-effort: a missing host, a
missing IDML, or an unreachable endpoint NEVER crashes the ship.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PREPROC = Path(__file__).resolve().parent.parent
if str(PREPROC) not in sys.path:
    sys.path.insert(0, str(PREPROC))

from stages.artifact_delivery import (  # noqa: E402
    ArtifactDelivery,
    upload_artifacts,
    _upload_one,
)


class _FakeResp:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body or {}
        self.text = ""

    def json(self):
        return self._body


class _FakeClient:
    """A post_fn-shaped client that records calls and returns canned responses."""

    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url, files):
        self.calls.append((url, files))
        if self.responses:
            return self.responses.pop(0)
        return _FakeResp(200, {"url": "/uploads/x.pdf"})


def _mk(tmp_path, name="x.pdf", content=b"data"):
    p = tmp_path / name
    p.write_bytes(content)
    return p


def test_upload_artifacts_uploads_pdf_and_zip_and_returns_urls(tmp_path):
    pdf = _mk(tmp_path, "report.pdf")
    z = _mk(tmp_path, "ApexReport_InDesign.zip")
    client = _FakeResp(200, {"url": "https://files.internal/uploads/y.pdf"})
    uploader = _FakeClient([client, client])
    d = upload_artifacts(
        pdf_path=pdf, idml_zip_path=z,
        upload_url="https://host/accept", public_base="https://files.internal",
        client=uploader,
    )
    assert len(uploader.calls) == 2
    assert d.pdf_url == "https://files.internal/uploads/y.pdf"
    assert d.idml_zip_url == "https://files.internal/uploads/y.pdf"
    assert d.local_paths == []


def test_upload_artifacts_relative_url_resolved_against_public_base(tmp_path):
    pdf = _mk(tmp_path, "report.pdf")
    client = _FakeClient([_FakeResp(200, {"url": "/dl/report.pdf"})])
    d = upload_artifacts(
        pdf_path=pdf, idml_zip_path=None,
        upload_url="https://host/accept", public_base="https://files.internal",
        client=client,
    )
    assert d.pdf_url == "https://files.internal/dl/report.pdf"


def test_upload_artifacts_no_host_keeps_local_paths(tmp_path):
    pdf = _mk(tmp_path, "report.pdf")
    z = _mk(tmp_path, "ApexReport_InDesign.zip")
    d = upload_artifacts(pdf_path=pdf, idml_zip_path=z, upload_url=None, public_base=None)
    assert d.pdf_url is None and d.idml_zip_url is None
    assert len(d.local_paths) == 2  # both kept as local fallback


def test_upload_artifacts_http_error_falls_back_to_local(tmp_path):
    pdf = _mk(tmp_path, "report.pdf")
    client = _FakeClient([_FakeResp(500), _FakeResp(404)])
    d = upload_artifacts(
        pdf_path=pdf, idml_zip_path=_mk(tmp_path, "x.zip"),
        upload_url="https://host", public_base="https://files",
        client=client,
    )
    assert d.pdf_url is None and d.idml_zip_url is None
    assert str(pdf) in d.local_paths
    assert d.errors


def test_upload_artifacts_missing_files_graceful(tmp_path):
    # a missing PDF (path doesn't exist) does not crash; the present one uploads
    client = _FakeClient([_FakeResp(200, {"url": "/dl/x.zip"})])
    d = upload_artifacts(
        pdf_path=tmp_path / "nope.pdf", idml_zip_path=_mk(tmp_path, "x.zip"),
        upload_url="https://host", public_base="https://files",
        client=client,
    )
    assert d.pdf_url is None
    assert d.idml_zip_url.endswith("/dl/x.zip")


def test_outcome_payload_includes_artifact_urls():
    """The webhook payload (outcome_payload) carries the deliverable URLs so n8n
    can fill an Airtable row / email the files."""
    from orchestrator import JobOutcome, outcome_payload
    outcome = JobOutcome(
        status="shipped",
        pdf_path=Path("/tmp/report.pdf"),
        gate=_FakeGate(),
        report={},
        idml_zip_path=Path("/tmp/ApexReport_InDesign.zip"),
        artifact_urls={"pdf": "https://files/internal/dl/report.pdf",
                       "idml_zip": "https://files/internal/dl/pkg.zip"},
    )
    payload = outcome_payload(outcome, "job-42")
    assert payload["pdf_path"] == "/tmp/report.pdf"
    assert payload["idml_zip_path"] == "/tmp/ApexReport_InDesign.zip"
    assert payload["artifact_urls"]["pdf"] is not None
    assert payload["artifact_urls"]["idml_zip"] is not None


class _FakeGate:
    clear_ratio = 1.0
    punch_list = []
    ship = True
