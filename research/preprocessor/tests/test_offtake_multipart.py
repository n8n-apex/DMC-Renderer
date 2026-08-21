"""Offtake wiring (approach A): the ship background task POSTs the finished
PDF + the editable IDML ZIP to the n8n webhook as MULTIPART FILES, not URL
strings. A local HTTP server captures the actual multipart body so we prove
the bytes cross the wire (the piece most likely to silently break).

Contract: payload carries `pdf_path` + `idml_zip_path` (local paths); the
delivery poster opens both and attaches them as `pdf` / `idml` form fields
with a JSON `payload` field of metadata.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest


class _Capture:
    def __init__(self):
        self.body = b""
        self.content_type = ""


def _server(capture: _Capture):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            capture.body = self.rfile.read(length)
            capture.content_type = self.headers.get("Content-Type", "")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


def test_post_webhook_sync_attaches_pdf_and_idml(tmp_path, monkeypatch):
    from main import _post_webhook_sync

    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-REAL-BYTES" * 10)
    idml = tmp_path / "report_indesign.zip"
    idml.write_bytes(b"PK\x03\x04-REAL-ZIP" * 10)

    capture = _Capture()
    srv = _server(capture)
    url = f"http://127.0.0.1:{srv.server_address[1]}/webhook/renderer-output"
    payload = {
        "job_id": "j-1",
        "status": "shipped",
        "pdf_path": str(pdf),
        "idml_zip_path": str(idml),
    }
    try:
        _post_webhook_sync(url, payload)
    finally:
        srv.shutdown()

    assert capture.body, "no multipart body sent"
    assert "multipart/form-data" in capture.content_type
    body = capture.body.decode("latin-1")
    # both files were attached
    assert "name=\"pdf\"" in body
    assert "name=\"idml\"" in body
    # the PDF's bytes are in the body (not a reference path/URL)
    assert b"%PDF-REAL-BYTES" in capture.body
    assert "--REAL-ZIP" in body or "REAL-ZIP" in body
    # the JSON metadata field is present
    assert '"job_id": "j-1"' in body or "j-1" in body


def test_post_webhook_sync_falls_back_to_json_when_no_files(tmp_path, monkeypatch):
    from main import _post_webhook_sync

    capture = _Capture()
    srv = _server(capture)
    url = f"http://127.0.0.1:{srv.server_address[1]}/webhook/renderer-output"
    try:
        _post_webhook_sync(url, {"job_id": "j-2", "status": "shipped",
                                 "pdf_path": "/nope/x.pdf"})
    finally:
        srv.shutdown()

    assert "multipart/form-data" not in capture.content_type
    assert "application/json" in capture.content_type
    assert "j-2" in capture.body.decode("utf-8", "replace")
