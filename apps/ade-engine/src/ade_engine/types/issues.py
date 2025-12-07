"""Validation issue helpers used by normalization and hooks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class ValidationIssue:
    """Represents a validation problem tied to a specific field/row."""

    row_index: int  # 0-based index relative to the first data row
    field: str | None
    code: str
    severity: Severity
    message: str | None = None
    details: dict[str, Any] | None = None


__all__ = ["Severity", "ValidationIssue"]
