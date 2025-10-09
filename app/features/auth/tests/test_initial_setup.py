"""Initial setup flow tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.db.session import get_sessionmaker
from app.features.roles.models import Role, UserGlobalRole


pytestmark = pytest.mark.asyncio


async def test_initial_setup_creates_admin_and_sets_session(
    async_client: AsyncClient,
) -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        await session.execute(text("DELETE FROM user_global_roles"))
        await session.execute(text("DELETE FROM api_keys"))
        await session.execute(text("DELETE FROM system_settings"))
        await session.execute(text("DELETE FROM users"))
        await session.execute(text("DELETE FROM workspace_membership_roles"))
        await session.execute(text("DELETE FROM role_permissions"))
        await session.execute(text("DELETE FROM roles"))
        await session.execute(text("DELETE FROM permissions"))
        await session.commit()

    status_response = await async_client.get("/api/setup/status")
    assert status_response.status_code == 200
    assert status_response.json() == {
        "requires_setup": True,
        "completed_at": None,
    }

    payload = {
        "email": "owner@example.test",
        "password": "ChangeMe123!",
        "displayName": "Owner",
    }

    response = await async_client.post("/api/setup", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["user"]["email"] == "owner@example.test"
    assert "Workspaces.Create" in data["user"].get("permissions", [])
    assert data["expires_at"]
    assert data["refresh_expires_at"]

    session_cookie = async_client.cookies.get("ade_session")
    refresh_cookie = async_client.cookies.get("ade_refresh")
    csrf_cookie = async_client.cookies.get("ade_csrf")
    assert session_cookie
    assert refresh_cookie
    assert csrf_cookie

    repeat = await async_client.post("/api/setup", json=payload)
    assert repeat.status_code == 409

    status_after = await async_client.get("/api/setup/status")
    assert status_after.status_code == 200
    after_payload = status_after.json()
    assert after_payload["requires_setup"] is False
    assert isinstance(after_payload["completed_at"], str)

    async with session_factory() as session:
        assignments = await session.execute(
            text("SELECT user_id, role_id FROM user_global_roles")
        )
        rows = assignments.fetchall()
        assert len(rows) == 1


async def test_initial_setup_rejected_when_admin_exists(
    async_client: AsyncClient,
) -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        await session.execute(text("DELETE FROM user_global_roles"))
        user = await session.execute(
            text(
                """
                INSERT INTO users (user_id, email, email_canonical, is_active, is_service_account, failed_login_count, created_at, updated_at)
                VALUES (:id, :email, :email, 1, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING user_id
                """
            ),
            {"id": "user_existing", "email": "existing@example.test"},
        )
        user_id = user.scalar_one()
        role_result = await session.execute(
            select(Role).where(Role.scope == "global", Role.slug == "global-admin")
        )
        role = role_result.scalar_one()
        session.add(UserGlobalRole(user_id=user_id, role_id=role.id))
        await session.flush()
        await session.commit()

    status_response = await async_client.get("/api/setup/status")
    assert status_response.status_code == 200
    assert status_response.json()["requires_setup"] is False

    response = await async_client.post(
        "/api/setup",
        json={"email": "new@example.test", "password": "NewPassword123!"},
    )
    assert response.status_code == 409
