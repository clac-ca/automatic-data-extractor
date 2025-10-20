"""Custom exceptions for the health module."""

from __future__ import annotations


class HealthCheckError(RuntimeError):
    """Raised when the health module fails to produce a response."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
