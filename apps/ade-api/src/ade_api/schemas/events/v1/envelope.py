from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, ConfigDict, Field

from ade_api.common.ids import UUIDStr
from ade_api.common.schema import BaseSchema

ADE_EVENT_SCHEMA = "ade.events.v1"


class AdeEventV1(BaseSchema):
    """API-owned canonical ADE event envelope."""

    model_config = ConfigDict(
        **BaseSchema.model_config,
        protected_namespaces=(),
    )

    schema_id: Literal["ade.events.v1"] = Field(
        default=ADE_EVENT_SCHEMA,
        alias="schema_id",
        serialization_alias="schema_id",
        validation_alias=AliasChoices("schema_id", "schema"),
    )

    type: str
    event_id: str
    sequence: int

    created_at: datetime
    source: Literal["api", "engine"]

    workspace_id: UUIDStr
    configuration_id: UUIDStr
    run_id: UUIDStr | None = None
    build_id: UUIDStr | None = None

    origin_event_id: str | None = None

    payload: dict[str, Any] = Field(default_factory=dict)

    def payload_dict(self) -> dict[str, Any]:
        return self.payload or {}


__all__ = ["ADE_EVENT_SCHEMA", "AdeEventV1"]
