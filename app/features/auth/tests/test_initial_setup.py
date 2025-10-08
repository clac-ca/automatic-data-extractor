"""Initial setup flow tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.db.session import get_sessionmaker
from app.features.auth.security import hash_password
from app.features.users.models import UserRole
from app.features.users.repository import UsersRepository


pytestmark = pytest.mark.asyncio


async def test_initial_setup_creates_admin_and_sets_session(
    async_client: AsyncClient,
) -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        await session.execute(text("DELETE FROM api_keys"))
        await session.execute(text("DELETE FROM system_settings"))
        await session.execute(text("DELETE FROM users"))
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
    assert data["user"]["role"] == "admin"
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


async def test_initial_setup_rejected_when_admin_exists(
    async_client: AsyncClient,
) -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        repo = UsersRepository(session)
        await repo.create(
            email="existing@example.test",
            password_hash=hash_password("Password123!"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        await session.commit()

    status_response = await async_client.get("/api/setup/status")
    assert status_response.status_code == 200
    assert status_response.json()["requires_setup"] is False

    response = await async_client.post(
        "/api/setup",
        json={"email": "new@example.test", "password": "NewPassword123!"},
    )
    assert response.status_code == 409
