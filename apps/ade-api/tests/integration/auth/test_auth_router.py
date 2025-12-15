"""Authentication endpoint smoke tests for the new auth module."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from pydantic import SecretStr

from ade_api.db.engine import ensure_database_ready, reset_database_state
from ade_api.db.session import reset_session_state
from ade_api.models import User
from ade_api.settings import get_settings
from tests.utils import login

pytestmark = pytest.mark.asyncio


async def test_login_and_refresh(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Password login should return tokens, cookies, and allow refresh."""

    admin = seed_identity["admin"]
    response = await async_client.post(
        "/api/v1/auth/session",
        json={"email": admin["email"], "password": admin["password"]},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    session = payload["session"]
    cookie_name = get_settings().session_cookie_name

    assert session["token_type"] == "bearer"
    assert session["refresh_token"]
    assert session["expires_in"] > 0
    assert session["refresh_expires_in"] > 0
    assert session["expires_at"]
    assert session["refresh_expires_at"]
    bootstrap = await async_client.get("/api/v1/me/bootstrap")
    assert bootstrap.status_code == 200, bootstrap.text
    context = bootstrap.json()
    assert context["user"]["email"] == admin["email"]
    assert async_client.cookies.get(cookie_name) == session["access_token"]

    refresh = await async_client.post(
        "/api/v1/auth/session/refresh",
        json={"refresh_token": session["refresh_token"]},
    )
    assert refresh.status_code == 200, refresh.text
    refreshed = refresh.json()["session"]
    assert refreshed["access_token"]
    assert refreshed["token_type"] == "bearer"
    assert async_client.cookies.get(cookie_name) == refreshed["access_token"]


async def test_refresh_prefers_body_over_cookie(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Body-supplied refresh tokens should override cookies."""

    admin = seed_identity["admin"]
    _, payload = await login(
        async_client,
        email=admin["email"],
        password=admin["password"],
    )
    session = payload["session"]

    refresh_cookie = get_settings().session_refresh_cookie_name
    async_client.cookies.set(refresh_cookie, "stale-cookie-token")

    response = await async_client.post(
        "/api/v1/auth/session/refresh",
        json={"refresh_token": session["refresh_token"]},
    )
    assert response.status_code == 200, response.text
    data = response.json()["session"]
    assert data["access_token"]
    assert data["refresh_token"]


async def test_refresh_falls_back_to_cookie(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Requests without a body should refresh using the cookie token."""

    admin = seed_identity["admin"]
    _, payload = await login(
        async_client,
        email=admin["email"],
        password=admin["password"],
    )
    session = payload["session"]

    refresh_cookie = get_settings().session_refresh_cookie_name
    async_client.cookies.set(refresh_cookie, session["refresh_token"])

    response = await async_client.post("/api/v1/auth/session/refresh")
    assert response.status_code == 200, response.text
    data = response.json()["session"]
    assert data["access_token"]
    assert data["refresh_token"]


async def test_invalid_credentials_rejected(async_client: AsyncClient) -> None:
    """Bad credentials should return 401."""

    response = await async_client.post(
        "/api/v1/auth/session",
        json={"email": "missing@example.com", "password": "nope"},
    )
    assert response.status_code == 401


async def test_setup_status_when_users_exist(async_client: AsyncClient) -> None:
    """When users are present, setup should be marked complete."""

    response = await async_client.get("/api/v1/auth/setup")
    assert response.status_code == 200
    payload = response.json()
    assert payload["requires_setup"] is False
    assert payload["has_users"] is True


async def test_setup_returns_created_on_first_admin(
    async_client: AsyncClient,
    override_app_settings,
    tmp_path: Path,
) -> None:
    """First-run setup should create the admin and return 201 with tokens."""

    db_root = tmp_path / "auth-setup-created"
    db_path = db_root / "api.sqlite"
    workspace_root = db_root / "workspaces"

    reset_database_state()
    reset_session_state()

    settings = override_app_settings(
        database_dsn=f"sqlite+aiosqlite:///{db_path}",
        workspaces_dir=workspace_root,
        documents_dir=workspace_root,
        configs_dir=workspace_root,
        runs_dir=workspace_root,
        venvs_dir=db_root / "venvs",
        pip_cache_dir=db_root / "cache" / "pip",
    )
    await ensure_database_ready(settings)

    status_response = await async_client.get("/api/v1/auth/setup")
    assert status_response.status_code == 200, status_response.text
    status_payload = status_response.json()
    assert status_payload["requires_setup"] is True
    assert status_payload["has_users"] is False

    response = await async_client.post(
        "/api/v1/auth/setup",
        json={
            "email": "first@example.com",
            "password": "Password123!",
            "display_name": "First Admin",
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    session = payload["session"]
    assert session["access_token"]
    assert session["token_type"] == "bearer"

    bootstrap = await async_client.get("/api/v1/me/bootstrap")
    assert bootstrap.status_code == 200, bootstrap.text
    context = bootstrap.json()
    assert context["user"]["email"] == "first@example.com"
    assert context["roles"] == ["global-admin"]
    assert "workspaces.create" in context["permissions"]

    verify_response = await async_client.get("/api/v1/auth/setup")
    assert verify_response.status_code == 200, verify_response.text
    verify_payload = verify_response.json()
    assert verify_payload["requires_setup"] is False
    assert verify_payload["has_users"] is True


async def test_setup_conflict_when_users_exist(async_client: AsyncClient) -> None:
    """POST /auth/setup should return 409 once users exist."""

    response = await async_client.post(
        "/api/v1/auth/setup",
        json={
            "email": "first@example.com",
            "password": "password123!",
            "display_name": "First Admin",
        },
    )
    assert response.status_code == 409


async def test_list_auth_providers_default_password_only(
    async_client: AsyncClient,
    override_app_settings,
) -> None:
    """Provider discovery should expose password login when SSO is disabled."""

    override_app_settings(auth_force_sso=False, oidc_enabled=False)
    response = await async_client.get("/api/v1/auth/providers")
    assert response.status_code == 200
    payload = response.json()
    assert payload["force_sso"] is False
    assert payload["providers"] == [
        {
            "id": "password",
            "label": "Email & password",
            "type": "password",
            "start_url": "/api/v1/auth/session",
            "icon_url": None,
        }
    ]


async def test_list_auth_providers_force_sso(
    async_client: AsyncClient,
    override_app_settings,
) -> None:
    """When SSO is forced and enabled, only the SSO provider should appear."""

    override_app_settings(
        auth_force_sso=True,
        oidc_enabled=True,
        oidc_client_id="demo-client",
        oidc_client_secret=SecretStr("demo-secret"),
        oidc_issuer="https://issuer.example.com",
        oidc_redirect_url="https://app.example.com/auth/callback",
    )
    response = await async_client.get("/api/v1/auth/providers")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["force_sso"] is True
    assert payload["providers"] == [
        {
            "id": "sso",
            "label": "Single sign-on",
            "type": "oidc",
            "start_url": "/api/v1/auth/sso/sso/authorize",
            "icon_url": None,
        }
    ]


async def test_logout_returns_no_content(async_client: AsyncClient) -> None:
    """Logout should be a no-op but return 204."""

    response = await async_client.delete("/api/v1/auth/session")
    assert response.status_code == 204


async def test_login_rejects_inactive_user(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
    session,
) -> None:
    """Inactive accounts should not receive new sessions."""

    member = seed_identity["member"]
    user = await session.get(User, member["id"])
    assert user is not None
    user.is_active = False
    await session.flush()

    response = await async_client.post(
        "/api/v1/auth/session",
        json={"email": member["email"], "password": member["password"]},
    )
    assert response.status_code == 403
    payload = response.json()
    assert payload["detail"]["error"] == "inactive_user"


async def test_access_token_rejected_after_deactivation(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
    session,
) -> None:
    """Existing access tokens should be blocked once the user is inactive."""

    member = seed_identity["member"]
    token, _ = await login(
        async_client,
        email=member["email"],
        password=member["password"],
    )

    user = await session.get(User, member["id"])
    assert user is not None
    user.is_active = False
    await session.flush()

    response = await async_client.get(
        "/api/v1/me/bootstrap",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert "inactive" in response.json()["detail"].lower()
