"""Shared helpers for handling HTTP ETag headers (compat re-export)."""

from __future__ import annotations

from ade_api.common.etag import (
    canonicalize_etag,
    format_etag,
    format_weak_etag,
)

__all__ = ["canonicalize_etag", "format_etag", "format_weak_etag"]
