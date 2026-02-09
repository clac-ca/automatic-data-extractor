from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

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
from ade_db.models import File, FileTag, FileVersion, FileVersionOrigin, Run, RunStatus

from .tags import TagValidationError, normalize_tag_set

ALLOWED_FILE_TYPES = {"xlsx", "xls", "csv", "pdf"}


def _current_version_byte_size_expr() -> ColumnElement[Any]:
    return (
        select(FileVersion.byte_size)
        .where(FileVersion.id == File.current_version_id)
        .scalar_subquery()
    )


def _current_version_content_type_expr() -> ColumnElement[Any]:
    return (
        select(FileVersion.content_type)
        .where(FileVersion.id == File.current_version_id)
        .scalar_subquery()
    )


def _current_version_origin_expr() -> ColumnElement[Any]:
    return (
        select(FileVersion.origin)
        .where(FileVersion.id == File.current_version_id)
        .scalar_subquery()
    )


def _last_run_at_expr() -> ColumnElement[Any]:
    return (
        select(func.max(func.coalesce(Run.completed_at, Run.started_at, Run.created_at)))
        .select_from(Run)
        .join(FileVersion, Run.input_file_version_id == FileVersion.id)
        .where(
            FileVersion.file_id == File.id,
            Run.workspace_id == File.workspace_id,
        )
        .scalar_subquery()
    )


def _activity_at_expr() -> ColumnElement[Any]:
    last_run_at = _last_run_at_expr()
    return case(
        (last_run_at.is_(None), File.updated_at),
        (File.updated_at.is_(None), last_run_at),
        (last_run_at > File.updated_at, last_run_at),
        else_=File.updated_at,
    )


DOCUMENT_FILTER_REGISTRY = FilterRegistry([
    FilterField(
        id="id",
        column=File.id,
        operators={FilterOperator.EQ, FilterOperator.IN},
        value_type=FilterValueType.UUID,
    ),
    FilterField(
        id="name",
        column=File.name,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.ILIKE,
            FilterOperator.NOT_ILIKE,
            FilterOperator.IS_EMPTY,
            FilterOperator.IS_NOT_EMPTY,
        },
        value_type=FilterValueType.STRING,
    ),
    FilterField(
        id="lastRunPhase",
        column=Run.status,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
            FilterOperator.IS_EMPTY,
            FilterOperator.IS_NOT_EMPTY,
        },
        value_type=FilterValueType.STRING,
    ),
    FilterField(
        id="fileType",
        column=File.name,
        operators={
            FilterOperator.EQ,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
            FilterOperator.IS_EMPTY,
            FilterOperator.IS_NOT_EMPTY,
        },
        value_type=FilterValueType.STRING,
    ),
    FilterField(
        id="tags",
        column=FileTag.tag,
        operators={
            FilterOperator.EQ,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
            FilterOperator.IS_EMPTY,
            FilterOperator.IS_NOT_EMPTY,
        },
        value_type=FilterValueType.STRING,
    ),
    FilterField(
        id="assigneeId",
        column=File.assignee_user_id,
        operators={
            FilterOperator.EQ,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
            FilterOperator.IS_EMPTY,
            FilterOperator.IS_NOT_EMPTY,
        },
        value_type=FilterValueType.UUID,
    ),
    FilterField(
        id="uploaderId",
        column=File.uploaded_by_user_id,
        operators={
            FilterOperator.EQ,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
            FilterOperator.IS_EMPTY,
            FilterOperator.IS_NOT_EMPTY,
        },
        value_type=FilterValueType.UUID,
    ),
    FilterField(
        id="createdAt",
        column=File.created_at,
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
        id="updatedAt",
        column=File.updated_at,
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
        id="activityAt",
        column=_activity_at_expr(),
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
        id="byteSize",
        column=_current_version_byte_size_expr(),
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
            FilterOperator.LT,
            FilterOperator.LTE,
            FilterOperator.GT,
            FilterOperator.GTE,
            FilterOperator.BETWEEN,
            FilterOperator.IS_EMPTY,
            FilterOperator.IS_NOT_EMPTY,
        },
        value_type=FilterValueType.INT,
    ),
    FilterField(
        id="hasOutput",
        column=Run.status,
        operators={FilterOperator.EQ, FilterOperator.NE},
        value_type=FilterValueType.BOOL,
    ),
    FilterField(
        id="source",
        column=_current_version_origin_expr(),
        operators={
            FilterOperator.EQ,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
            FilterOperator.IS_EMPTY,
            FilterOperator.IS_NOT_EMPTY,
        },
        value_type=FilterValueType.ENUM,
        enum_type=FileVersionOrigin,
    ),
])


