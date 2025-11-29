"""Pydantic schemas describing build resources and streaming events."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import ConfigDict, Field

from ade_api.shared.core.schema import BaseSchema

BuildObjectType = Literal["ade.build"]
BuildEventObjectType = Literal["ade.build.event"]
BuildStatusLiteral = Literal["queued", "building", "active", "failed", "canceled"]

__all__ = [
    "BuildCreateOptions",
    "BuildCreateRequest",
    "BuildEvent",
    "BuildResource",
    "BuildStatusLiteral",
]


def _timestamp(dt: datetime | None) -> int | None:
    return int(dt.timestamp()) if dt else None


class BuildResource(BaseSchema):
    """API representation of a build row."""

    id: str
    object: BuildObjectType = "ade.build"

    workspace_id: str
    configuration_id: str

    status: BuildStatusLiteral
    created: int = Field(..., description="Unix timestamp when the build request was created")
    started: int | None = Field(None, description="Unix timestamp when execution started")
    finished: int | None = Field(None, description="Unix timestamp when execution completed")

    exit_code: int | None = None
    summary: str | None = None
    error_message: str | None = None

    model_config = ConfigDict(json_encoders={datetime: _timestamp})


class BuildCreateOptions(BaseSchema):
    """Options controlling build orchestration."""

    force: bool = Field(
        False,
        description="Force rebuild even if fingerprints match",
    )
    wait: bool = Field(
        False,
        description="Wait for in-progress builds to complete before starting a new one",
    )


class BuildCreateRequest(BaseSchema):
    """Request body for POST /builds."""

    stream: bool = False
    options: BuildCreateOptions = Field(default_factory=BuildCreateOptions)


class BuildEventBase(BaseSchema):
    """Common fields shared by all build events."""

    object: BuildEventObjectType = "ade.build.event"
    build_id: str = Field(..., description="API build identifier")
    created: int = Field(..., description="Unix timestamp seconds")
    type: str = Field(..., description="Event discriminator")


class BuildCreatedEvent(BuildEventBase):
    type: Literal["build.created"] = "build.created"
    status: BuildStatusLiteral
    configuration_id: str


class BuildCompletedEvent(BuildEventBase):
    type: Literal["build.completed"] = "build.completed"
    status: BuildStatusLiteral
    exit_code: int | None = None
    error_message: str | None = None
    summary: str | None = None


BuildEvent = Annotated[
    BuildCreatedEvent | BuildCompletedEvent,
    Field(discriminator="type"),
]
