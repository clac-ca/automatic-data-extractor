"""Unit tests for ETag helpers."""

from __future__ import annotations

import pytest

from ade_api.features.configs.etag import canonicalize_etag, format_etag


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('"sha256:abc"', "sha256:abc"),
        ('W/"sha256:def"', "sha256:def"),
        (" sha256:ghi ", "sha256:ghi"),
        (None, None),
        ("", None),
    ],
)
def test_canonicalize_etag(raw: str | None, expected: str | None) -> None:
    assert canonicalize_etag(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("sha256:abc", '"sha256:abc"'),
        ('"sha256:def"', '"sha256:def"'),
        (" W/\"sha256:ghi\" ", '"sha256:ghi"'),
        (None, None),
        ("", None),
    ],
)
def test_format_etag(raw: str | None, expected: str | None) -> None:
    assert format_etag(raw) == expected
