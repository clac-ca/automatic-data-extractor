from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ade_api.common.list_filters import FilterJoinOperator
from ade_api.common.listing import ListQueryParams
from ade_api.features.documents.filters import evaluate_document_filters
from ade_api.features.documents.router import _apply_change_metadata
from ade_api.features.documents.schemas import (
    DocumentChangeEntry,
    DocumentFileType,
    DocumentListRow,
    UserSummary,
)
from ade_api.models import DocumentStatus


def _make_row(*, name: str, status: DocumentStatus, tags: list[str]) -> DocumentListRow:
    now = datetime.now(tz=UTC)
    uploader = UserSummary(
        id=str(uuid4()),
        name="Uploader",
        email="uploader@example.com",
    )
    return DocumentListRow(
        id=str(uuid4()),
        workspace_id=str(uuid4()),
        name=name,
        file_type=DocumentFileType.PDF,
        status=status,
        uploader=uploader,
        assignee=None,
        tags=tags,
        byte_size=100,
        created_at=now,
        updated_at=now,
        activity_at=now,
        latest_run=None,
        latest_successful_run=None,
        latest_result=None,
    )


def test_evaluate_document_filters_matches_q_tokens() -> None:
    row = _make_row(
        name="alpha-report.pdf",
        status=DocumentStatus.PROCESSED,
        tags=["finance"],
    )

    matched, requires_refresh = evaluate_document_filters(
        row,
        [],
        join_operator=FilterJoinOperator.AND,
        q="alpha finance",
    )

    assert matched is True
    assert requires_refresh is False


def test_evaluate_document_filters_rejects_non_matching_q() -> None:
    row = _make_row(
        name="alpha-report.pdf",
        status=DocumentStatus.PROCESSED,
        tags=["finance"],
    )

    matched, requires_refresh = evaluate_document_filters(
        row,
        [],
        join_operator=FilterJoinOperator.AND,
        q="alpha beta",
    )

    assert matched is False
    assert requires_refresh is False


def test_change_metadata_requires_refresh_when_row_missing() -> None:
    entry = DocumentChangeEntry(
        cursor="1",
        type="document.deleted",
        document_id=str(uuid4()),
        occurred_at=datetime.now(tz=UTC),
        row=None,
    )
    list_query = ListQueryParams(
        page=1,
        per_page=50,
        sort=[],
        filters=[],
        join_operator=FilterJoinOperator.AND,
        q="alpha",
    )

    updated = _apply_change_metadata(entry, list_query=list_query, sort_tokens=["-createdAt"])

    assert updated.requires_refresh is True
