"""Helpers for document upload metadata payloads."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from .schemas import DocumentUploadRunOptions

UPLOAD_RUN_OPTIONS_KEY = "__ade_run_options"


def build_upload_metadata(
    metadata: Mapping[str, Any] | None,
    run_options: DocumentUploadRunOptions | None,
) -> dict[str, Any]:
    """Merge caller metadata with optional run options."""

    payload = dict(metadata or {})
    if run_options is not None:
        payload[UPLOAD_RUN_OPTIONS_KEY] = run_options.model_dump(exclude_none=True)
    return payload


def parse_upload_run_options(
    metadata: Mapping[str, Any] | None,
) -> DocumentUploadRunOptions | None:
    """Parse run options stored in document metadata."""

    if not metadata:
        return None
    raw = metadata.get(UPLOAD_RUN_OPTIONS_KEY)
    if raw is None:
        return None
    try:
        return DocumentUploadRunOptions.model_validate(raw)
    except ValidationError:
        return None


__all__ = [
    "UPLOAD_RUN_OPTIONS_KEY",
    "build_upload_metadata",
    "parse_upload_run_options",
]
