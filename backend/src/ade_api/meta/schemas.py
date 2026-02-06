"""Schemas for metadata routes."""

from pydantic import BaseModel, Field


class VersionsResponse(BaseModel):
    """Installed ADE package versions."""

    backend: str = Field(..., description="Installed backend distribution version.")
    engine: str = Field(..., description="Installed ade-engine version.")
    web: str = Field(..., description="Installed ade-web version (from version.json).")


__all__ = ["VersionsResponse"]
