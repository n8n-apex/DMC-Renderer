"""Tests for the error taxonomy + top-level handlers."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main
from errors import ExternalServiceError, InputError, PreprocessorError, error_payload


def test_error_payload_for_preprocessor_error() -> None:
    p = error_payload(InputError("bad field", field="brand_hex_dark"), job_id="J1")
    assert p["status"] == "error"
    assert p["code"] == "input_error"
    assert p["detail"] == "bad field"
    assert p["context"] == {"field": "brand_hex_dark"}
    assert p["job_id"] == "J1"


def test_error_payload_for_unexpected() -> None:
    p = error_payload(RuntimeError("surprise"))
    assert p["code"] == "unexpected_error"
    assert p["detail"] == "surprise"


def test_subclass_codes_and_status() -> None:
    assert InputError().http_status == 422
    assert ExternalServiceError().http_status == 502
    assert issubclass(InputError, PreprocessorError)


def test_unexpected_exception_in_render_returns_structured_500(monkeypatch) -> None:
    def boom(_request):
        raise RuntimeError("forced failure")

    monkeypatch.setattr(main, "validate_and_resolve_brand_tokens", boom)
    client = TestClient(main.app, raise_server_exceptions=False)
    payload = {
        "record_id": "RID",
        "client": {
            "name": "x", "company": "x", "website_url": "https://x.test",
            "brand_hex_dark": "#111", "brand_hex_light": "#eee", "brand_hex_accent": "#0af",
        },
        "report_json": {"meta": {"client_slug": "x", "report_id": "RID", "page_count_target": 1}, "pages": []},
        "image_manifest": {"images": []},
    }
    resp = client.post("/render", json=payload)
    assert resp.status_code == 500
    body = resp.json()
    assert body["status"] == "error"
    assert body["code"] == "unexpected_error"
    assert body["job_id"]  # correlation id flows middleware → request.state → payload
