from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import HTTPException
from pydantic import AliasChoices, Field, field_validator, model_validator
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.sql import Select

from ade_api.common.filters import FilterBase
from ade_api.common.ids import UUIDStr
from ade_api.common.validators import normalize_utc, parse_csv_or_repeated
from ade_api.models import (
    DOCUMENT_SOURCE_VALUES,
    DOCUMENT_STATUS_VALUES,
    Document,
    DocumentSource,
    DocumentStatus,
    DocumentTag,
    Run,
    RunStatus,
    User,
)
from ade_api.settings import MAX_SEARCH_LEN, MAX_SET_SIZE, MIN_SEARCH_LEN

from .tags import TagValidationError, normalize_tag_set


class DocumentFilters(FilterBase):
    """Query parameters supported by the document listing endpoint."""

    q: str | None = Field(
        None,
        min_length=MIN_SEARCH_LEN,
        max_length=MAX_SEARCH_LEN,
        description="Free text search applied to document name, tags, and uploader info.",
    )
    status: set[DocumentStatus] | None = Field(
        None,
        validation_alias=AliasChoices("status", "status_in"),
        description="Filter by one or more document statuses.",
    )
    run_status: set[RunStatus] | None = Field(
        None,
        description="Filter by the latest run status for each document.",
    )
    source_in: set[DocumentSource] | None = Field(
        None,
        description="Filter by the origin of the document.",
    )
    tags: set[str] | None = Field(
        None,
        description="Filter by documents tagged with the provided values (CSV or repeated params).",
    )
    tag_mode: Literal["any", "all"] | None = Field(
        None,
        validation_alias=AliasChoices("tag_mode", "tags_match"),
        description="Match strategy for tags (any or all). Defaults to any.",
    )
    tags_not: set[str] | None = Field(
        None,
        description="Exclude documents tagged with any of the provided values (CSV or repeated params).",
    )
    tags_empty: bool | None = Field(
        None,
        description="When true, only return documents without tags.",
    )
    uploader: str | None = Field(
        None,
        description="Restrict results to the literal 'me' to scope to the caller.",
    )
    uploader_id: set[UUIDStr] | None = Field(
        None,
        validation_alias=AliasChoices("uploader_id", "uploader_id_in"),
        description="Filter by one or more uploader identifiers.",
    )
    uploader_email: set[str] | None = Field(
        None,
        description="Filter by one or more uploader email addresses.",
    )
    folder_id: str | None = Field(
        None,
        description="Filter by folder identifier (use null to match unassigned).",
    )
    created_after: datetime | None = Field(
        None,
        validation_alias=AliasChoices("created_after", "created_at_from"),
        description="Return documents created on or after this timestamp (UTC).",
    )
    created_before: datetime | None = Field(
        None,
        validation_alias=AliasChoices("created_before", "created_at_to"),
        description="Return documents created before this timestamp (UTC).",
    )
    updated_after: datetime | None = Field(
        None,
        description="Return documents updated on or after this timestamp (UTC).",
    )
    updated_before: datetime | None = Field(
        None,
        description="Return documents updated before this timestamp (UTC).",
    )
    last_run_from: datetime | None = Field(
        None,
        description="Return documents last processed on or after this timestamp (UTC).",
    )
    last_run_to: datetime | None = Field(
        None,
        description="Return documents last processed before this timestamp (UTC).",
    )
    byte_size_from: int | None = Field(
        None,
        ge=0,
        description="Return documents with a byte size greater than or equal to this value.",
    )
    byte_size_to: int | None = Field(
        None,
        ge=0,
        description="Return documents with a byte size less than this value.",
    )
    file_type: set[Literal["xlsx", "xls", "csv", "pdf"]] | None = Field(
        None,
        description="Filter by file extension (CSV or repeated params).",
    )
    has_output: bool | None = Field(
        None,
        description="When true, only return documents with a successful run output.",
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
            return {DocumentStatus(item) for item in parsed}
        except ValueError as exc:  # pragma: no cover - validation guard
            raise HTTPException(422, "Invalid status value") from exc

    @field_validator("run_status", mode="before")
    @classmethod
    def _parse_run_statuses(cls, value):
        parsed = parse_csv_or_repeated(value)
        if parsed and len(parsed) > MAX_SET_SIZE:
            raise HTTPException(422, f"Too many run status values; max {MAX_SET_SIZE}.")
        if not parsed:
            return None
        try:
            return {RunStatus(item) for item in parsed}
        except ValueError as exc:  # pragma: no cover - validation guard
            raise HTTPException(422, "Invalid run status value") from exc

    @field_validator("source_in", mode="before")
    @classmethod
    def _parse_sources(cls, value):
        parsed = parse_csv_or_repeated(value)
        if parsed and len(parsed) > MAX_SET_SIZE:
            raise HTTPException(422, f"Too many source values; max {MAX_SET_SIZE}.")
        if not parsed:
            return None
        try:
            return {DocumentSource(item) for item in parsed}
        except ValueError as exc:  # pragma: no cover - validation guard
            raise HTTPException(422, "Invalid source value") from exc

    @field_validator("tags", "tags_not", mode="before")
    @classmethod
    def _parse_tags(cls, value):
        parsed = parse_csv_or_repeated(value)
        if parsed and len(parsed) > MAX_SET_SIZE:
            raise HTTPException(422, f"Too many tag values; max {MAX_SET_SIZE}.")
        if not parsed:
            return None
        try:
            normalized = normalize_tag_set(parsed)
        except TagValidationError as exc:
            raise HTTPException(422, str(exc)) from exc
        return normalized or None

    @field_validator("uploader_id", mode="before")
    @classmethod
    def _parse_uploader_ids(cls, value):
        parsed = parse_csv_or_repeated(value)
        if parsed and len(parsed) > MAX_SET_SIZE:
            raise HTTPException(422, f"Too many uploader IDs; max {MAX_SET_SIZE}.")
        return parsed or None

    @field_validator("uploader_email", mode="before")
    @classmethod
    def _parse_uploader_emails(cls, value):
        parsed = parse_csv_or_repeated(value)
        if parsed and len(parsed) > MAX_SET_SIZE:
            raise HTTPException(422, f"Too many uploader emails; max {MAX_SET_SIZE}.")
        if not parsed:
            return None
        return {item.strip().lower() for item in parsed if item.strip()} or None

    @field_validator("folder_id", mode="before")
    @classmethod
    def _normalize_folder_id(cls, value):
        if value is None:
            return None
        if isinstance(value, list):
            if not value:
                return None
            if len(value) > 1:
                raise HTTPException(422, "folder_id does not accept multiple values")
            value = value[0]
        candidate = str(value).strip()
        if not candidate:
            return ""
        if candidate.lower() == "null":
            return ""
        return candidate

    @field_validator(
        "created_after",
        "created_before",
        "updated_after",
        "updated_before",
        "last_run_from",
        "last_run_to",
        mode="before",
    )
    @classmethod
    def _normalise_datetimes(cls, value):
        return normalize_utc(value)

    @field_validator("byte_size_to")
    @classmethod
    def _validate_byte_size_to(cls, value, info):
        byte_size_from = info.data.get("byte_size_from")
        if value is not None and byte_size_from is not None and value <= byte_size_from:
            raise HTTPException(
                422,
                "byte_size_to must be greater than byte_size_from",
            )
        return value

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

    @field_validator("updated_before")
    @classmethod
    def _validate_updated_range(cls, value, info):
        updated_after = info.data.get("updated_after")
        if value is not None and updated_after is not None and value <= updated_after:
            raise HTTPException(
                422,
                "updated_before must be greater than updated_after",
            )
        return value

    @field_validator("last_run_to")
    @classmethod
    def _validate_last_run_range(cls, value, info):
        last_run_from = info.data.get("last_run_from")
        if value is not None and last_run_from is not None and value <= last_run_from:
            raise HTTPException(
                422,
                "last_run_to must be greater than last_run_from",
            )
        return value

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

    @model_validator(mode="after")
    def _validate_tag_filters(self) -> "DocumentFilters":
        if self.tags_empty and (self.tags or self.tags_not):
            raise HTTPException(422, "tags_empty cannot be combined with tags or tags_not.")
        return self


def apply_document_filters(
    stmt: Select,
    filters: DocumentFilters,
    *,
    actor: User | None,
) -> Select:
    """Apply ``filters`` to the provided document ``stmt``."""

    predicates = []

    if filters.status:
        status_values = sorted(
            status.value if isinstance(status, DocumentStatus) else str(status)
            for status in filters.status
        )
        predicates.append(Document.status.in_(status_values))
    if filters.run_status:
        run_status_values = sorted(
            status.value if isinstance(status, RunStatus) else str(status)
            for status in filters.run_status
        )
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
        predicates.append(latest_runs.c.rank == 1)
        predicates.append(latest_runs.c.status.in_(run_status_values))
    if filters.source_in:
        source_values = sorted(
            source.value if isinstance(source, DocumentSource) else str(source)
            for source in filters.source_in
        )
        predicates.append(Document.source.in_(source_values))
    if filters.tags_empty:
        predicates.append(~Document.tags.any())
    else:
        if filters.tags:
            match = filters.tag_mode or "any"
            if match == "all":
                for tag in sorted(filters.tags):
                    predicates.append(Document.tags.any(DocumentTag.tag == tag))
            else:
                predicates.append(Document.tags.any(DocumentTag.tag.in_(sorted(filters.tags))))
        if filters.tags_not:
            predicates.append(~Document.tags.any(DocumentTag.tag.in_(sorted(filters.tags_not))))

    uploader_ids: set[str] = set()
    uploader_emails: set[str] = set(filters.uploader_email or [])
    if filters.uploader == "me":
        if actor is None:
            raise HTTPException(422, "uploader=me requires authentication")
        uploader_ids.add(str(actor.id))
    elif filters.uploader:
        raise HTTPException(422, "uploader only accepts the literal 'me'")
    if filters.uploader_id:
        uploader_ids.update(filters.uploader_id)
    if uploader_ids or uploader_emails:
        uploader_predicates = []
        if uploader_ids:
            uploader_predicates.append(Document.uploaded_by_user_id.in_(sorted(uploader_ids)))
        if uploader_emails:
            uploader_predicates.append(
                Document.uploaded_by_user.has(func.lower(User.email).in_(sorted(uploader_emails)))
            )
        if len(uploader_predicates) == 1:
            predicates.append(uploader_predicates[0])
        else:
            predicates.append(or_(*uploader_predicates))

    if filters.created_after is not None:
        predicates.append(Document.created_at >= filters.created_after)
    if filters.created_before is not None:
        predicates.append(Document.created_at < filters.created_before)
    if filters.updated_after is not None:
        predicates.append(Document.updated_at >= filters.updated_after)
    if filters.updated_before is not None:
        predicates.append(Document.updated_at < filters.updated_before)

    if filters.last_run_from is not None:
        predicates.append(Document.last_run_at.is_not(None))
        predicates.append(Document.last_run_at >= filters.last_run_from)
    if filters.last_run_to is not None:
        if filters.last_run_from is not None:
            predicates.append(Document.last_run_at < filters.last_run_to)
        else:
            predicates.append(
                or_(
                    Document.last_run_at.is_(None),
                    Document.last_run_at < filters.last_run_to,
                )
            )

    if filters.byte_size_from is not None:
        predicates.append(Document.byte_size >= filters.byte_size_from)
    if filters.byte_size_to is not None:
        predicates.append(Document.byte_size < filters.byte_size_to)

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

    if filters.folder_id is not None:
        folder_value = filters.folder_id
        folder_field = Document.attributes["folder_id"].as_string()
        if folder_value == "":
            predicates.append(or_(folder_field.is_(None), folder_field == ""))
        else:
            predicates.append(folder_field == folder_value)

    if filters.has_output is not None:
        output_exists = (
            select(Run.id)
            .where(
                Run.workspace_id == Document.workspace_id,
                Run.input_document_id == Document.id,
                Run.status == RunStatus.SUCCEEDED,
            )
            .exists()
        )
        predicates.append(output_exists if filters.has_output else ~output_exists)

    if filters.q:
        uploader_alias = aliased(User)
        pattern = f"%{filters.q.lower()}%"
        stmt = stmt.outerjoin(uploader_alias, Document.uploaded_by_user)
        predicates.append(
            or_(
                func.lower(Document.original_filename).like(pattern),
                Document.tags.any(func.lower(DocumentTag.tag).like(pattern)),
                func.lower(uploader_alias.display_name).like(pattern),
                func.lower(uploader_alias.email).like(pattern),
            )
        )

    if predicates:
        stmt = stmt.where(and_(*predicates))

    return stmt


__all__ = [
    "DOCUMENT_SOURCE_VALUES",
    "DOCUMENT_STATUS_VALUES",
    "DocumentFilters",
    "DocumentSource",
    "DocumentStatus",
    "apply_document_filters",
]
