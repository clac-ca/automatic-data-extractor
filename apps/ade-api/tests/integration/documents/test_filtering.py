from datetime import UTC

import pytest
from fastapi import HTTPException

from ade_api.common.list_filters import (
    FilterItem,
    FilterOperator,
    parse_filter_items,
    prepare_filters,
)
from ade_api.common.sorting import parse_sort, resolve_sort
from ade_api.features.documents.filters import DOCUMENT_FILTER_REGISTRY
from ade_api.features.documents.sorting import DEFAULT_SORT, ID_FIELD, SORT_FIELDS
from ade_api.models import DocumentStatus


def test_parse_filters_rejects_invalid_json() -> None:
    with pytest.raises(HTTPException):
        parse_filter_items("{invalid", max_filters=5, max_raw_length=100)


def test_parse_filters_rejects_invalid_value_shapes() -> None:
    raw = '[{"id":"status","operator":"in","value":"processed"}]'
    with pytest.raises(HTTPException):
        parse_filter_items(raw, max_filters=5, max_raw_length=200)


def test_prepare_filters_coerces_enum_and_datetime() -> None:
    items = [
        FilterItem(id="status", operator=FilterOperator.EQ, value="processed"),
        FilterItem(
            id="createdAt",
            operator=FilterOperator.GTE,
            value="2024-05-01T08:30:00Z",
        ),
    ]
    parsed = prepare_filters(items, DOCUMENT_FILTER_REGISTRY)

    assert parsed[0].value == DocumentStatus.PROCESSED
    assert getattr(parsed[1].value, "tzinfo", None) is UTC


def test_prepare_filters_rejects_unknown_ids() -> None:
    items = [FilterItem(id="unknown", operator=FilterOperator.EQ, value="x")]
    with pytest.raises(HTTPException):
        prepare_filters(items, DOCUMENT_FILTER_REGISTRY)


def test_sort_helpers_apply_defaults_and_tie_breakers() -> None:
    order = resolve_sort(
        parse_sort(None),
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )

    assert order[0] is SORT_FIELDS["createdAt"][1]
    assert order[-1] is ID_FIELD[1]


def test_parse_sort_accepts_json_sort_items() -> None:
    raw = '[{"id":"createdAt","desc":false},{"id":"status","desc":true}]'
    assert parse_sort(raw) == ["createdAt", "-status"]


def test_parse_sort_rejects_csv_input() -> None:
    with pytest.raises(HTTPException):
        parse_sort("-createdAt,status")


def test_sort_helpers_reject_unknown_fields() -> None:
    with pytest.raises(HTTPException):
        resolve_sort(["-unknown"], allowed=SORT_FIELDS, default=DEFAULT_SORT, id_field=ID_FIELD)
