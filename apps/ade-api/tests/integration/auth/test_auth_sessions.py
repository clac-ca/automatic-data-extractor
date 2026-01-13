from __future__ import annotations

import anyio
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ade_api.models import AccessToken
from ade_api.settings import Settings

pytestmark = pytest.mark.asyncio


def _login_form(email: str, password: str) -> dict[str, str]:
    return {"username": email, "password": password}


async def test_cookie_login_sets_session_and_bootstrap(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
    db_session,
) -> None:
    admin = seed_identity.admin

    response = await async_client.post(
        "/api/v1/auth/cookie/login",
        data=_login_form(admin.email, admin.password),
    )
    assert response.status_code == 204, response.text
    assert async_client.cookies.get(settings.session_cookie_name)

    def _load_tokens():
        return db_session.execute(select(AccessToken)).scalars().all()

    tokens = await anyio.to_thread.run_sync(_load_tokens)
    assert len(tokens) == 1
    assert tokens[0].user_id == admin.id

    bootstrap = await async_client.get("/api/v1/me/bootstrap")
    assert bootstrap.status_code == 200, bootstrap.text
    payload = bootstrap.json()
    assert payload["user"]["email"] == admin.email


async def test_cookie_logout_revokes_access_tokens(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
    db_session,
) -> None:
    admin = seed_identity.admin

    response = await async_client.post(
        "/api/v1/auth/cookie/login",
        data=_login_form(admin.email, admin.password),
    )
    assert response.status_code == 204, response.text

    bootstrap = await async_client.get("/api/v1/me/bootstrap")
    assert bootstrap.status_code == 200, bootstrap.text
    csrf_cookie = async_client.cookies.get(settings.session_csrf_cookie_name)
    assert csrf_cookie

    logout = await async_client.post(
        "/api/v1/auth/cookie/logout",
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert logout.status_code == 204, logout.text
    assert not async_client.cookies.get(settings.session_cookie_name)

    def _load_tokens():
        return db_session.execute(select(AccessToken)).scalars().all()

    tokens = await anyio.to_thread.run_sync(_load_tokens)
    assert tokens == []
