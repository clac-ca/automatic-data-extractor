"""Initial setup flow tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from apps.api.app.features.roles.models import Role, ScopeType
from apps.api.app.features.roles.service import assign_global_role
from apps.api.app.settings import get_settings
from apps.api.app.shared.db.session import get_sessionmaker
from apps.api.app.shared.db.mixins import generate_ulid


pytestmark = pytest.mark.asyncio
_settings = get_settings()
SESSION_COOKIE = _settings.session_cookie_name
REFRESH_COOKIE = _settings.session_refresh_cookie_name
CSRF_COOKIE = _settings.session_csrf_cookie_name


async def test_initial_setup_creates_admin_and_sets_session(
    async_client: AsyncClient,
) -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        await session.execute(text("DELETE FROM role_assignments"))
        await session.execute(text("DELETE FROM principals"))
        await session.execute(text("DELETE FROM api_keys"))
        await session.execute(text("DELETE FROM system_settings"))
        await session.execute(text("DELETE FROM users"))
        await session.execute(text("DELETE FROM role_permissions"))
        await session.execute(text("DELETE FROM roles"))
        await session.execute(text("DELETE FROM permissions"))
        await session.commit()

    status_response = await async_client.get("/api/v1/setup/status")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["requires_setup"] is True
    assert status_payload["completed_at"] is None

    payload = {
        "email": "owner@example.test",
        "password": "ChangeMe123!",
        "display_name": "Owner",
    }

    response = await async_client.post("/api/v1/setup", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["user"]["email"] == "owner@example.test"
    assert "Workspaces.Create" in data["user"].get("permissions", [])
    assert data["expires_at"]
    assert data["refresh_expires_at"]

    session_cookie = async_client.cookies.get(SESSION_COOKIE)
    refresh_cookie = async_client.cookies.get(REFRESH_COOKIE)
    csrf_cookie = async_client.cookies.get(CSRF_COOKIE)
    assert session_cookie
    assert refresh_cookie
    assert csrf_cookie

    repeat = await async_client.post("/api/v1/setup", json=payload)
    assert repeat.status_code == 409

    status_after = await async_client.get("/api/v1/setup/status")
    assert status_after.status_code == 200
    after_payload = status_after.json()
    assert after_payload["requires_setup"] is False
    assert isinstance(after_payload["completed_at"], str)

    async with session_factory() as session:
        assignments = await session.execute(
            text(
                "SELECT principal_id, role_id, scope_type FROM role_assignments"
            )
        )
        rows = [row for row in assignments.fetchall() if row.scope_type == ScopeType.GLOBAL]
        assert len(rows) == 1


async def test_initial_setup_rejected_when_admin_exists(
    async_client: AsyncClient,
) -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        await session.execute(text("DELETE FROM role_assignments"))
        await session.execute(text("DELETE FROM principals"))
        existing_user_id = generate_ulid()
        user = await session.execute(
            text(
                """
                INSERT INTO users (id, email, email_canonical, is_active, is_service_account, failed_login_count, created_at, updated_at)
                VALUES (:id, :email, :email, 1, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING id
                """
            ),
            {"id": existing_user_id, "email": "existing@example.test"},
        )
        user_id = user.scalar_one()
        role_result = await session.execute(
            select(Role).where(
                Role.scope_type == ScopeType.GLOBAL,
                Role.scope_id.is_(None),
                Role.slug == "global-administrator",
            )
        )
        role = role_result.scalar_one()
        await assign_global_role(
            session=session, user_id=user_id, role_id=role.id
        )
        await session.commit()

    status_response = await async_client.get("/api/v1/setup/status")
    assert status_response.status_code == 200
    assert status_response.json()["requires_setup"] is False

    response = await async_client.post(
        "/api/v1/setup",
        json={"email": "new@example.test", "password": "NewPassword123!"},
    )
    assert response.status_code == 409
