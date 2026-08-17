"""Error taxonomy for the pre-processor + a structured payload for the
top-level handler, so /render never returns a bare 500. No client literal.
"""
from __future__ import annotations

from typing import Optional


class PreprocessorError(Exception):
    """Base. `code` is a stable machine string; `detail` is human text;
    `context` carries structured key/values for logs + the response.
    """

    code = "preprocessor_error"
    http_status = 500

    def __init__(self, detail: str = "", **context):
        super().__init__(detail or self.code)
        self.detail = detail
        self.context = context


class InputError(PreprocessorError):
    code = "input_error"
    http_status = 422


class AssetSourceError(PreprocessorError):
    code = "asset_source_error"
    http_status = 502


class ExternalServiceError(PreprocessorError):
    code = "external_service_error"
    http_status = 502


def error_payload(exc: Exception, *, job_id: Optional[str] = None) -> dict:
    if isinstance(exc, PreprocessorError):
        return {
            "status": "error",
            "code": exc.code,
            "detail": exc.detail,
            "context": exc.context,
            "job_id": job_id,
        }
    return {
        "status": "error",
        "code": "unexpected_error",
        "detail": str(exc),
        "job_id": job_id,
    }
