"""Schemas for Graph-style batch request execution."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ade_api.common.schema import BaseSchema


class BatchSubrequest(BaseSchema):
    """Single operation within a batch request envelope."""

    id: str = Field(min_length=1, max_length=120)
    method: str = Field(min_length=1, max_length=16)
    url: str = Field(min_length=1, max_length=2048)
    headers: dict[str, str] | None = None
    body: dict[str, Any] | None = None
    depends_on: list[str] = Field(default_factory=list, alias="dependsOn")


class BatchRequest(BaseSchema):
    """Graph-style batch request envelope."""

    requests: list[BatchSubrequest] = Field(min_length=1, max_length=20)


class BatchSubresponse(BaseSchema):
    """Single operation result returned by the batch executor."""

    id: str
    status: int
    headers: dict[str, str] | None = None
    body: dict[str, Any] | list[Any] | str | None = None


class BatchResponse(BaseSchema):
    """Batch response envelope keyed by subrequest id."""

    responses: list[BatchSubresponse]


__all__ = [
    "BatchRequest",
    "BatchResponse",
    "BatchSubrequest",
    "BatchSubresponse",
]
