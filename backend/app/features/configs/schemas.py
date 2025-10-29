"""Pydantic schemas for configuration engine v0.4 (initial placeholders)."""

from __future__ import annotations

from pydantic import BaseModel


class ConfigRecord(BaseModel):
    """Placeholder schema representing a config record."""

    config_id: str


__all__ = ["ConfigRecord"]
