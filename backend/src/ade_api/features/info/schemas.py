"""Schemas for the info endpoint."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from ade_api.common.schema import BaseSchema


class InfoResponse(BaseSchema):
    """Runtime/build metadata for ADE API."""

    version: str
    commit_sha: str = Field(alias="commitSha")
    started_at: datetime = Field(alias="startedAt")


__all__ = ["InfoResponse"]
