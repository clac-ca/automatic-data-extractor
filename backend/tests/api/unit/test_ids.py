import uuid

import pytest

from ade_api.common import ids


def test_generate_uuid7_returns_uuidv7() -> None:
    value = ids.generate_uuid7()

    assert isinstance(value, uuid.UUID)
    assert value.version == 7
    assert value.variant == uuid.RFC_4122


def test_generate_uuid7_monotonic_with_same_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ids.time, "time_ns", lambda: 1_700_000_000_000_000_000)
    monkeypatch.setattr(ids, "_uuid7_randbits", lambda n: 0)
    ids._UUID7_LAST_TS_MS = -1  # type: ignore[attr-defined]
    ids._UUID7_LAST_RAND = 0  # type: ignore[attr-defined]

    first = ids.generate_uuid7()
    second = ids.generate_uuid7()

    assert int.from_bytes(first.bytes[:6], "big") == int.from_bytes(second.bytes[:6], "big")
    assert first.int < second.int
