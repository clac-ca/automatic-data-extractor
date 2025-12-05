from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

ENGINE_FRAME_SCHEMA = "ade.engine.events.v1"


class EngineEventFrameV1(BaseModel):
    """Inbound engine frame parsed from stdout."""

    model_config = ConfigDict(
        extra="forbid",
        protected_namespaces=(),
        populate_by_name=True,
    )

    schema_id: Literal["ade.engine.events.v1"] = Field(
        default=ENGINE_FRAME_SCHEMA,
        alias="schema_id",
        serialization_alias="schema_id",
        validation_alias=AliasChoices("schema_id", "schema"),
    )
    type: str = Field(..., description="Event type, e.g. engine.start or console.line")
    event_id: UUID = Field(..., description="Engine-local UUID for traceability")
    created_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


__all__ = ["ENGINE_FRAME_SCHEMA", "EngineEventFrameV1"]
