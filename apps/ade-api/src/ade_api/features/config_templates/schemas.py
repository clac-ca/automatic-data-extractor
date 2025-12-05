"""Schemas for bundled and user-provided config templates."""

from __future__ import annotations

from ade_api.common.schema import BaseSchema


class ConfigTemplate(BaseSchema):
    """Metadata for an available configuration template."""

    id: str
    name: str
    description: str | None = None
    version: str | None = None


__all__ = ["ConfigTemplate"]
