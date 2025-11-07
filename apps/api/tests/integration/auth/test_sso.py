from __future__ import annotations

from urllib.parse import parse_qsl, urlparse

import pytest
from fastapi import HTTPException

from apps.api.app.settings import reload_settings
from apps.api.app.shared.db.session import get_sessionmaker
from apps.api.app.features.auth.service import AuthService, OIDCProviderMetadata
from apps.api.app.features.roles.service import sync_permission_registry


@pytest.mark.asyncio()
async def test_prepare_sso_login_rejects_external_next(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """prepare_sso_login should reject open redirects to other origins."""

    monkeypatch.setenv("ADE_OIDC_CLIENT_ID", "demo-client")
    monkeypatch.setenv("ADE_OIDC_CLIENT_SECRET", "demo-secret")
    monkeypatch.setenv("ADE_OIDC_ISSUER", "https://issuer.example.com")
    monkeypatch.setenv("ADE_OIDC_REDIRECT_URL", "https://app.example.com/auth/sso/callback")
    monkeypatch.setenv("ADE_OIDC_SCOPES", '["openid","email"]')
    monkeypatch.setenv("ADE_SERVER_PUBLIC_URL", "https://app.example.com")
    settings = reload_settings()

    metadata = OIDCProviderMetadata(
        authorization_endpoint="https://issuer.example.com/authorize",
        token_endpoint="https://issuer.example.com/token",
        jwks_uri="https://issuer.example.com/jwks",
    )

    async def _fake_metadata(self: AuthService) -> OIDCProviderMetadata:
        return metadata

    monkeypatch.setattr(AuthService, "_get_oidc_metadata", _fake_metadata)

    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        service = AuthService(session=session, settings=settings)
        with pytest.raises(HTTPException) as exc:
            await service.prepare_sso_login(return_to="https://malicious.example.com")
        assert exc.value.status_code == 400

    for key in (
        "ADE_OIDC_CLIENT_ID",
        "ADE_OIDC_CLIENT_SECRET",
        "ADE_OIDC_ISSUER",
        "ADE_OIDC_REDIRECT_URL",
        "ADE_OIDC_SCOPES",
        "ADE_SERVER_PUBLIC_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    reload_settings()


@pytest.mark.asyncio()
async def test_prepare_sso_login_allows_same_origin_absolute_next(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Absolute next targets matching server_public_url should be normalised."""

    monkeypatch.setenv("ADE_OIDC_CLIENT_ID", "demo-client")
    monkeypatch.setenv("ADE_OIDC_CLIENT_SECRET", "demo-secret")
    monkeypatch.setenv("ADE_OIDC_ISSUER", "https://issuer.example.com")
    monkeypatch.setenv("ADE_OIDC_REDIRECT_URL", "https://app.example.com/auth/sso/callback")
    monkeypatch.setenv("ADE_OIDC_SCOPES", '["openid","email"]')
    monkeypatch.setenv("ADE_SERVER_PUBLIC_URL", "https://app.example.com")
    settings = reload_settings()

    metadata = OIDCProviderMetadata(
        authorization_endpoint="https://issuer.example.com/authorize",
        token_endpoint="https://issuer.example.com/token",
        jwks_uri="https://issuer.example.com/jwks",
    )

    async def _fake_metadata(self: AuthService) -> OIDCProviderMetadata:
        return metadata

    monkeypatch.setattr(AuthService, "_get_oidc_metadata", _fake_metadata)

    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        service = AuthService(session=session, settings=settings)
        challenge = await service.prepare_sso_login(
            return_to="https://app.example.com/dashboard?tab=overview"
        )
        state = service.decode_sso_state(challenge.state_token)
        assert state.return_to == "/dashboard?tab=overview"
        parsed = urlparse(challenge.redirect_url)
        params = dict(parse_qsl(parsed.query))
        assert params.get("nonce") == state.nonce

    for key in (
        "ADE_OIDC_CLIENT_ID",
        "ADE_OIDC_CLIENT_SECRET",
        "ADE_OIDC_ISSUER",
        "ADE_OIDC_REDIRECT_URL",
        "ADE_OIDC_SCOPES",
        "ADE_SERVER_PUBLIC_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    reload_settings()


@pytest.mark.asyncio()
async def test_resolve_sso_user_provisions_and_links_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """New SSO users should be provisioned and linked to their identity."""

    settings = reload_settings()

    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        await sync_permission_registry(session=session)
        service = AuthService(session=session, settings=settings)
        user = await service._resolve_sso_user(
            provider="https://issuer.example.com",
            subject="sub-abc",
            email="person@example.com",
        )
        assert user.email == "person@example.com"
        identity = await service._users.get_identity("https://issuer.example.com", "sub-abc")
        assert identity is not None
        assert identity.user_id == user.id


@pytest.mark.asyncio()
async def test_resolve_sso_user_respects_auto_provision_toggle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto-provisioning toggle should block new users when disabled."""

    monkeypatch.setenv("ADE_AUTH_SSO_AUTO_PROVISION", "false")
    settings = reload_settings()

    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        await sync_permission_registry(session=session)
        service = AuthService(session=session, settings=settings)
        with pytest.raises(HTTPException) as exc:
            await service._resolve_sso_user(
                provider="https://issuer.example.com",
                subject="sub-new",
                email="new-user@example.com",
            )
        assert exc.value.status_code == 403
        assert "not invited" in str(exc.value.detail).lower()

    monkeypatch.delenv("ADE_AUTH_SSO_AUTO_PROVISION", raising=False)
    reload_settings()


@pytest.mark.asyncio()
async def test_complete_sso_login_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Completing the SSO flow should provision and link the identity."""

    for key, value in {
        "ADE_OIDC_CLIENT_ID": "demo-client",
        "ADE_OIDC_CLIENT_SECRET": "demo-secret",
        "ADE_OIDC_ISSUER": "https://issuer.example.com",
        "ADE_OIDC_REDIRECT_URL": "https://app.example.com/auth/sso/callback",
        "ADE_OIDC_SCOPES": '["openid","email","profile"]',
        "ADE_SERVER_PUBLIC_URL": "https://app.example.com",
    }.items():
        monkeypatch.setenv(key, value)

    settings = reload_settings()

    metadata = OIDCProviderMetadata(
        authorization_endpoint="https://issuer.example.com/authorize",
        token_endpoint="https://issuer.example.com/token",
        jwks_uri="https://issuer.example.com/jwks",
    )

    async def fake_metadata(self: AuthService) -> OIDCProviderMetadata:
        return metadata

    exchange_calls = 0

    async def fake_exchange(
        self: AuthService, *, code: str, code_verifier: str
    ) -> dict[str, str]:
        nonlocal exchange_calls
        exchange_calls += 1
        assert code == "auth-code"
        assert code_verifier
        return {
            "id_token": "id-token",
            "access_token": "access-token",
            "token_type": "Bearer",
        }

    verify_tokens: list[str] = []

    async def fake_verify(
        self: AuthService,
        *,
        token: str,
        jwks_uri: str,
        audience: str | None,
        issuer: str,
        nonce: str | None = None,
    ) -> dict[str, str]:
        verify_tokens.append(token)
        assert jwks_uri == metadata.jwks_uri
        assert audience == settings.oidc_client_id
        assert issuer == settings.oidc_issuer
        return {"sub": "subject-123", "email": "person@example.com", "nonce": nonce or ""}

    monkeypatch.setattr(AuthService, "_get_oidc_metadata", fake_metadata)
    monkeypatch.setattr(AuthService, "_exchange_authorization_code", fake_exchange)
    monkeypatch.setattr(AuthService, "_verify_jwt_via_jwks", fake_verify)

    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        await sync_permission_registry(session=session)
        service = AuthService(session=session, settings=settings)
        challenge = await service.prepare_sso_login(return_to="/documents")
        redirect_params = dict(parse_qsl(urlparse(challenge.redirect_url).query))
        state_param = redirect_params.get("state")
        assert state_param is not None

        result = await service.complete_sso_login(
            code="auth-code",
            state=state_param,
            state_token=challenge.state_token,
        )

        assert result.return_to == "/documents"
        assert result.user.email == "person@example.com"
        identity = await service._users.get_identity(settings.oidc_issuer or "", "subject-123")
        assert identity is not None
        assert identity.user_id == result.user.id
        assert exchange_calls == 1
        assert "id-token" in verify_tokens

    for key in (
        "ADE_OIDC_CLIENT_ID",
        "ADE_OIDC_CLIENT_SECRET",
        "ADE_OIDC_ISSUER",
        "ADE_OIDC_REDIRECT_URL",
        "ADE_OIDC_SCOPES",
        "ADE_SERVER_PUBLIC_URL",
    ):
        monkeypatch.delenv(key, raising=False)

    reload_settings()
