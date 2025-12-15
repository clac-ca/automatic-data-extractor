from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from ade_api.common.sorting import parse_sort, resolve_sort
from ade_api.features.documents.filters import (
    DOCUMENT_SOURCE_VALUES,
    DOCUMENT_STATUS_VALUES,
    DocumentFilters,
    DocumentSource,
    DocumentStatus,
)
from ade_api.features.documents.sorting import DEFAULT_SORT, ID_FIELD, SORT_FIELDS


def test_document_filters_normalise_sets_and_strings() -> None:
    uploader_one = str(uuid4())
    uploader_two = str(uuid4())
    filters = DocumentFilters(
        status_in=[DocumentStatus.UPLOADED.value, DocumentStatus.PROCESSED.value],
        source_in=[
            DocumentSource.MANUAL_UPLOAD.value,
            DocumentSource.MANUAL_UPLOAD.value,
        ],
        tags_in=[" alpha ", "beta", "alpha", ""],
        uploader_id_in=[
            uploader_one,
            uploader_one,
            uploader_two,
        ],
        q="  quarterly ",
    )

    assert filters.status_in == {
        DocumentStatus.UPLOADED,
        DocumentStatus.PROCESSED,
    }
    assert filters.source_in == {DocumentSource.MANUAL_UPLOAD}
    assert filters.tags_in == {"alpha", "beta"}
    assert filters.uploader_id_in == {
        UUID(uploader_one),
        UUID(uploader_two),
    }
    assert filters.q == "quarterly"


def test_document_filters_normalise_datetimes_to_utc() -> None:
    filters = DocumentFilters(
        created_at_from=datetime(2024, 5, 1, 8, 30),
        last_run_to=datetime(2024, 5, 3, 12, 0, tzinfo=UTC),
    )

    assert filters.created_at_from.tzinfo is UTC
    assert filters.last_run_to.tzinfo is UTC


def test_document_filters_reject_invalid_ranges() -> None:
    with pytest.raises(HTTPException):
        DocumentFilters(
            created_at_from=datetime(2024, 5, 2),
            created_at_to=datetime(2024, 5, 2),
        )

    with pytest.raises(HTTPException):
        DocumentFilters(
            last_run_from=datetime(2024, 4, 10, tzinfo=UTC),
            last_run_to=datetime(2024, 4, 10, tzinfo=UTC),
        )

    with pytest.raises(HTTPException):
        DocumentFilters(byte_size_from=100, byte_size_to=50)


def test_document_filter_enums_export_expected_values() -> None:
    assert set(DOCUMENT_STATUS_VALUES) == {status.value for status in DocumentStatus}
    assert set(DOCUMENT_SOURCE_VALUES) == {source.value for source in DocumentSource}


def test_sort_helpers_apply_defaults_and_tie_breakers() -> None:
    order = resolve_sort(
        parse_sort(None),
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )

    assert order[0] is SORT_FIELDS["created_at"][1]
    assert order[-1] is ID_FIELD[1]


def test_sort_helpers_reject_unknown_fields() -> None:
    with pytest.raises(HTTPException):
        resolve_sort(["-unknown"], allowed=SORT_FIELDS, default=DEFAULT_SORT, id_field=ID_FIELD)
