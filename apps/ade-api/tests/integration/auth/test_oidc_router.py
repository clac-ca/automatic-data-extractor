"""OIDC auth flow smoke tests."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from pydantic import SecretStr

from ade_api.features.auth import oidc_router
from ade_api.settings import Settings

pytestmark = pytest.mark.asyncio


class StubOidcClient:
    def __init__(
        self,
        *,
        authorization_url: str = "https://idp.example.com/auth",
        token: dict[str, Any] | None = None,
        claims: dict[str, Any] | None = None,
    ) -> None:
        self.authorization_url = authorization_url
        self.token = token or {"access_token": "access-token", "id_token": "id-token"}
        self.claims = claims or {"sub": "oidc-subject", "email": "oidc@example.com"}
        self.metadata = {"token_endpoint": "https://idp.example.com/token"}

    def create_authorization_url(self, **_kwargs: Any) -> tuple[str, dict[str, Any]]:
        return self.authorization_url, {}

    async def fetch_token(self, **_kwargs: Any) -> dict[str, Any]:
        return self.token

    def parse_id_token(self, _token: dict[str, Any]) -> dict[str, Any]:
        return self.claims

    async def userinfo(self, **_kwargs: Any) -> dict[str, Any]:
        return self.claims


def _enable_oidc(override_app_settings) -> Settings:
    return override_app_settings(
        oidc_enabled=True,
        oidc_client_id="demo-client",
        oidc_client_secret=SecretStr("demo-secret"),
        oidc_issuer="https://issuer.example.com",
        oidc_redirect_url="https://app.example.com/auth/callback",
        auth_sso_auto_provision=True,
    )


async def test_oidc_authorize_sets_state_and_redirects(
    async_client: AsyncClient,
    override_app_settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _enable_oidc(override_app_settings)
    client = StubOidcClient()
    monkeypatch.setattr(oidc_router, "_oidc_client", lambda _settings, _provider: client)

    response = await async_client.get(
        "/api/v1/auth/oidc/oidc/authorize?return_to=/runs",
        follow_redirects=False,
    )

    assert response.status_code in {302, 307}
    assert response.headers["location"] == client.authorization_url
    assert async_client.cookies.get("ade_oidc_state")
    return_to = async_client.cookies.get("ade_oidc_return_to")
    assert return_to is not None
    assert return_to.strip('"') == "/runs"
    assert settings.oidc_redirect_url


async def test_oidc_callback_sets_session_and_redirects(
    async_client: AsyncClient,
    override_app_settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _enable_oidc(override_app_settings)
    client = StubOidcClient()
    monkeypatch.setattr(oidc_router, "_oidc_client", lambda _settings, _provider: client)

    async_client.cookies.set("ade_oidc_state", "state-123")
    async_client.cookies.set("ade_oidc_return_to", "/runs")

    response = await async_client.get(
        "/api/v1/auth/oidc/oidc/callback?state=state-123&code=demo-code",
        follow_redirects=False,
    )

    assert response.status_code in {302, 307}
    expected = f"{settings.frontend_url or settings.server_public_url}/auth/callback?return_to=/runs"
    assert response.headers["location"] == expected
    assert async_client.cookies.get(settings.session_cookie_name)
    assert async_client.cookies.get(settings.session_csrf_cookie_name)
    set_cookies = [value.lower() for value in response.headers.get_list("set-cookie")]
    assert any("ade_oidc_state=" in cookie and "max-age=0" in cookie for cookie in set_cookies)
    assert any("ade_oidc_return_to=" in cookie and "max-age=0" in cookie for cookie in set_cookies)


async def test_oidc_callback_json_mode_returns_ok(
    async_client: AsyncClient,
    override_app_settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _enable_oidc(override_app_settings)
    client = StubOidcClient()
    monkeypatch.setattr(oidc_router, "_oidc_client", lambda _settings, _provider: client)

    async_client.cookies.set("ade_oidc_state", "state-456")
    async_client.cookies.set("ade_oidc_return_to", "/")

    response = await async_client.get(
        "/api/v1/auth/oidc/oidc/callback?state=state-456&code=demo-code&response_mode=json",
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert async_client.cookies.get(settings.session_cookie_name)
    assert async_client.cookies.get(settings.session_csrf_cookie_name)
