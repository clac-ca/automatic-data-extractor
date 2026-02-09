from __future__ import annotations

from typing import Literal

from fastapi import HTTPException, status
from pydantic import Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.sql import Select

from ade_api.common.filters import FilterBase
from ade_api.common.list_filters import (
    FilterField,
    FilterItem,
    FilterJoinOperator,
    FilterOperator,
    FilterRegistry,
    FilterValueType,
    build_predicate,
    combine_predicates,
    prepare_filters,
)
from ade_api.common.search import build_q_predicate
from ade_api.features.search_registry import SEARCH_REGISTRY
from ade_api.settings import MAX_SET_SIZE
from ade_db.models import FileVersion, Run, RunStatus, RunTableColumn

ALLOWED_FILE_TYPES = {"xlsx", "xls", "csv", "pdf"}

RUN_FILTER_REGISTRY = FilterRegistry([
    FilterField(
        id="status",
        column=Run.status,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
        },
        value_type=FilterValueType.ENUM,
        enum_type=RunStatus,
    ),
    FilterField(
        id="configurationId",
        column=Run.configuration_id,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
        },
        value_type=FilterValueType.UUID,
    ),
    FilterField(
        id="inputDocumentId",
        column=FileVersion.file_id,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
            FilterOperator.IS_EMPTY,
            FilterOperator.IS_NOT_EMPTY,
        },
        value_type=FilterValueType.UUID,
    ),
    FilterField(
        id="createdAt",
        column=Run.created_at,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.LT,
            FilterOperator.LTE,
            FilterOperator.GT,
            FilterOperator.GTE,
            FilterOperator.BETWEEN,
        },
        value_type=FilterValueType.DATETIME,
    ),
    FilterField(
        id="startedAt",
        column=Run.started_at,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.LT,
            FilterOperator.LTE,
            FilterOperator.GT,
            FilterOperator.GTE,
            FilterOperator.BETWEEN,
            FilterOperator.IS_EMPTY,
            FilterOperator.IS_NOT_EMPTY,
        },
        value_type=FilterValueType.DATETIME,
    ),
    FilterField(
        id="completedAt",
        column=Run.completed_at,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.LT,
            FilterOperator.LTE,
            FilterOperator.GT,
            FilterOperator.GTE,
            FilterOperator.BETWEEN,
            FilterOperator.IS_EMPTY,
            FilterOperator.IS_NOT_EMPTY,
        },
        value_type=FilterValueType.DATETIME,
    ),
    FilterField(
        id="fileType",
        column=FileVersion.filename_at_upload,
        operators={FilterOperator.EQ, FilterOperator.IN, FilterOperator.NOT_IN},
        value_type=FilterValueType.STRING,
    ),
    FilterField(
        id="hasOutput",
        column=Run.status,
        operators={FilterOperator.EQ, FilterOperator.NE},
        value_type=FilterValueType.BOOL,
    ),
])


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


def apply_run_filters(
    stmt: Select,
    filters: list[FilterItem],
    *,
    join_operator: FilterJoinOperator,
    q: str | None,
) -> Select:
    parsed_filters = prepare_filters(filters, RUN_FILTER_REGISTRY)
    predicates: list = []
    join_file_version = False
    q_predicate = build_q_predicate(resource="runs", q=q, registry=SEARCH_REGISTRY)
    if q_predicate is not None:
        join_file_version = True

    for parsed in parsed_filters:
        filter_id = parsed.field.id

        if filter_id == "inputDocumentId":
            join_file_version = True

        if filter_id == "fileType":
            join_file_version = True
            values = parsed.value
            types = values if isinstance(values, list) else [values]
            normalized = {str(item).strip().lower() for item in types if str(item).strip()}
            if len(normalized) > MAX_SET_SIZE:
                raise HTTPException(422, f"Too many file types; max {MAX_SET_SIZE}.")
            invalid = sorted(value for value in normalized if value not in ALLOWED_FILE_TYPES)
            if invalid:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Invalid file type value(s): {', '.join(invalid)}",
                )
            lower_name = func.lower(FileVersion.filename_at_upload)
            lower_type = func.lower(FileVersion.content_type)
            type_predicates = []
            if "xlsx" in normalized:
                type_predicates.append(
                    or_(lower_name.like("%.xlsx"), lower_type.like("%spreadsheetml%"))
                )
            if "xls" in normalized:
                type_predicates.append(or_(lower_name.like("%.xls"), lower_type.like("%ms-excel%")))
            if "csv" in normalized:
                type_predicates.append(or_(lower_name.like("%.csv"), lower_type.like("%csv%")))
            if "pdf" in normalized:
                type_predicates.append(or_(lower_name.like("%.pdf"), lower_type.like("%pdf%")))
            if not type_predicates:
                continue
            predicate = or_(*type_predicates)
            if parsed.operator == FilterOperator.NOT_IN:
                predicate = ~predicate
            predicates.append(predicate)
            continue

        if filter_id == "hasOutput":
            if parsed.value is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="hasOutput requires a boolean value",
                )
            value = bool(parsed.value)
            predicate = Run.status == RunStatus.SUCCEEDED
            predicate = predicate if value else ~predicate
            if parsed.operator == FilterOperator.NE:
                predicate = ~predicate
            predicates.append(predicate)
            continue

        predicates.append(build_predicate(parsed))

    combined = combine_predicates(predicates, join_operator)
    if combined is not None:
        stmt = stmt.where(combined)

    if join_file_version:
        stmt = stmt.join(FileVersion, Run.input_file_version_id == FileVersion.id)
    if q_predicate is not None:
        stmt = stmt.where(q_predicate)

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
    "RUN_FILTER_REGISTRY",
    "RunColumnFilters",
    "apply_run_filters",
    "apply_run_column_filters",
]
