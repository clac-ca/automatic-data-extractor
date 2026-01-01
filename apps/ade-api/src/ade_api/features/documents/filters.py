from __future__ import annotations

from typing import Iterable

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
from ade_api.common.search import build_q_predicate, matches_tokens, parse_q
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

from .schemas import DocumentFileType, DocumentListRow
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
            },
            value_type=FilterValueType.ENUM,
            enum_type=DocumentStatus,
        ),
        FilterField(
            id="runStatus",
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
            id="fileType",
            column=Document.original_filename,
            operators={FilterOperator.EQ, FilterOperator.IN, FilterOperator.NOT_IN},
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
                FilterOperator.LT,
                FilterOperator.LTE,
                FilterOperator.GT,
                FilterOperator.GTE,
                FilterOperator.BETWEEN,
            },
            value_type=FilterValueType.DATETIME,
        ),
        FilterField(
            id="updatedAt",
            column=Document.updated_at,
            operators={
                FilterOperator.LT,
                FilterOperator.LTE,
                FilterOperator.GT,
                FilterOperator.GTE,
                FilterOperator.BETWEEN,
            },
            value_type=FilterValueType.DATETIME,
        ),
        FilterField(
            id="activityAt",
            column=_activity_at_expr(),
            operators={
                FilterOperator.LT,
                FilterOperator.LTE,
                FilterOperator.GT,
                FilterOperator.GTE,
                FilterOperator.BETWEEN,
            },
            value_type=FilterValueType.DATETIME,
        ),
        FilterField(
            id="byteSize",
            column=Document.byte_size,
            operators={
                FilterOperator.EQ,
                FilterOperator.IN,
                FilterOperator.NOT_IN,
                FilterOperator.LT,
                FilterOperator.LTE,
                FilterOperator.GT,
                FilterOperator.GTE,
                FilterOperator.BETWEEN,
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
            operators={FilterOperator.EQ, FilterOperator.IN, FilterOperator.NOT_IN},
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
            status_list = [value.value if isinstance(value, RunStatus) else str(value) for value in status_values]
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


def evaluate_document_filters(
    row: DocumentListRow,
    filters: list[FilterItem],
    *,
    join_operator: FilterJoinOperator,
    q: str | None,
) -> tuple[bool, bool]:
    parsed_filters = prepare_filters(filters, DOCUMENT_FILTER_REGISTRY)
    results: list[bool] = []
    requires_refresh = False

    for parsed in parsed_filters:
        filter_id = parsed.field.id
        operator = parsed.operator
        value = parsed.value

        if filter_id == "status":
            values = value if isinstance(value, list) else [value]
            statuses = {status.value if isinstance(status, DocumentStatus) else str(status) for status in values}
            row_status = row.status.value if isinstance(row.status, DocumentStatus) else str(row.status)
            match = row_status in statuses
            if operator in {FilterOperator.NE, FilterOperator.NOT_IN}:
                match = not match
            results.append(match)
            continue

        if filter_id == "runStatus":
            if row.latest_run is None:
                results.append(False)
                continue
            values = value if isinstance(value, list) else [value]
            statuses = {status.value if isinstance(status, RunStatus) else str(status) for status in values}
            last_status = (
                row.latest_run.status.value
                if isinstance(row.latest_run.status, RunStatus)
                else str(row.latest_run.status)
            )
            match = last_status in statuses
            if operator in {FilterOperator.NE, FilterOperator.NOT_IN}:
                match = not match
            results.append(match)
            continue

        if filter_id == "fileType":
            values = value if isinstance(value, list) else [value]
            types = {str(item) for item in values}
            file_type = row.file_type.value if isinstance(row.file_type, DocumentFileType) else str(row.file_type)
            match = file_type in types
            if operator == FilterOperator.NOT_IN:
                match = not match
            results.append(match)
            continue

        if filter_id == "tags":
            tags = set(row.tags or [])
            if operator == FilterOperator.IS_EMPTY:
                results.append(not tags)
                continue
            if operator == FilterOperator.IS_NOT_EMPTY:
                results.append(bool(tags))
                continue
            values = value if isinstance(value, list) else [value]
            tag_set = {str(item) for item in values}
            match = bool(tags & tag_set)
            if operator == FilterOperator.EQ:
                match = str(next(iter(tag_set))) in tags
            if operator == FilterOperator.NOT_IN:
                match = not match
            results.append(match)
            continue

        if filter_id == "assigneeId":
            assignee_id = row.assignee.id if row.assignee else None
            if operator == FilterOperator.IS_EMPTY:
                results.append(assignee_id is None)
                continue
            if operator == FilterOperator.IS_NOT_EMPTY:
                results.append(assignee_id is not None)
                continue
            values = value if isinstance(value, list) else [value]
            assignee_ids = {str(item) for item in values}
            match = assignee_id is not None and str(assignee_id) in assignee_ids
            if operator == FilterOperator.NOT_IN:
                match = not match
            results.append(match)
            continue

        if filter_id == "uploaderId":
            uploader_id = row.uploader.id if row.uploader else None
            if operator == FilterOperator.IS_EMPTY:
                results.append(uploader_id is None)
                continue
            if operator == FilterOperator.IS_NOT_EMPTY:
                results.append(uploader_id is not None)
                continue
            values = value if isinstance(value, list) else [value]
            uploader_ids = {str(item) for item in values}
            match = uploader_id is not None and str(uploader_id) in uploader_ids
            if operator == FilterOperator.NOT_IN:
                match = not match
            results.append(match)
            continue

        if filter_id in {"createdAt", "updatedAt", "activityAt"}:
            source = {
                "createdAt": row.created_at,
                "updatedAt": row.updated_at,
                "activityAt": row.activity_at,
            }[filter_id]
            if operator == FilterOperator.BETWEEN:
                lower, upper = value
                results.append(lower <= source <= upper)
                continue
            if operator == FilterOperator.LT:
                results.append(source < value)
                continue
            if operator == FilterOperator.LTE:
                results.append(source <= value)
                continue
            if operator == FilterOperator.GT:
                results.append(source > value)
                continue
            if operator == FilterOperator.GTE:
                results.append(source >= value)
                continue

        if filter_id == "byteSize":
            if operator == FilterOperator.BETWEEN:
                lower, upper = value
                results.append(lower <= row.byte_size <= upper)
                continue
            if operator == FilterOperator.LT:
                results.append(row.byte_size < value)
                continue
            if operator == FilterOperator.LTE:
                results.append(row.byte_size <= value)
                continue
            if operator == FilterOperator.GT:
                results.append(row.byte_size > value)
                continue
            if operator == FilterOperator.GTE:
                results.append(row.byte_size >= value)
                continue
            if operator == FilterOperator.EQ:
                results.append(row.byte_size == value)
                continue
            if operator == FilterOperator.NOT_IN:
                results.append(row.byte_size not in set(value or []))
                continue
            if operator == FilterOperator.IN:
                results.append(row.byte_size in set(value or []))
                continue

        if filter_id == "hasOutput":
            has_output = row.latest_successful_run is not None
            match = has_output == bool(value)
            if operator == FilterOperator.NE:
                match = not match
            results.append(match)
            continue

        requires_refresh = True
        results.append(False)

    filter_match = True
    if results:
        if join_operator == FilterJoinOperator.OR:
            filter_match = any(results)
        else:
            filter_match = all(results)

    if q:
        tokens = parse_q(q).tokens
        status_value = row.status.value if isinstance(row.status, DocumentStatus) else str(row.status)
        values: list[str | None] = [row.name, status_value]
        if row.uploader:
            values.extend([row.uploader.name, row.uploader.email])
        values.extend(row.tags or [])
        filter_match = filter_match and matches_tokens(tokens, values)

    return filter_match, requires_refresh


__all__.append("evaluate_document_filters")
