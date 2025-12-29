"""Tests covering the asynchronous session dependency wiring."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

import pytest
from fastapi import Depends, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.db.mixins import generate_uuid7
from ade_api.db.session import get_session


@pytest.mark.asyncio
async def test_session_dependency_commits_and_populates_context(
    db_connection,
    settings,
    seed_identity,
):
    """The session dependency should attach to the request and commit writes."""

    route_path = "/__tests__/configurations"
    workspace_id = seed_identity.workspace_id
    workspace_id_str = str(workspace_id)

    from ade_api.main import create_app
    from ade_api.settings import get_settings

    app = create_app(settings=settings)

    app.dependency_overrides[get_settings] = lambda: app.state.settings

    async def _get_session(request: Request) -> AsyncIterator[AsyncSession]:
        session = AsyncSession(
            bind=db_connection,
            expire_on_commit=False,
            autoflush=False,
        )

        nested = session.begin_nested()
        await nested.start()

        @event.listens_for(session.sync_session, "after_transaction_end")
        def _restart_savepoint(sync_session, transaction) -> None:
            if transaction.nested and not transaction._parent.nested:
                sync_session.begin_nested()

        request.state.db_session = session
        error: BaseException | None = None
        try:
            yield session
        except BaseException as exc:
            error = exc
            raise
        finally:
            try:
                if session.in_transaction():
                    commit_on_error = session.info.pop("force_commit_on_error", False)
                    if error is None or commit_on_error:
                        try:
                            await session.commit()
                        except Exception:
                            await session.rollback()
                            raise
                    else:
                        await session.rollback()
            finally:
                if getattr(request.state, "db_session", None) is session:
                    request.state.db_session = None
                await session.close()

    app.dependency_overrides[get_session] = _get_session

    @app.post(route_path)
    async def _create_config(
        request: Request,
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> dict[str, bool | str]:
        assert isinstance(session, AsyncSession)
        assert request.state.db_session is session

        configuration_id = str(generate_uuid7())
        now_iso = datetime.now(UTC).isoformat()
        payload = {
            "id": configuration_id,
            "workspace_id": workspace_id_str,
            "display_name": "Session Configuration",
            "status": "draft",
            "content_digest": None,
            "activated_at": None,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        await session.execute(
            text(
                """
                INSERT INTO configurations (
                    id,
                    workspace_id,
                    display_name,
                    status,
                    content_digest,
                    activated_at,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :workspace_id,
                    :display_name,
                    :status,
                    :content_digest,
                    :activated_at,
                    :created_at,
                    :updated_at
                )
                """
            ),
            payload,
        )
        return {"session_attached": True, "configuration_id": configuration_id}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(route_path)
        response.raise_for_status()
        data = response.json()

    configuration_id = data["configuration_id"]
    assert data["session_attached"] is True

    result = await db_connection.execute(
        text("SELECT COUNT(1) FROM configurations WHERE id = :configuration_id"),
        {"configuration_id": configuration_id},
    )
    assert result.scalar_one() == 1
