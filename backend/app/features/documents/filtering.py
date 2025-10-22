"""Filter primitives for the documents feature."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any

from pydantic import Field, ValidationError, field_validator, model_validator

from backend.app.shared.core.schema import BaseSchema

ULID_PATTERN = r"[0-9A-HJKMNP-TV-Z]{26}"
ULIDStr = Annotated[
    str,
    Field(
        min_length=26,
        max_length=26,
        pattern=ULID_PATTERN,
        description="ULID (26-character string).",
    ),
]


DOCUMENT_STATUS_VALUES: tuple[str, ...]
DOCUMENT_SOURCE_VALUES: tuple[str, ...]


class DocumentStatus(str, Enum):
    """Canonical document processing states."""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    ARCHIVED = "archived"


class DocumentSource(str, Enum):
    """Origins for uploaded documents."""

    MANUAL_UPLOAD = "manual_upload"


DOCUMENT_STATUS_VALUES = tuple(status.value for status in DocumentStatus)
DOCUMENT_SOURCE_VALUES = tuple(source.value for source in DocumentSource)


class DocumentSortableField(str, Enum):
    """Fields that can be used for ordering document queries."""

    CREATED_AT = "created_at"
    STATUS = "status"
    LAST_RUN_AT = "last_run_at"
    BYTE_SIZE = "byte_size"
    SOURCE = "source"
    NAME = "name"


class DocumentSort(BaseSchema):
    """Single-field sort descriptor."""

    field: DocumentSortableField = Field(description="Field used for ordering results.")
    descending: bool = Field(default=False, description="Whether the sort is descending.")

    @field_validator("field", mode="after")
    @classmethod
    def _coerce_field(
        cls, value: DocumentSortableField | str
    ) -> DocumentSortableField:
        return DocumentSortableField(value)

    @classmethod
    def parse(cls, raw: str | None) -> "DocumentSort":
        """Return a sort descriptor from the API-provided value.

        The backend accepts an optional ``-`` prefix to denote descending order.
        When ``raw`` is ``None`` a descending sort on ``created_at`` is returned so
        callers inherit the contract's default ordering.
        """

        if not raw:
            return cls(field=DocumentSortableField.CREATED_AT, descending=True)

        descending = raw.startswith("-")
        field_name = raw[1:] if descending else raw
        try:
            field = DocumentSortableField(field_name)
        except ValueError as exc:  # pragma: no cover - guarded by validation layer
            raise ValueError(f"Invalid sort field: {field_name}") from exc
        return cls(field=field, descending=descending)

    def api_param(self) -> str:
        """Return the string representation suitable for query parameters."""

        prefix = "-" if self.descending else ""
        return f"{prefix}{self.field.value}"


class DocumentFilters(BaseSchema):
    """Normalised collection of filters applied to a document search."""

    model_config = BaseSchema.model_config.copy()
    model_config["extra"] = "forbid"

    status: list[DocumentStatus] = Field(default_factory=list)
    source: list[DocumentSource] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    uploader_me: bool = Field(
        default=False,
        description="Whether to restrict results to the authenticated uploader.",
    )
    uploader_ids: list[ULIDStr] = Field(default_factory=list)
    q: str | None = Field(
        default=None,
        description="Substring search applied to document name or uploader metadata.",
    )
    created_from: datetime | None = Field(default=None)
    created_to: datetime | None = Field(default=None)
    last_run_from: datetime | None = Field(default=None)
    last_run_to: datetime | None = Field(default=None)
    byte_size_min: int | None = Field(default=None, ge=0)
    byte_size_max: int | None = Field(default=None, ge=0)

    @field_validator("status", "source", "tags", "uploader_ids", mode="before")
    @classmethod
    def _listify(cls, value: object) -> list[object]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, (set, tuple)):
            return list(value)
        return list(value)

    @field_validator("tags")
    @classmethod
    def _normalise_tags(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for tag in value:
            tag = tag.strip()
            if not tag:
                continue
            if tag in seen:
                continue
            seen.add(tag)
            unique.append(tag)
        return unique

    @field_validator("status", "source", "uploader_ids", mode="after")
    @classmethod
    def _deduplicate(cls, value: list[object]) -> list[object]:
        seen: set[object] = set()
        unique: list[object] = []
        for item in value:
            if item in seen:
                continue
            seen.add(item)
            unique.append(item)
        return unique

    @field_validator("status", mode="after")
    @classmethod
    def _coerce_status(
        cls, value: list[DocumentStatus | str]
    ) -> list[DocumentStatus]:
        return [DocumentStatus(item) for item in value]

    @field_validator("source", mode="after")
    @classmethod
    def _coerce_source(
        cls, value: list[DocumentSource | str]
    ) -> list[DocumentSource]:
        return [DocumentSource(item) for item in value]

    @field_validator("q")
    @classmethod
    def _clean_query(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def _validate_ranges(self) -> "DocumentFilters":
        if (
            self.created_from
            and self.created_to
            and self.created_from > self.created_to
        ):
            raise ValueError("created_from must be earlier than or equal to created_to")
        if (
            self.last_run_from
            and self.last_run_to
            and self.last_run_from > self.last_run_to
        ):
            raise ValueError("last_run_from must be earlier than or equal to last_run_to")
        if (
            self.byte_size_min is not None
            and self.byte_size_max is not None
            and self.byte_size_min > self.byte_size_max
        ):
            raise ValueError("byte_size_min must be less than or equal to byte_size_max")
        return self


class DocumentFilterParams(DocumentFilters):
    """Request-level filter payload including sort directives."""

    sort: DocumentSort = Field(
        default_factory=lambda: DocumentSort.parse(None),
        description="Sort descriptor parsed from the `sort` query parameter.",
    )
    uploader: str | None = Field(
        default=None,
        description="Identity shortcut accepting the literal 'me'.",
    )

    @model_validator(mode="before")
    @classmethod
    def _prepare_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        payload = dict(data)
        uploader = payload.pop("uploader", None)
        if uploader is not None:
            if uploader != "me":
                raise ValidationError(
                    [
                        {
                            "type": "value_error",
                            "loc": ("uploader",),
                            "msg": "uploader must be the literal 'me'",
                            "input": uploader,
                        }
                    ],
                    cls,
                )
            payload["uploader_me"] = True

        raw_sort = payload.get("sort")
        if isinstance(raw_sort, DocumentSort):
            payload["sort"] = raw_sort
        else:
            payload["sort"] = DocumentSort.parse(raw_sort)
        return payload

    def to_filters(self) -> DocumentFilters:
        """Return the query-ready filter payload without sort metadata."""

        return DocumentFilters.model_validate(
            self.model_dump(
                mode="python",
                exclude={"sort", "uploader"},
            )
        )


__all__ = [
    "DOCUMENT_SOURCE_VALUES",
    "DOCUMENT_STATUS_VALUES",
    "DocumentFilterParams",
    "DocumentFilters",
    "DocumentSort",
    "DocumentSortableField",
    "DocumentSource",
    "DocumentStatus",
    "ULIDStr",
]
