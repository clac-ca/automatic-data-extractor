"""End-to-end document change stream tests (SSE → delta → list)."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
import json
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from asgi_lifespan import LifespanManager
from sqlalchemy.orm import Session

from ade_api.core.security.hashing import hash_password
from ade_api.db import get_sessionmaker_from_app
from ade_api.db.migrations import run_migrations
from ade_api.features.rbac.service import RbacService
from ade_api.main import create_app
from ade_api.models import User, Workspace, WorkspaceMembership
from ade_api.settings import get_settings
from tests.utils import login

pytestmark = pytest.mark.asyncio


@dataclass(frozen=True, slots=True)
class SeededUser:
    id: UUID
    email: str
    password: str


@dataclass(frozen=True, slots=True)
class SeededIdentity:
    workspace_id: UUID
    member: SeededUser


def _seed_identity(session: Session) -> SeededIdentity:
    def _create_user(email: str, password: str, *, is_superuser: bool = False) -> SeededUser:
        user = User(
            email=email,
            email_normalized=email.lower(),
            hashed_password=hash_password(password),
            is_active=True,
            is_verified=True,
            is_superuser=is_superuser,
        )
        session.add(user)
        session.flush()
        return SeededUser(id=user.id, email=email, password=password)

    admin = _create_user("admin@example.com", "admin_pass", is_superuser=True)
    member = _create_user("member@example.com", "member_pass")

    workspace = Workspace(name="Primary Workspace", slug="primary")
    session.add(workspace)
    session.flush()

    rbac = RbacService(session=session)
    rbac.sync_registry()
    admin_role = rbac.get_role_by_slug(slug="global-admin")
    global_user_role = rbac.get_role_by_slug(slug="global-user")
    member_role = rbac.get_role_by_slug(slug="workspace-member")
    if global_user_role is not None:
        for user_id in (admin.id, member.id):
            rbac.assign_role_if_missing(
                user_id=user_id,
                role_id=global_user_role.id,
                workspace_id=None,
            )
    if admin_role is not None:
        rbac.assign_role_if_missing(user_id=admin.id, role_id=admin_role.id, workspace_id=None)
    if member_role is not None:
        rbac.assign_role_if_missing(
            user_id=member.id,
            role_id=member_role.id,
            workspace_id=workspace.id,
        )

    session.add(
        WorkspaceMembership(
            user_id=member.id,
            workspace_id=workspace.id,
            is_default=True,
        )
    )

    session.commit()

    return SeededIdentity(
        workspace_id=workspace.id,
        member=member,
    )


@pytest_asyncio.fixture()
async def committed_app(empty_database_settings):
    run_migrations(empty_database_settings)
    app = create_app(settings=empty_database_settings)
    settings_ref = {"value": empty_database_settings}
    app.state.settings = settings_ref["value"]
    app.dependency_overrides[get_settings] = lambda: settings_ref["value"]
    async with LifespanManager(app):
        yield app


@pytest_asyncio.fixture()
async def committed_client(committed_app):
    async with AsyncClient(
        transport=ASGITransport(app=committed_app),
        base_url="http://testserver",
    ) as client:
        yield client


class _SseCollector:
    def __init__(self) -> None:
        self.events: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        self._buffer = ""
        self._current: dict[str, str] = {}
        self._data_lines: list[str] = []

    def feed(self, chunk: bytes) -> None:
        if not chunk:
            return
        self._buffer += chunk.decode("utf-8", errors="replace")
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.rstrip("\r")
            self._parse_line(line)

    def _parse_line(self, line: str) -> None:
        if line == "":
            if self._data_lines:
                self._current["data"] = "\n".join(self._data_lines)
            if self._current:
                self.events.put_nowait(self._current)
            self._current = {}
            self._data_lines = []
            return
        if line.startswith(":"):
            return
        if line.startswith("event:"):
            self._current["event"] = line[len("event:") :].strip()
        elif line.startswith("id:"):
            self._current["id"] = line[len("id:") :].strip()
        elif line.startswith("data:"):
            self._data_lines.append(line[len("data:") :].strip())


async def _wait_for_event(
    queue: asyncio.Queue[dict[str, str]],
    *,
    expected: set[str],
    timeout: float = 10.0,
) -> dict[str, str]:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise TimeoutError(f"Timed out waiting for SSE event(s): {sorted(expected)}")
        event = await asyncio.wait_for(queue.get(), timeout=remaining)
        if event.get("event") in expected:
            return event


async def _open_sse_stream(
    app,
    *,
    path: str,
    headers: dict[str, str],
    query_string: str = "",
) -> tuple[asyncio.Task[None], _SseCollector, asyncio.Event]:
    collector = _SseCollector()
    disconnect = asyncio.Event()
    request_sent = False

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": query_string.encode("utf-8"),
        "headers": [
            (key.lower().encode("latin-1"), value.encode("latin-1"))
            for key, value in headers.items()
        ],
        "client": ("testclient", 123),
        "server": ("testserver", 80),
    }

    async def receive() -> dict[str, Any]:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.body":
            collector.feed(message.get("body", b""))

    task = asyncio.create_task(app(scope, receive, send))
    return task, collector, disconnect


async def test_document_change_stream_round_trip(
    committed_client: AsyncClient,
    committed_app,
) -> None:
    session_factory = get_sessionmaker_from_app(committed_app)
    with session_factory() as session:
        seed_identity = _seed_identity(session)

    member = seed_identity.member
    token, _ = await login(committed_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"Authorization": f"Bearer {token}"}

    request_timeout = 15.0

    baseline = await committed_client.post(
        f"{workspace_base}/documents",
        headers={**headers, "Idempotency-Key": "idem-stream-baseline"},
        files={"file": ("baseline.txt", b"baseline", "text/plain")},
        timeout=request_timeout,
    )
    assert baseline.status_code == 201, baseline.text

    task, collector, disconnect = await _open_sse_stream(
        committed_app,
        path=f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/stream",
        headers={**headers, "Accept": "text/event-stream"},
    )
    try:
        ready = await _wait_for_event(collector.events, expected={"ready"})
        ready_payload = json.loads(ready["data"])
        start_token = ready_payload.get("lastId")
        assert start_token, "Expected stream ready payload to include a cursor"

        created = await committed_client.post(
            f"{workspace_base}/documents",
            headers={**headers, "Idempotency-Key": "idem-stream-change"},
            files={"file": ("streamed.txt", b"streamed", "text/plain")},
            timeout=request_timeout,
        )
        assert created.status_code == 201, created.text
        created_id = created.json()["id"]

        change_event = await _wait_for_event(collector.events, expected={"document.changed"})
        change_payload = json.loads(change_event["data"])
        assert change_payload["documentId"] == created_id
        assert change_payload["op"] == "upsert"
        assert change_payload.get("id")
    finally:
        disconnect.set()
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except asyncio.TimeoutError:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    delta = await committed_client.get(
        f"{workspace_base}/documents/delta",
        headers=headers,
        params={"since": start_token, "limit": 100},
        timeout=request_timeout,
    )
    assert delta.status_code == 200, delta.text
    delta_payload = delta.json()
    delta_ids = [item["documentId"] for item in delta_payload.get("changes", [])]
    assert created_id in delta_ids

    listing = await committed_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={
            "filters": json.dumps(
                [{"id": "id", "operator": "in", "value": [created_id]}]
            )
        },
        timeout=request_timeout,
    )
    assert listing.status_code == 200, listing.text
    items = listing.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == created_id
