"""Smoke tests for logging helpers and exception handler."""

from __future__ import annotations

import json
import logging

from starlette.requests import Request

from ade_api.common.exceptions import unhandled_exception_handler
from ade_api.common.logging import (
    ConsoleLogFormatter,
    JsonLogFormatter,
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
    setup_logging(
        Settings(
            _env_file=None,
            log_level="DEBUG",
            database_url="postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable",
            blob_container="ade-test",
            blob_connection_string="UseDevelopmentStorage=true",
            secret_key="test-secret-key-for-tests-please-change",
        )
    )
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
    setup_logging(
        Settings(
            _env_file=None,
            log_level="DEBUG",
            database_url="postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable",
            blob_container="ade-test",
            blob_connection_string="UseDevelopmentStorage=true",
            secret_key="test-secret-key-for-tests-please-change",
        )
    )
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

        response = unhandled_exception_handler(request=request, exc=RuntimeError("boom"))
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


def test_json_formatter_emits_structured_output():
    setup_logging(
        Settings(
            _env_file=None,
            log_format="json",
            log_level="INFO",
            database_url="postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable",
            blob_container="ade-test",
            blob_connection_string="UseDevelopmentStorage=true",
            secret_key="test-secret-key-for-tests-please-change",
        )
    )
    handler = _CaptureHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        bind_request_context("cid-json")
        logging.getLogger("test.json").info("json.event", extra={"answer": 42})

        assert handler.formatted, "Structured JSON log not captured"
        payload = json.loads(handler.formatted[-1])
        assert payload["message"] == "json.event"
        assert payload["correlation_id"] == "cid-json"
        assert payload["answer"] == 42
        assert payload["service"] == "ade-api"
    finally:
        clear_request_context()
        root.removeHandler(handler)


def test_setup_logging_disables_access_logger_when_requested():
    setup_logging(
        Settings(
            _env_file=None,
            log_level="INFO",
            access_log_enabled=False,
            database_url="postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable",
            blob_container="ade-test",
            blob_connection_string="UseDevelopmentStorage=true",
            secret_key="test-secret-key-for-tests-please-change",
        )
    )
    access_logger = logging.getLogger("uvicorn.access")
    assert access_logger.disabled is True
    assert access_logger.propagate is False


def test_setup_logging_applies_request_log_level_override():
    setup_logging(
        Settings(
            _env_file=None,
            log_level="WARNING",
            request_log_level="INFO",
            database_url="postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable",
            blob_container="ade-test",
            blob_connection_string="UseDevelopmentStorage=true",
            secret_key="test-secret-key-for-tests-please-change",
        )
    )
    request_logger = logging.getLogger("ade_api.request")
    assert request_logger.level == logging.INFO


def test_setup_logging_applies_effective_level_to_uvicorn_access_logger():
    setup_logging(
        Settings(
            _env_file=None,
            log_level="WARNING",
            database_url="postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable",
            blob_container="ade-test",
            blob_connection_string="UseDevelopmentStorage=true",
            secret_key="test-secret-key-for-tests-please-change",
        )
    )
    access_logger = logging.getLogger("uvicorn.access")
    assert access_logger.disabled is False
    assert access_logger.level == logging.WARNING
