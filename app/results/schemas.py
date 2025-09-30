from __future__ import annotations

from typing import Any

from pydantic import Field

from app.core.schema import BaseSchema


class ExtractedTableRecord(BaseSchema):
    """Serialised representation of an extracted table."""

    table_id: str = Field(alias="id", serialization_alias="table_id")
    job_id: str
    document_id: str
    sequence_index: int
    title: str | None = None
    row_count: int
    columns: list[str] = Field(default_factory=list)
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        alias="metadata_",
        serialization_alias="metadata",
    )
    created_at: str
    updated_at: str


__all__ = ["ExtractedTableRecord"]