def apply_document_filters(
    stmt: Select,
    filters: list[FilterItem],
    *,
    join_operator: FilterJoinOperator,
    q: str | None,
) -> Select:
    parsed_filters = prepare_filters(filters, DOCUMENT_FILTER_REGISTRY)
    predicates: list = []

    last_run_joined = False
    status_expr = None
    last_run_subquery = None

    for parsed in parsed_filters:
        filter_id = parsed.field.id
        if filter_id == "lastRunPhase":
            if not last_run_joined:
                timestamp = func.coalesce(Run.completed_at, Run.started_at, Run.created_at)
                last_run_subquery = (
                    select(
                        FileVersion.file_id.label("file_id"),
                        Run.status.label("status"),
                        func
                        .row_number()
                        .over(
                            partition_by=FileVersion.file_id,
                            order_by=timestamp.desc(),
                        )
                        .label("rank"),
                    )
                    .select_from(Run)
                    .join(FileVersion, Run.input_file_version_id == FileVersion.id)
                    .where(Run.input_file_version_id.is_not(None))
                    .subquery()
                )
                stmt = stmt.outerjoin(
                    last_run_subquery,
                    (last_run_subquery.c.file_id == File.id) & (last_run_subquery.c.rank == 1),
                )
                status_expr = last_run_subquery.c.status
                last_run_joined = True
            if parsed.operator == FilterOperator.IS_EMPTY:
                assert status_expr is not None
                predicates.append(status_expr.is_(None))
                continue
            if parsed.operator == FilterOperator.IS_NOT_EMPTY:
                assert status_expr is not None
                predicates.append(status_expr.is_not(None))
                continue

            values = parsed.value
            phase_values = values if isinstance(values, list) else [values]
            normalized_phases: list[str] = []
            include_empty = False
            invalid: list[str] = []
            for value in phase_values:
                if isinstance(value, RunStatus):
                    raw = value.value
                else:
                    raw = str(value).strip().lower()
                if not raw:
                    continue
                if raw == "__empty__":
                    include_empty = True
                    continue
                try:
                    normalized_phases.append(RunStatus(raw).value)
                except ValueError:
                    invalid.append(raw)
            if invalid:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Invalid lastRunPhase value(s): {', '.join(sorted(invalid))}",
                )
            if parsed.operator in {FilterOperator.NE, FilterOperator.NOT_IN}:
                assert status_expr is not None
                base = (
                    and_(status_expr.is_not(None), ~status_expr.in_(normalized_phases))
                    if normalized_phases
                    else status_expr.is_not(None)
                )
                predicate = base if not include_empty else base
            else:
                if not normalized_phases and not include_empty:
                    continue
                phase_predicates = []
                if normalized_phases:
                    assert status_expr is not None
                    phase_predicates.append(status_expr.in_(normalized_phases))
                if include_empty:
                    assert status_expr is not None
                    phase_predicates.append(status_expr.is_(None))
                assert status_expr is not None
                predicate = or_(*phase_predicates) if phase_predicates else status_expr.is_(None)
            predicates.append(predicate)
            continue

        if filter_id == "fileType":
            values = parsed.value
            types = values if isinstance(values, list) else [values]
            normalized_types = {str(item).strip().lower() for item in types if str(item).strip()}
            if len(normalized_types) > MAX_SET_SIZE:
                raise HTTPException(422, f"Too many file types; max {MAX_SET_SIZE}.")
            invalid = sorted(value for value in normalized_types if value not in ALLOWED_FILE_TYPES)
            if invalid:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Invalid file type value(s): {', '.join(invalid)}",
                )
            lower_name = func.lower(File.name)
            lower_type = func.lower(_current_version_content_type_expr())
            type_predicates = []
            if "xlsx" in normalized_types:
                type_predicates.append(
                    or_(lower_name.like("%.xlsx"), lower_type.like("%spreadsheetml%"))
                )
            if "xls" in normalized_types:
                type_predicates.append(or_(lower_name.like("%.xls"), lower_type.like("%ms-excel%")))
            if "csv" in normalized_types:
                type_predicates.append(or_(lower_name.like("%.csv"), lower_type.like("%csv%")))
            if "pdf" in normalized_types:
                type_predicates.append(or_(lower_name.like("%.pdf"), lower_type.like("%pdf%")))
            if not type_predicates:
                continue
            predicate = or_(*type_predicates)
            if parsed.operator == FilterOperator.NOT_IN:
                predicate = ~predicate
            predicates.append(predicate)
            continue

        if filter_id == "tags":
            if parsed.operator == FilterOperator.IS_EMPTY:
                predicates.append(~File.tags.any())
                continue
            if parsed.operator == FilterOperator.IS_NOT_EMPTY:
                predicates.append(File.tags.any())
                continue

            values = parsed.value
            tag_values = values if isinstance(values, list) else [values]
            if len(tag_values) > MAX_SET_SIZE:
                raise HTTPException(422, f"Too many tag values; max {MAX_SET_SIZE}.")
            try:
                normalized_tags = normalize_tag_set(tag_values)
            except TagValidationError as exc:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
            if not normalized_tags:
                continue
            if parsed.operator == FilterOperator.EQ:
                predicates.append(File.tags.any(FileTag.tag == next(iter(normalized_tags))))
                continue
            predicate = File.tags.any(FileTag.tag.in_(sorted(normalized_tags)))
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
            output_exists = (
                select(Run.id)
                .select_from(Run)
                .join(FileVersion, Run.input_file_version_id == FileVersion.id)
                .where(
                    Run.workspace_id == File.workspace_id,
                    FileVersion.file_id == File.id,
                    Run.status == RunStatus.SUCCEEDED,
                    Run.output_file_version_id.is_not(None),
                )
                .exists()
            )
            value = bool(parsed.value)
            predicate = output_exists if value else ~output_exists
            if parsed.operator == FilterOperator.NE:
                predicate = ~predicate
            predicates.append(predicate)
            continue

        predicates.append(build_predicate(parsed))

    combined = combine_predicates(predicates, join_operator)
    if combined is not None:
        stmt = stmt.where(combined)

    q_predicate = build_q_predicate(resource="documents", q=q, registry=SEARCH_REGISTRY)
    if q_predicate is not None:
        stmt = stmt.where(q_predicate)

    return stmt


__all__ = ["DOCUMENT_FILTER_REGISTRY", "apply_document_filters"]
