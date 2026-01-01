"""Pydantic schemas describing build resources and streaming events."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import ConfigDict, Field

from ade_api.common.events import EventRecord
from ade_api.common.ids import UUIDStr
from ade_api.common.listing import ListPage
from ade_api.common.schema import BaseSchema
from ade_api.models import BuildStatus

BuildObjectType = Literal["ade.build"]
BuildEventObjectType = Literal["ade.build.event"]

__all__ = [
    "BuildCreateOptions",
    "BuildCreateRequest",
    "BuildLinks",
    "BuildEventsPage",
    "BuildEvent",
    "BuildPage",
    "BuildResource",
]


def _timestamp(dt: datetime | None) -> int | None:
    return int(dt.timestamp()) if dt else None


class BuildResource(BaseSchema):
    """API representation of a build row."""

    id: UUIDStr
    object: BuildObjectType = "ade.build"

    workspace_id: UUIDStr
    configuration_id: UUIDStr

    status: BuildStatus
    created: int = Field(..., description="Unix timestamp when the build request was created")
    started: int | None = Field(None, description="Unix timestamp when execution started")
    finished: int | None = Field(None, description="Unix timestamp when execution completed")

    exit_code: int | None = None
    summary: str | None = None
    error_message: str | None = None
    links: BuildLinks

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

    options: BuildCreateOptions = Field(default_factory=BuildCreateOptions)


class BuildLinks(BaseSchema):
    """Hypermedia links for build-related resources."""

    self: str
    events: str
    events_stream: str


class BuildPage(ListPage[BuildResource]):
    """Paginated collection of ``BuildResource`` items."""

    items: list[BuildResource]


class BuildEventsPage(BaseSchema):
    """Paginated ADE events for a build."""

    items: list[EventRecord]
    next_after_sequence: int | None = None


class BuildEventBase(BaseSchema):
    """Common fields shared by all build events."""

    object: BuildEventObjectType = "ade.build.event"
    build_id: UUIDStr = Field(..., description="API build identifier")
    created: int = Field(..., description="Unix timestamp seconds")
    type: str = Field(..., description="Event discriminator")


class BuildCreatedEvent(BuildEventBase):
    type: Literal["build.created"] = "build.created"
    status: BuildStatus
    configuration_id: UUIDStr


class BuildCompletedEvent(BuildEventBase):
    type: Literal["build.complete"] = "build.complete"
    status: BuildStatus
    exit_code: int | None = None
    error_message: str | None = None
    summary: str | None = None


BuildEvent = Annotated[
    BuildCreatedEvent | BuildCompletedEvent,
    Field(discriminator="type"),
]
