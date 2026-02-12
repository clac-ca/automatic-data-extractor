from __future__ import annotations

import asyncio
from types import SimpleNamespace

from ade_api.features.documents.events import (
    DocumentChangesHub,
    RESYNC_REASON_QUEUE_OVERFLOW,
)


def test_enqueue_queue_overflow_replaces_oldest_with_resync_marker() -> None:
    hub = DocumentChangesHub(settings=SimpleNamespace(), queue_size=10)
    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=1)
    queue.put_nowait(
        {
            "workspaceId": "ws-1",
            "documentId": "doc-old",
            "op": "upsert",
            "id": "1",
        }
    )

    hub._enqueue(  # noqa: SLF001 - exercising overflow behavior directly
        queue,
        {
            "workspaceId": "ws-1",
            "documentId": "doc-new",
            "op": "upsert",
            "id": "2",
        },
    )

    marker = queue.get_nowait()
    assert marker["workspaceId"] == "ws-1"
    assert marker["resync"] is True
    assert marker["reason"] == RESYNC_REASON_QUEUE_OVERFLOW
    assert marker["id"] == "2"
