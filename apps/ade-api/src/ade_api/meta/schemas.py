"""Schemas for metadata routes."""

from pydantic import BaseModel, Field


class VersionsResponse(BaseModel):
    """Installed ADE package versions."""

    ade_api: str = Field(..., description="Installed ade-api version.")
    ade_engine: str = Field(..., description="Installed ade-engine version.")


__all__ = ["VersionsResponse"]
