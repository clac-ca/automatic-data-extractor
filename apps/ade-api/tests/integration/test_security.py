"""Tests for shared security dependencies."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.security import SecurityScopes
from httpx import AsyncClient
from starlette.requests import Request

from ade_api.features.auth.service import AuthenticatedIdentity
from ade_api.features.roles.service import ensure_user_principal
from ade_api.features.users.models import User
from ade_api.settings import get_settings
from ade_api.shared.db.session import get_sessionmaker
from ade_api.shared.dependency import require_csrf, require_global, require_workspace

pytestmark = pytest.mark.asyncio
SESSION_COOKIE = get_settings().session_cookie_name


async def test_require_global_allows_authorised_user(app, seed_identity) -> None:
    dependency = require_global("Roles.Read.All")
    session_factory = get_sessionmaker(settings=app.state.settings)

    async with session_factory() as session:
        user = await session.get(User, seed_identity["admin"]["id"])
        assert user is not None
        principal = await ensure_user_principal(session=session, user=user)
        identity = AuthenticatedIdentity(
            user=user, principal=principal, credentials="bearer_token"
        )

        result = await dependency(SecurityScopes(scopes=[]), identity, session)
        assert result.id == identity.user.id


async def test_require_global_rejects_missing_permission(app, seed_identity) -> None:
    dependency = require_global("Roles.Read.All")
    session_factory = get_sessionmaker(settings=app.state.settings)

    async with session_factory() as session:
        user = await session.get(User, seed_identity["member"]["id"])
        assert user is not None
        principal = await ensure_user_principal(session=session, user=user)
        identity = AuthenticatedIdentity(
            user=user, principal=principal, credentials="bearer_token"
        )

        with pytest.raises(HTTPException) as excinfo:
            await dependency(SecurityScopes(scopes=[]), identity, session)

    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == {
        "error": "forbidden",
        "permission": "Roles.Read.All",
        "scope_type": "global",
        "scope_id": None,
    }


async def test_require_workspace_allows_member(app, seed_identity) -> None:
    dependency = require_workspace("Workspace.Documents.Read")
    session_factory = get_sessionmaker(settings=app.state.settings)

    async with session_factory() as session:
        user = await session.get(User, seed_identity["workspace_owner"]["id"])
        assert user is not None
        principal = await ensure_user_principal(session=session, user=user)
        identity = AuthenticatedIdentity(
            user=user, principal=principal, credentials="bearer_token"
        )

        result = await dependency(
            Request({
                "type": "http",
                "method": "GET",
                "path": "/api/v1/workspaces/abc/documents",
                "headers": [],
                "query_string": b"",
                "path_params": {"workspace_id": seed_identity["workspace_id"]},
            }),
            SecurityScopes(scopes=["{workspace_id}"]),
            identity,
            session,
        )
        assert result.id == identity.user.id


async def test_require_workspace_rejects_missing_scope(app, seed_identity) -> None:
    dependency = require_workspace("Workspace.Documents.Read")
    session_factory = get_sessionmaker(settings=app.state.settings)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/workspaces/missing/documents",
        "headers": [],
        "query_string": b"",
        "path_params": {},
    }
    request = Request(scope)

    async with session_factory() as session:
        user = await session.get(User, seed_identity["workspace_owner"]["id"])
        assert user is not None
        principal = await ensure_user_principal(session=session, user=user)
        identity = AuthenticatedIdentity(
            user=user, principal=principal, credentials="bearer_token"
        )

        with pytest.raises(HTTPException) as excinfo:
            await dependency(
                request,
                SecurityScopes(scopes=["{workspace_id}"]),
                identity,
                session,
            )

    assert excinfo.value.status_code == 422
    assert excinfo.value.detail["error"] == "invalid_scope"


async def test_require_csrf_accepts_non_cookie_credentials(app, async_client) -> None:
    dependency = require_csrf
    request = Request({
        "type": "http",
        "method": "POST",
        "headers": [],
        "query_string": b"",
        "path": "/api/v1/documents",
    })

    settings = app.state.settings
    session_factory = get_sessionmaker(settings=settings)

    async with session_factory() as session:
        identity = AuthenticatedIdentity(
            user=None,  # type: ignore[arg-type]
            principal=None,  # type: ignore[arg-type]
            credentials="bearer_token",
        )
        await dependency(request, identity, session, settings)
        # Should not raise because non-cookie credentials bypass CSRF.


async def test_require_csrf_rejects_invalid_cookie(app, async_client, seed_identity) -> None:
    session_cookie = await _login(async_client, seed_identity["admin"]["email"], "admin-password")
    request = Request({
        "type": "http",
        "method": "POST",
        "headers": [(b"Cookie", f"{SESSION_COOKIE}={session_cookie}".encode())],
        "query_string": b"",
        "path": "/api/v1/documents",
    })

    settings = app.state.settings
    session_factory = get_sessionmaker(settings=settings)

    async with session_factory() as session:
        identity = await _load_identity(session, seed_identity["admin"]["id"])
        with pytest.raises(HTTPException) as excinfo:
            await require_csrf(request, identity, session, settings)

    assert excinfo.value.status_code == 401


async def test_auth_disabled_returns_session_without_credentials(
    async_client: AsyncClient,
    override_app_settings,
) -> None:
    """Requests should resolve a session automatically when auth is disabled."""

    override_app_settings(
        auth_disabled=True,
        auth_disabled_user_email="dev@example.test",
    )
    response = await async_client.get("/api/v1/auth/session")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["user"]["email"] == "dev@example.test"
    assert payload["expires_at"] is None
    assert payload["refresh_expires_at"] is None


async def test_auth_disabled_bypasses_workspace_permissions(
    async_client: AsyncClient,
    override_app_settings,
    seed_identity,
) -> None:
    """Workspace endpoints should be accessible without login when auth is disabled."""

    override_app_settings(
        auth_disabled=True,
        auth_disabled_user_email="dev@example.test",
    )
    response = await async_client.get(f"/api/v1/workspaces/{seed_identity['workspace_id']}")

    assert response.status_code == 200, response.text


async def _load_identity(session, user_id: str) -> AuthenticatedIdentity:
    user = await session.get(User, user_id)
    assert user is not None
    principal = await ensure_user_principal(session=session, user=user)
    return AuthenticatedIdentity(user=user, principal=principal, credentials="session_cookie")


async def _login(client, email: str, password: str) -> str:
    response = await client.post(
        "/api/v1/auth/session",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    token = client.cookies.get(SESSION_COOKIE)
    assert token
    return token
