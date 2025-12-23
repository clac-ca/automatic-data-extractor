from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import HTTPException
from pydantic import Field, field_validator, model_validator
from sqlalchemy import and_, func, or_
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
        description="Free text search applied to document name and uploader info.",
    )
    status_in: set[DocumentStatus] | None = Field(
        None,
        description="Filter by one or more document statuses.",
    )
    source_in: set[DocumentSource] | None = Field(
        None,
        description="Filter by the origin of the document.",
    )
    tags: set[str] | None = Field(
        None,
        description="Filter by documents tagged with the provided values (CSV or repeated params).",
    )
    tags_match: Literal["any", "all"] | None = Field(
        None,
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
    uploader_id_in: set[UUIDStr] | None = Field(
        None,
        alias="uploader_id_in",
        description="Filter by one or more uploader identifiers.",
    )
    created_at_from: datetime | None = Field(
        None,
        description="Return documents created on or after this timestamp (UTC).",
    )
    created_at_to: datetime | None = Field(
        None,
        description="Return documents created before this timestamp (UTC).",
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

    @field_validator("q")
    @classmethod
    def _trim_query(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        return candidate or None

    @field_validator("status_in", mode="before")
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

    @field_validator("uploader_id_in", mode="before")
    @classmethod
    def _parse_uploader_ids(cls, value):
        parsed = parse_csv_or_repeated(value)
        if parsed and len(parsed) > MAX_SET_SIZE:
            raise HTTPException(422, f"Too many uploader IDs; max {MAX_SET_SIZE}.")
        return parsed or None

    @field_validator(
        "created_at_from",
        "created_at_to",
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

    @field_validator("created_at_to")
    @classmethod
    def _validate_created_range(cls, value, info):
        created_at_from = info.data.get("created_at_from")
        if value is not None and created_at_from is not None and value <= created_at_from:
            raise HTTPException(
                422,
                "created_at_to must be greater than created_at_from",
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

    if filters.status_in:
        status_values = sorted(
            status.value if isinstance(status, DocumentStatus) else str(status)
            for status in filters.status_in
        )
        predicates.append(Document.status.in_(status_values))
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
            match = filters.tags_match or "any"
            if match == "all":
                for tag in sorted(filters.tags):
                    predicates.append(Document.tags.any(DocumentTag.tag == tag))
            else:
                predicates.append(Document.tags.any(DocumentTag.tag.in_(sorted(filters.tags))))
        if filters.tags_not:
            predicates.append(~Document.tags.any(DocumentTag.tag.in_(sorted(filters.tags_not))))

    uploader_ids: set[str] = set()
    if filters.uploader == "me":
        if actor is None:
            raise HTTPException(422, "uploader=me requires authentication")
        uploader_ids.add(actor.id)
    elif filters.uploader:
        raise HTTPException(422, "uploader only accepts the literal 'me'")
    if filters.uploader_id_in:
        uploader_ids.update(filters.uploader_id_in)
    if uploader_ids:
        predicates.append(Document.uploaded_by_user_id.in_(sorted(uploader_ids)))

    if filters.created_at_from is not None:
        predicates.append(Document.created_at >= filters.created_at_from)
    if filters.created_at_to is not None:
        predicates.append(Document.created_at < filters.created_at_to)

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

    if filters.q:
        uploader_alias = aliased(User)
        pattern = f"%{filters.q.lower()}%"
        stmt = stmt.outerjoin(uploader_alias, Document.uploaded_by_user)
        predicates.append(
            or_(
                func.lower(Document.original_filename).like(pattern),
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
