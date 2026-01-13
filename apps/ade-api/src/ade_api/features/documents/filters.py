from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.sql import Select

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
from ade_api.models import (
    Document,
    DocumentSource,
    DocumentStatus,
    DocumentTag,
    Run,
    RunStatus,
)
from ade_api.settings import MAX_SET_SIZE

from .tags import TagValidationError, normalize_tag_set

ALLOWED_FILE_TYPES = {"xlsx", "xls", "csv", "pdf"}


def _activity_at_expr():
    return case(
        (Document.last_run_at.is_(None), Document.updated_at),
        (Document.updated_at.is_(None), Document.last_run_at),
        (Document.last_run_at > Document.updated_at, Document.last_run_at),
        else_=Document.updated_at,
    )


DOCUMENT_FILTER_REGISTRY = FilterRegistry(
    [
        FilterField(
            id="status",
            column=Document.status,
            operators={
                FilterOperator.EQ,
                FilterOperator.NE,
                FilterOperator.IN,
                FilterOperator.NOT_IN,
                FilterOperator.IS_EMPTY,
                FilterOperator.IS_NOT_EMPTY,
            },
            value_type=FilterValueType.ENUM,
            enum_type=DocumentStatus,
        ),
        FilterField(
            id="name",
            column=Document.original_filename,
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
            id="runStatus",
            column=Run.status,
            operators={
                FilterOperator.EQ,
                FilterOperator.NE,
                FilterOperator.IN,
                FilterOperator.NOT_IN,
                FilterOperator.IS_EMPTY,
                FilterOperator.IS_NOT_EMPTY,
            },
            value_type=FilterValueType.ENUM,
            enum_type=RunStatus,
        ),
        FilterField(
            id="fileType",
            column=Document.original_filename,
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
            column=DocumentTag.tag,
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
            column=Document.assignee_user_id,
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
            column=Document.uploaded_by_user_id,
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
            column=Document.created_at,
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
            column=Document.updated_at,
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
            column=Document.byte_size,
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
            column=Document.source,
            operators={
                FilterOperator.EQ,
                FilterOperator.IN,
                FilterOperator.NOT_IN,
                FilterOperator.IS_EMPTY,
                FilterOperator.IS_NOT_EMPTY,
            },
            value_type=FilterValueType.ENUM,
            enum_type=DocumentSource,
        ),
    ]
)


def apply_document_filters(
    stmt: Select,
    filters: list[FilterItem],
    *,
    join_operator: FilterJoinOperator,
    q: str | None,
) -> Select:
    parsed_filters = prepare_filters(filters, DOCUMENT_FILTER_REGISTRY)
    predicates: list = []

    latest_runs = None

    for parsed in parsed_filters:
        filter_id = parsed.field.id
        if filter_id == "status":
            values = parsed.value
            status_values = values if isinstance(values, list) else [values]
            normalized = [
                value.value if isinstance(value, DocumentStatus) else str(value)
                for value in status_values
            ]
            if parsed.operator in {FilterOperator.NE, FilterOperator.NOT_IN}:
                predicate = ~Document.status.in_(normalized)
            else:
                predicate = Document.status.in_(normalized)
            predicates.append(predicate)
            continue

        if filter_id == "runStatus":
            if latest_runs is None:
                timestamp = func.coalesce(Run.completed_at, Run.started_at, Run.created_at)
                latest_runs = (
                    select(
                        Run.input_document_id.label("document_id"),
                        Run.status.label("status"),
                        func.row_number()
                        .over(
                            partition_by=Run.input_document_id,
                            order_by=timestamp.desc(),
                        )
                        .label("rank"),
                    )
                    .where(Run.input_document_id.is_not(None))
                    .subquery()
                )
                stmt = stmt.join(latest_runs, latest_runs.c.document_id == Document.id)
            values = parsed.value
            status_values = values if isinstance(values, list) else [values]
            status_list = [
                value.value if isinstance(value, RunStatus) else str(value)
                for value in status_values
            ]
            if parsed.operator in {FilterOperator.NE, FilterOperator.NOT_IN}:
                predicate = and_(
                    latest_runs.c.rank == 1,
                    ~latest_runs.c.status.in_(status_list),
                )
            else:
                predicate = and_(
                    latest_runs.c.rank == 1,
                    latest_runs.c.status.in_(status_list),
                )
            predicates.append(predicate)
            continue

        if filter_id == "fileType":
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
            lower_name = func.lower(Document.original_filename)
            lower_type = func.lower(Document.content_type)
            type_predicates = []
            if "xlsx" in normalized:
                type_predicates.append(
                    or_(lower_name.like("%.xlsx"), lower_type.like("%spreadsheetml%"))
                )
            if "xls" in normalized:
                type_predicates.append(
                    or_(lower_name.like("%.xls"), lower_type.like("%ms-excel%"))
                )
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

        if filter_id == "tags":
            if parsed.operator == FilterOperator.IS_EMPTY:
                predicates.append(~Document.tags.any())
                continue
            if parsed.operator == FilterOperator.IS_NOT_EMPTY:
                predicates.append(Document.tags.any())
                continue

            values = parsed.value
            tag_values = values if isinstance(values, list) else [values]
            if len(tag_values) > MAX_SET_SIZE:
                raise HTTPException(422, f"Too many tag values; max {MAX_SET_SIZE}.")
            try:
                normalized = normalize_tag_set(tag_values)
            except TagValidationError as exc:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
            if not normalized:
                continue
            if parsed.operator == FilterOperator.EQ:
                predicates.append(Document.tags.any(DocumentTag.tag == next(iter(normalized))))
                continue
            predicate = Document.tags.any(DocumentTag.tag.in_(sorted(normalized)))
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
                .where(
                    Run.workspace_id == Document.workspace_id,
                    Run.input_document_id == Document.id,
                    Run.status == RunStatus.SUCCEEDED,
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
