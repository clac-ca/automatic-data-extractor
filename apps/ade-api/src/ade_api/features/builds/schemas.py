"""Pydantic schemas describing build resources and streaming events."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AliasChoices, ConfigDict, Field, conint

from ade_engine.schemas import AdeEvent
from ade_api.common.ids import UUIDStr
from ade_api.common.pagination import Page, PageParams
from ade_api.common.schema import BaseSchema
from ade_api.core.models import BuildStatus
from ade_api.settings import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

BuildObjectType = Literal["ade.build"]
BuildEventObjectType = Literal["ade.build.event"]

__all__ = [
    "BuildCreateOptions",
    "BuildCreateRequest",
    "BuildLinks",
    "BuildEventsPage",
    "BuildEvent",
    "BuildFilters",
    "BuildListParams",
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
    links: "BuildLinks"

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


class BuildFilters(BaseSchema):
    """Query parameters for filtering build listings."""

    status: list[BuildStatus] | None = Field(
        default=None,
        description="Optional build statuses to include (filters out others).",
    )


class BuildListParams(PageParams):
    """Pagination parameters for build listings with limit alias."""

    page_size: conint(ge=1, le=MAX_PAGE_SIZE) = Field(  # type: ignore[assignment]
        DEFAULT_PAGE_SIZE,
        description=f"Items per page (alias: limit, max {MAX_PAGE_SIZE})",
        validation_alias=AliasChoices("page_size", "limit"),
        serialization_alias="limit",
    )


class BuildPage(Page[BuildResource]):
    """Paginated collection of ``BuildResource`` items."""

    items: list[BuildResource]


class BuildEventsPage(BaseSchema):
    """Paginated ADE events for a build."""

    items: list[AdeEvent]
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
    type: Literal["build.completed"] = "build.completed"
    status: BuildStatus
    exit_code: int | None = None
    error_message: str | None = None
    summary: str | None = None


BuildEvent = Annotated[
    BuildCreatedEvent | BuildCompletedEvent,
    Field(discriminator="type"),
]
