"""Smoke tests for logging helpers and exception handler."""

from __future__ import annotations

import asyncio
import json
import logging

from starlette.requests import Request

from ade_api.common.exceptions import unhandled_exception_handler
from ade_api.common.logging import (
    ConsoleLogFormatter,
    bind_request_context,
    clear_request_context,
    log_context,
    setup_logging,
)
from ade_api.settings import Settings


class _CaptureHandler(logging.Handler):
    """Handler that stores log records and formatted strings."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []
        self.formatted: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self.records.append(record)
        self.formatted.append(msg)


def test_log_context_includes_correlation_and_fields():
    setup_logging(Settings(logging_level="DEBUG"))
    handler = _CaptureHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(ConsoleLogFormatter())
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        bind_request_context("cid-123")
        logger = logging.getLogger("test.logging")
        logger.info(
            "test.request",
            extra=log_context(path="/foo", status_code=200, workspace_id="ws_1"),
        )

        assert handler.records, "Log record not captured"
        record = handler.records[-1]
        assert getattr(record, "correlation_id", None) == "cid-123"
        assert getattr(record, "path", "") == "/foo"
        assert getattr(record, "status_code", None) == 200
        assert getattr(record, "workspace_id", None) == "ws_1"
    finally:
        clear_request_context()
        root.removeHandler(handler)


def test_unhandled_exception_handler_logs_with_correlation():
    setup_logging(Settings(logging_level="DEBUG"))
    handler = _CaptureHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(ConsoleLogFormatter())
    root = logging.getLogger()
    for name in ("ade_api", "ade_api.errors"):
        logger = logging.getLogger(name)
        logger.disabled = False
        logger.setLevel(logging.DEBUG)
        logger.propagate = True
    error_logger = logging.getLogger("ade_api.errors")
    root.addHandler(handler)
    error_logger.addHandler(handler)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/boom",
        "headers": [],
        "scheme": "http",
        "server": ("testserver", 80),
    }
    request = Request(scope)
    try:
        bind_request_context("exc-1")
        error_logger.error("probe.error")
        assert any(rec.getMessage() == "probe.error" for rec in handler.records)
        handler.records.clear()

        response = asyncio.run(unhandled_exception_handler(request=request, exc=RuntimeError("boom")))
        assert response.status_code == 500
        payload = json.loads(response.body.decode())
        assert payload["type"] == "internal_error"
        assert payload["title"] == "Internal server error"
        assert payload["status"] == 500
        assert payload["detail"] == "Internal server error"
        assert payload["instance"] == "/boom"

        error_logs = [record for record in handler.records if record.name == "ade_api.errors"]
        assert error_logs, "Unhandled exception log not captured"
        record = error_logs[-1]
        assert getattr(record, "correlation_id", None) == "exc-1"
        assert record.exc_info is not None
        assert "unhandled_exception" in record.getMessage()
    finally:
        clear_request_context()
        root.removeHandler(handler)
        error_logger.removeHandler(handler)
