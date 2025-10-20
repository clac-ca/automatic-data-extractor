"""Tests for shared security dependencies."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.security import SecurityScopes
from starlette.requests import Request

from backend.app.shared.db.session import get_sessionmaker
from backend.app.features.auth.dependencies import require_csrf
from backend.app.features.auth.service import AuthenticatedIdentity
from backend.app.features.roles.dependencies import require_global, require_workspace
from backend.app.features.roles.service import ensure_user_principal
from backend.app.features.users.models import User


pytestmark = pytest.mark.asyncio


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
        "headers": [(b"Cookie", f"backend_app_session={session_cookie}".encode())],
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
    token = client.cookies.get("backend_app_session")
    assert token
    return token
