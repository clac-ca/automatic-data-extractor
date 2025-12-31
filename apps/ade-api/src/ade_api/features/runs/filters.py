from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import HTTPException
from pydantic import Field, field_validator
from sqlalchemy import and_, func, or_
from sqlalchemy.sql import Select

from ade_api.common.filters import FilterBase
from ade_api.common.ids import UUIDStr
from ade_api.common.validators import normalize_utc, parse_csv_or_repeated
from ade_api.models import Document, Run, RunStatus, RunTableColumn
from ade_api.settings import MAX_SEARCH_LEN, MAX_SET_SIZE, MIN_SEARCH_LEN


class RunFilters(FilterBase):
    """Query parameters for filtering workspace-scoped run listings."""

    q: str | None = Field(
        None,
        min_length=MIN_SEARCH_LEN,
        max_length=MAX_SEARCH_LEN,
        description="Free text search applied to document filenames.",
    )
    status: set[RunStatus] | None = Field(
        default=None,
        description="Optional run statuses to include (filters out others).",
    )
    configuration_id: set[UUIDStr] | None = Field(
        default=None,
        description="Limit runs to one or more configuration identifiers.",
    )
    input_document_id: UUIDStr | None = Field(
        default=None,
        description="Limit runs to those started for the given document.",
    )
    created_after: datetime | None = Field(
        None,
        description="Return runs created on or after this timestamp (UTC).",
    )
    created_before: datetime | None = Field(
        None,
        description="Return runs created before this timestamp (UTC).",
    )
    file_type: set[Literal["xlsx", "xls", "csv", "pdf"]] | None = Field(
        None,
        description="Filter by input document file extension (CSV or repeated params).",
    )
    has_output: bool | None = Field(
        None,
        description="When true, only return runs with a successful output.",
    )

    @field_validator("q")
    @classmethod
    def _trim_query(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        return candidate or None

    @field_validator("status", mode="before")
    @classmethod
    def _parse_statuses(cls, value):
        parsed = parse_csv_or_repeated(value)
        if parsed and len(parsed) > MAX_SET_SIZE:
            raise HTTPException(422, f"Too many status values; max {MAX_SET_SIZE}.")
        if not parsed:
            return None
        try:
            return {RunStatus(item) for item in parsed}
        except ValueError as exc:  # pragma: no cover - validation guard
            raise HTTPException(422, "Invalid status value") from exc

    @field_validator("configuration_id", mode="before")
    @classmethod
    def _parse_configuration_ids(cls, value):
        parsed = parse_csv_or_repeated(value)
        if parsed and len(parsed) > MAX_SET_SIZE:
            raise HTTPException(422, f"Too many configuration IDs; max {MAX_SET_SIZE}.")
        return parsed or None

    @field_validator("file_type", mode="before")
    @classmethod
    def _parse_file_types(cls, value):
        parsed = parse_csv_or_repeated(value)
        if parsed and len(parsed) > MAX_SET_SIZE:
            raise HTTPException(422, f"Too many file types; max {MAX_SET_SIZE}.")
        if not parsed:
            return None
        allowed = {"xlsx", "xls", "csv", "pdf"}
        normalized = {item.strip().lower() for item in parsed if item.strip()}
        invalid = sorted(value for value in normalized if value not in allowed)
        if invalid:
            raise HTTPException(422, f"Invalid file type value(s): {', '.join(invalid)}")
        return normalized or None

    @field_validator("created_after", "created_before", mode="before")
    @classmethod
    def _normalise_datetimes(cls, value):
        return normalize_utc(value)

    @field_validator("created_before")
    @classmethod
    def _validate_created_range(cls, value, info):
        created_after = info.data.get("created_after")
        if value is not None and created_after is not None and value <= created_after:
            raise HTTPException(
                422,
                "created_before must be greater than created_after",
            )
        return value


class RunColumnFilters(FilterBase):
    """Query parameters supported by run column listings."""

    sheet_name: str | None = Field(
        None,
        description="Filter columns to a specific sheet name.",
    )
    sheet_index: int | None = Field(
        None,
        ge=0,
        description="Filter columns to a specific sheet index (0-based).",
    )
    table_index: int | None = Field(
        None,
        ge=0,
        description="Filter columns to a specific table index (0-based).",
    )
    mapped_field: str | None = Field(
        None,
        description="Filter columns mapped to a specific field.",
    )
    mapping_status: Literal["mapped", "unmapped"] | None = Field(
        None,
        description="Filter columns by mapping status (mapped or unmapped).",
    )

    @field_validator("sheet_name", "mapped_field", mode="before")
    @classmethod
    def _trim_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        return candidate or None

    @field_validator("mapping_status", mode="before")
    @classmethod
    def _normalize_status(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip().lower() or None
        return value


def apply_run_filters(stmt: Select, filters: RunFilters) -> Select:
    """Apply ``filters`` to a run query."""

    predicates = []

    if filters.status:
        status_values = sorted(
            status.value if isinstance(status, RunStatus) else str(status)
            for status in filters.status
        )
        predicates.append(Run.status.in_(status_values))

    if filters.configuration_id:
        predicates.append(Run.configuration_id.in_(sorted(filters.configuration_id)))

    if filters.input_document_id:
        predicates.append(Run.input_document_id == filters.input_document_id)

    if filters.created_after is not None:
        predicates.append(Run.created_at >= filters.created_after)
    if filters.created_before is not None:
        predicates.append(Run.created_at < filters.created_before)

    if filters.has_output is not None:
        predicate = Run.status == RunStatus.SUCCEEDED
        predicates.append(predicate if filters.has_output else ~predicate)

    if filters.q or filters.file_type:
        stmt = stmt.join(Document, Run.input_document_id == Document.id)
        if filters.q:
            pattern = f"%{filters.q.lower()}%"
            predicates.append(func.lower(Document.original_filename).like(pattern))
        if filters.file_type:
            lower_name = func.lower(Document.original_filename)
            lower_type = func.lower(Document.content_type)
            type_predicates = []
            if "xlsx" in filters.file_type:
                type_predicates.append(
                    or_(lower_name.like("%.xlsx"), lower_type.like("%spreadsheetml%"))
                )
            if "xls" in filters.file_type:
                type_predicates.append(
                    or_(lower_name.like("%.xls"), lower_type.like("%ms-excel%"))
                )
            if "csv" in filters.file_type:
                type_predicates.append(or_(lower_name.like("%.csv"), lower_type.like("%csv%")))
            if "pdf" in filters.file_type:
                type_predicates.append(or_(lower_name.like("%.pdf"), lower_type.like("%pdf%")))
            if type_predicates:
                predicates.append(or_(*type_predicates))

    if predicates:
        stmt = stmt.where(and_(*predicates))

    return stmt


def apply_run_column_filters(stmt: Select, filters: RunColumnFilters) -> Select:
    """Apply ``filters`` to a run column query."""

    if filters.sheet_name:
        stmt = stmt.where(RunTableColumn.sheet_name == filters.sheet_name)
    if filters.sheet_index is not None:
        stmt = stmt.where(RunTableColumn.sheet_index == filters.sheet_index)
    if filters.table_index is not None:
        stmt = stmt.where(RunTableColumn.table_index == filters.table_index)
    if filters.mapped_field:
        stmt = stmt.where(RunTableColumn.mapped_field == filters.mapped_field)
    if filters.mapping_status:
        stmt = stmt.where(RunTableColumn.mapping_status == filters.mapping_status)
    return stmt


__all__ = [
    "RunFilters",
    "apply_run_filters",
    "RunColumnFilters",
    "apply_run_column_filters",
]
