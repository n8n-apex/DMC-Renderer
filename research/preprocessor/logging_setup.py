"""structlog configuration + a job/correlation id bound through every log
line of a render or onboard job. Pure infrastructure — no client literal.
"""
from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Optional

import structlog

_job_id: ContextVar[Optional[str]] = ContextVar("job_id", default=None)
_configured = False


def _add_job_id(logger, method_name, event_dict):
    """structlog processor: merge the bound job id into every event."""
    jid = _job_id.get()
    if jid is not None:
        event_dict["job_id"] = jid
    return event_dict


def configure_logging(*, json_logs: bool = True) -> None:
    """Idempotent process-wide structlog setup."""
    global _configured
    if _configured:
        return
    renderer = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _add_job_id,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def bind_job_id(job_id: str) -> None:
    _job_id.set(job_id)


def clear_job_id() -> None:
    _job_id.set(None)


def get_logger(name: Optional[str] = None):
    return structlog.get_logger(name)
