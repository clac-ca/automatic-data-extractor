"""Response helper tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from ade.core.responses import DefaultResponse, JSONResponse
from ade.core.schema import BaseSchema


class ExampleSchema(BaseSchema):
    """Simple schema used to validate response serialization."""

    name: str
    timestamp: datetime


def test_json_response_serializes_schema_instance() -> None:
    """JSONResponse should encode BaseSchema instances using ADE helpers."""

    payload = ExampleSchema(name="test", timestamp=datetime(2024, 1, 1, tzinfo=UTC))
    response = JSONResponse(payload)

    assert response.media_type == "application/json"
    data = json.loads(response.body)
    assert data["name"] == "test"
    assert data["timestamp"].startswith("2024-01-01")


def test_json_response_serializes_schema_list() -> None:
    """JSONResponse should serialize lists of BaseSchema objects."""

    payload = [
        ExampleSchema(name="one", timestamp=datetime.now(tz=UTC)),
        ExampleSchema(name="two", timestamp=datetime.now(tz=UTC)),
    ]
    response = JSONResponse(payload)

    data = json.loads(response.body)
    assert isinstance(data, list)
    assert {item["name"] for item in data} == {"one", "two"}


def test_default_response_helpers() -> None:
    """DefaultResponse helpers should set status flags appropriately."""

    ok = DefaultResponse.success("Done")
    assert ok.status is True
    assert ok.message == "Done"

    err = DefaultResponse.failure("nope")
    assert err.status is False
    assert err.message == "nope"
