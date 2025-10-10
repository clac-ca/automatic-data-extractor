"""Tests for shared security dependencies."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.security import SecurityScopes
from starlette.requests import Request

from ade.api.security import require_csrf, require_global, require_workspace
from ade.db.session import get_sessionmaker
from ade.features.auth.service import AuthenticatedIdentity
from ade.features.roles.service import ensure_user_principal
from ade.features.users.models import User


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_require_workspace_allows_member(app, seed_identity) -> None:
    dependency = require_workspace("Workspace.Members.Read")
    session_factory = get_sessionmaker(settings=app.state.settings)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/workspaces/{workspace_id}/members",
        "headers": [],
        "query_string": b"",
        "path_params": {"workspace_id": seed_identity["workspace_id"]},
    }
    request = Request(scope)

    async with session_factory() as session:
        user = await session.get(User, seed_identity["workspace_owner"]["id"])
        assert user is not None
        principal = await ensure_user_principal(session=session, user=user)
        identity = AuthenticatedIdentity(
            user=user, principal=principal, credentials="bearer_token"
        )

        result = await dependency(
            request,
            SecurityScopes(scopes=["{workspace_id}"]),
            identity,
            session,
        )
        assert result.id == identity.user.id


@pytest.mark.asyncio
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
    assert excinfo.value.detail["permission"] == "Workspace.Documents.Read"


@pytest.mark.asyncio
async def test_require_workspace_rejects_unauthorised_user(app, seed_identity) -> None:
    dependency = require_workspace("Workspace.Documents.Read")
    session_factory = get_sessionmaker(settings=app.state.settings)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/workspaces/{workspace_id}/documents",
        "headers": [],
        "query_string": b"",
        "path_params": {"workspace_id": seed_identity["workspace_id"]},
    }
    request = Request(scope)

    async with session_factory() as session:
        user = await session.get(User, seed_identity["orphan"]["id"])
        assert user is not None
        principal = await ensure_user_principal(session=session, user=user)
        identity = AuthenticatedIdentity(
            user=user, principal=principal, credentials="bearer_token"
        )

        with pytest.raises(HTTPException) as excinfo:
            await dependency(
                request,
                SecurityScopes(scopes=[]),
                identity,
                session,
            )

    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == {
        "error": "forbidden",
        "permission": "Workspace.Documents.Read",
        "scope_type": "workspace",
        "scope_id": seed_identity["workspace_id"],
    }


@pytest.mark.asyncio
async def test_require_csrf_noops_for_api_key_identity(app, seed_identity) -> None:
    session_factory = get_sessionmaker(settings=app.state.settings)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/documents",
        "headers": [],
        "query_string": b"",
        "path_params": {},
    }
    request = Request(scope)

    async with session_factory() as session:
        user = await session.get(User, seed_identity["admin"]["id"])
        assert user is not None
        principal = await ensure_user_principal(session=session, user=user)
        identity = AuthenticatedIdentity(
            user=user,
            principal=principal,
            credentials="api_key",
        )
        settings = app.state.settings

        await require_csrf(request, identity, session, settings)


def test_openapi_includes_security_schemes(app) -> None:
    schema = app.openapi()

    schemes = schema["components"]["securitySchemes"]
    assert schemes["SessionCookie"]["type"] == "apiKey"
    assert schemes["SessionCookie"]["in"] == "cookie"
    assert schemes["SessionCookie"]["name"] == app.state.settings.session_cookie_name

    assert schemes["HTTPBearer"]["type"] == "http"
    assert schemes["HTTPBearer"]["scheme"] == "bearer"

    assert schemes["APIKeyHeader"]["type"] == "apiKey"
    assert schemes["APIKeyHeader"]["in"] == "header"
    assert schemes["APIKeyHeader"]["name"] == "X-API-Key"

    assert {"SessionCookie": []} in schema["security"]
    assert {"HTTPBearer": []} in schema["security"]
    assert {"APIKeyHeader": []} in schema["security"]
