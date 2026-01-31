from __future__ import annotations

import pytest
from fastapi import HTTPException

from ade_api.features.documents.changes import parse_document_change_cursor


def test_document_change_cursor_parses_numeric() -> None:
    assert parse_document_change_cursor("42") == 42


def test_document_change_cursor_invalid() -> None:
    with pytest.raises(HTTPException):
        parse_document_change_cursor("not-a-token")
