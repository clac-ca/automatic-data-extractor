"""Authentication endpoint smoke tests for the new auth module."""

from __future__ import annotations

import anyio
import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import select

from ade_api.models import AccessToken, User
from ade_api.settings import Settings
from tests.utils import login

pytestmark = pytest.mark.asyncio


def _login_form(email: str, password: str) -> dict[str, str]:
    return {"username": email, "password": password}


async def test_cookie_login_sets_session_and_bootstrap(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
) -> None:
    """Password login should set the session cookie and allow bootstrap."""

    admin = seed_identity.admin
    response = await async_client.post(
        "/api/v1/auth/cookie/login",
        data=_login_form(admin.email, admin.password),
    )
    assert response.status_code == 204, response.text
    cookie_name = settings.session_cookie_name
    assert async_client.cookies.get(cookie_name)

    bootstrap = await async_client.get("/api/v1/me/bootstrap")
    assert bootstrap.status_code == 200, bootstrap.text
    context = bootstrap.json()
    assert context["user"]["email"] == admin.email


async def test_cookie_login_creates_access_token(
    async_client: AsyncClient,
    seed_identity,
    session,
) -> None:
    """Cookie login should persist an access token row."""

    admin = seed_identity.admin
    response = await async_client.post(
        "/api/v1/auth/cookie/login",
        data=_login_form(admin.email, admin.password),
    )
    assert response.status_code == 204, response.text

    def _load_tokens():
        return session.execute(select(AccessToken)).scalars().all()

    tokens = await anyio.to_thread.run_sync(_load_tokens)
    assert len(tokens) == 1
    assert tokens[0].user_id == admin.id


async def test_cookie_logout_clears_access_token(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
    session,
) -> None:
    """Logout should delete access tokens and clear session cookies."""

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
        return session.execute(select(AccessToken)).scalars().all()

    tokens = await anyio.to_thread.run_sync(_load_tokens)
    assert tokens == []


async def test_jwt_login_returns_access_token(async_client: AsyncClient, seed_identity) -> None:
    """JWT login should return a bearer token payload."""

    admin = seed_identity.admin
    response = await async_client.post(
        "/api/v1/auth/jwt/login",
        data=_login_form(admin.email, admin.password),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["access_token"]
    assert payload["token_type"] == "bearer"


async def test_setup_status_when_users_exist(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """When users are present, setup should be marked complete."""

    response = await async_client.get("/api/v1/auth/setup")
    assert response.status_code == 200
    payload = response.json()
    assert payload["setup_required"] is False
    assert payload["registration_mode"] == "closed"


async def test_setup_returns_no_content_on_first_admin(
    async_client: AsyncClient,
    settings: Settings,
) -> None:
    """First-run setup should create the admin and set cookies."""

    status_response = await async_client.get("/api/v1/auth/setup")
    assert status_response.status_code == 200, status_response.text
    status_payload = status_response.json()
    assert status_payload["setup_required"] is True
    assert status_payload["registration_mode"] == "setup-only"

    response = await async_client.post(
        "/api/v1/auth/setup",
        json={
            "email": "first@example.com",
            "password": "Password123!",
            "display_name": "First Admin",
        },
    )
    assert response.status_code == 204, response.text
    assert async_client.cookies.get(settings.session_cookie_name)
    assert async_client.cookies.get(settings.session_csrf_cookie_name)

    bootstrap = await async_client.get("/api/v1/me/bootstrap")
    assert bootstrap.status_code == 200, bootstrap.text
    context = bootstrap.json()
    assert context["user"]["email"] == "first@example.com"
    assert "global-admin" in context["roles"]

    verify_response = await async_client.get("/api/v1/auth/setup")
    assert verify_response.status_code == 200, verify_response.text
    verify_payload = verify_response.json()
    assert verify_payload["setup_required"] is False


async def test_setup_conflict_when_users_exist(async_client: AsyncClient, seed_identity) -> None:
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
            "start_url": "/api/v1/auth/cookie/login",
            "icon_url": None,
        }
    ]


async def test_list_auth_providers_force_sso(
    async_client: AsyncClient,
    override_app_settings,
) -> None:
    """When SSO is forced and enabled, only the OIDC provider should appear."""

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
            "id": "oidc",
            "label": "Single sign-on",
            "type": "oidc",
            "start_url": "/api/v1/auth/oidc/oidc/authorize",
            "icon_url": None,
        }
    ]


async def test_login_rejects_inactive_user(
    async_client: AsyncClient,
    seed_identity,
    session,
) -> None:
    """Inactive accounts should not receive new sessions."""

    member = seed_identity.member
    user = await anyio.to_thread.run_sync(session.get, User, member.id)
    assert user is not None
    user.is_active = False
    await anyio.to_thread.run_sync(session.flush)

    response = await async_client.post(
        "/api/v1/auth/cookie/login",
        data=_login_form(member.email, member.password),
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"] == "LOGIN_BAD_CREDENTIALS"


async def test_access_token_rejected_after_deactivation(
    async_client: AsyncClient,
    seed_identity,
    session,
) -> None:
    """Existing bearer tokens should be blocked once the user is inactive."""

    member = seed_identity.member
    token, _ = await login(
        async_client,
        email=member.email,
        password=member.password,
    )

    user = await anyio.to_thread.run_sync(session.get, User, member.id)
    assert user is not None
    user.is_active = False
    await anyio.to_thread.run_sync(session.flush)

    response = await async_client.get(
        "/api/v1/me/bootstrap",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert "inactive" in response.json()["detail"].lower()
