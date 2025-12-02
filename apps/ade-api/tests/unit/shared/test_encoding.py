from __future__ import annotations

import json
from uuid import uuid4

from ade_api.common.encoding import json_bytes, json_dumps
from ade_api.common.schema import BaseSchema


class _SampleSchema(BaseSchema):
    id: str


def test_json_dumps_serializes_uuid_keys_and_values() -> None:
    uid = uuid4()
    payload = {"id": uid, "nested": {uid: uid}}

    encoded = json_dumps(payload)
    data = json.loads(encoded)

    assert data["id"] == str(uid)
    assert data["nested"][str(uid)] == str(uid)


def test_json_dumps_handles_base_schema() -> None:
    sample = _SampleSchema(id="abc123")

    encoded = json_dumps({"sample": sample})
    data = json.loads(encoded)

    assert data["sample"]["id"] == "abc123"


def test_json_bytes_matches_dumps() -> None:
    payload = {"id": str(uuid4())}

    assert json_bytes(payload) == json_dumps(payload).encode("utf-8")
