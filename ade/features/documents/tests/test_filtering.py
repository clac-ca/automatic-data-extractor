from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ade.features.documents.filtering import (
    DOCUMENT_SOURCE_VALUES,
    DOCUMENT_STATUS_VALUES,
    DocumentFilterParams,
    DocumentFilters,
    DocumentSort,
    DocumentSortableField,
    DocumentSource,
    DocumentStatus,
)


def test_document_filters_normalise_lists_and_strings() -> None:
    filters = DocumentFilters(
        status=[DocumentStatus.UPLOADED.value, DocumentStatus.PROCESSED],
        source=[DocumentSource.MANUAL_UPLOAD, DocumentSource.MANUAL_UPLOAD.value],
        tags=[" alpha ", "beta", "alpha", ""],
        uploader_ids=[
            "01H8M8Z1QB9X4Y7V5T2R3S4Q5A",
            "01H8M8Z1QB9X4Y7V5T2R3S4Q5A",
            "01H8M8Z1QB9X4Y7V5T2R3S4Q6A",
        ],
        q="  quarterly ",
    )

    assert filters.status == [DocumentStatus.UPLOADED, DocumentStatus.PROCESSED]
    assert filters.source == [DocumentSource.MANUAL_UPLOAD]
    assert filters.tags == ["alpha", "beta"]
    assert filters.uploader_ids == [
        "01H8M8Z1QB9X4Y7V5T2R3S4Q5A",
        "01H8M8Z1QB9X4Y7V5T2R3S4Q6A",
    ]
    assert filters.q == "quarterly"
    assert filters.uploader_me is False


@pytest.mark.parametrize(
    "created_from, created_to",
    [
        (
            datetime(2024, 5, 2, tzinfo=UTC),
            datetime(2024, 5, 1, tzinfo=UTC),
        ),
    ],
)
def test_document_filters_reject_invalid_created_range(
    created_from: datetime, created_to: datetime
) -> None:
    with pytest.raises(ValidationError):
        DocumentFilters(created_from=created_from, created_to=created_to)


@pytest.mark.parametrize(
    "last_run_from, last_run_to",
    [
        (
            datetime(2024, 4, 10, tzinfo=UTC),
            datetime(2024, 4, 9, tzinfo=UTC),
        ),
    ],
)
def test_document_filters_reject_invalid_last_run_range(
    last_run_from: datetime, last_run_to: datetime
) -> None:
    with pytest.raises(ValidationError):
        DocumentFilters(last_run_from=last_run_from, last_run_to=last_run_to)


def test_document_filters_reject_invalid_byte_size_range() -> None:
    with pytest.raises(ValidationError):
        DocumentFilters(byte_size_min=500, byte_size_max=100)


def test_document_sort_parsing_defaults_to_created_desc() -> None:
    result = DocumentSort.parse(None)

    assert result.field is DocumentSortableField.CREATED_AT
    assert result.descending is True


@pytest.mark.parametrize(
    "raw, expected_field, expected_descending",
    [
        ("status", DocumentSortableField.STATUS, False),
        ("-byte_size", DocumentSortableField.BYTE_SIZE, True),
        ("name", DocumentSortableField.NAME, False),
    ],
)
def test_document_sort_parsing_handles_prefixes(
    raw: str, expected_field: DocumentSortableField, expected_descending: bool
) -> None:
    parsed = DocumentSort.parse(raw)

    assert parsed.field is expected_field
    assert parsed.descending is expected_descending


def test_document_sort_parsing_rejects_unknown_field() -> None:
    with pytest.raises(ValueError):
        DocumentSort.parse("-unknown")


def test_document_filter_enums_export_expected_values() -> None:
    assert set(DOCUMENT_STATUS_VALUES) == {status.value for status in DocumentStatus}
    assert set(DOCUMENT_SOURCE_VALUES) == {source.value for source in DocumentSource}


def test_document_filter_params_normalise_uploader_and_sort() -> None:
    params = DocumentFilterParams(
        uploader="me",
        sort="-status",
        status=[DocumentStatus.PROCESSED.value, DocumentStatus.UPLOADED.value],
    )

    assert params.uploader_me is True
    assert params.sort.field is DocumentSortableField.STATUS
    assert params.sort.descending is True

    filters = params.to_filters()
    assert isinstance(filters, DocumentFilters)
    assert filters.status == [DocumentStatus.PROCESSED, DocumentStatus.UPLOADED]
