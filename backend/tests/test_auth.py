from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app import config
from backend.app.auth.email import EmailValidationError, canonicalize_email, normalize_email
from backend.app.db import get_sessionmaker
from backend.app.models import APIKey, Event, User, UserRole
from backend.app.services import auth as auth_service
from backend.tests.conftest import DEFAULT_USER_EMAIL, DEFAULT_USER_PASSWORD


def test_hash_password_roundtrip() -> None:
    hashed = auth_service.hash_password("super-secret")
    assert auth_service.verify_password("super-secret", hashed)
    assert not auth_service.verify_password("not-it", hashed)


def test_hash_password_rejects_blank() -> None:
    with pytest.raises(ValueError):
        auth_service.hash_password("   ")


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/auth/token",
        data={"username": email, "password": password},
    )
    return response


def test_canonicalize_email_handles_unicode_domain() -> None:
    canonical = canonicalize_email(" Admin@Exämple.com ")
    assert canonical == "admin@xn--exmple-cua.com"


def test_normalize_email_preserves_display_formatting() -> None:
    result = normalize_email(" Admin@Exämple.com ")
    assert result.original == "Admin@Exämple.com"
    assert result.canonical == "admin@xn--exmple-cua.com"


def test_canonicalize_email_casefolds_local_part() -> None:
    canonical = canonicalize_email("MiXeD.Case@Example.com")
    assert canonical == "mixed.case@example.com"


def test_canonicalize_email_preserves_provider_tags() -> None:
    tagged = canonicalize_email("user.name+tag@Example.com")
    assert tagged == "user.name+tag@example.com"


def test_canonicalize_email_normalises_unicode_local_parts() -> None:
    accented = canonicalize_email("Jörg@bücher.example")
    decomposed = canonicalize_email("jörg@bücher.example")
    assert accented == decomposed
    assert accented == "jörg@xn--bcher-kva.example"


def test_canonicalize_email_rejects_invalid_addresses() -> None:
    with pytest.raises(EmailValidationError):
        canonicalize_email("not-an-email")


def test_login_issues_bearer_token(app_client) -> None:
    client, _, _ = app_client
    response = _login(client, DEFAULT_USER_EMAIL, DEFAULT_USER_PASSWORD)
    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert isinstance(payload["access_token"], str)


def test_login_rejects_invalid_credentials(app_client) -> None:
    client, _, _ = app_client
    response = _login(client, DEFAULT_USER_EMAIL, "wrong-password")
    assert response.status_code == 401


def test_login_rejects_malformed_email(app_client) -> None:
    client, _, _ = app_client
    response = _login(client, "invalid", DEFAULT_USER_PASSWORD)
    assert response.status_code == 401


def test_login_accepts_case_insensitive_email(app_client) -> None:
    client, _, _ = app_client
    response = _login(client, DEFAULT_USER_EMAIL.upper(), DEFAULT_USER_PASSWORD)
    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"


def test_me_endpoint_returns_profile(app_client) -> None:
    client, _, _ = app_client
    response = client.get("/auth/me")
    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == DEFAULT_USER_EMAIL
    assert payload["role"] == UserRole.ADMIN.value


def test_protected_endpoint_requires_token(app_client_factory, tmp_path) -> None:
    data_dir = tmp_path / "data"
    with app_client_factory(None, None, data_dir=data_dir) as client:
        client.headers.pop("Authorization", None)
        unauthenticated = client.get("/documents")
        assert unauthenticated.status_code == 401

        login = _login(client, DEFAULT_USER_EMAIL, DEFAULT_USER_PASSWORD)
        token = login.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        authorised = client.get("/documents")
        assert authorised.status_code == 200


def test_decode_access_token_with_expired_token_raises(monkeypatch, app_client) -> None:
    client, _, _ = app_client
    del client
    monkeypatch.setenv("ADE_JWT_SECRET_KEY", "expire-test-secret")
    config.reset_settings_cache()
    settings = config.get_settings()
    session_factory = get_sessionmaker()
    with session_factory() as db:
        user = (
            db.query(User)
            .filter(User.email_canonical == canonicalize_email(DEFAULT_USER_EMAIL))
            .one()
        )
        expired = auth_service.create_access_token(
            user,
            settings,
            expires_delta=timedelta(seconds=-5),
        )
    with pytest.raises(HTTPException):
        auth_service.decode_access_token(expired, settings)
    config.reset_settings_cache()


def test_require_admin_blocks_non_admin(app_client) -> None:
    _, _, _ = app_client
    session_factory = get_sessionmaker()
    with session_factory() as db:
        viewer = User(
            email="viewer@example.com",
            password_hash=auth_service.hash_password("viewerpass"),
            role=UserRole.VIEWER,
            is_active=True,
        )
        db.add(viewer)
        db.commit()
        db.refresh(viewer)

        token = auth_service.create_access_token(viewer, config.get_settings())

    test_app = FastAPI()

    @test_app.get("/admin")
    async def admin_endpoint(
        _user: User = Depends(auth_service.require_admin),
    ) -> dict[str, str]:
        return {"status": "ok"}

    dependency_app = TestClient(test_app)
    dependency_app.headers.update({"Authorization": f"Bearer {token}"})
    response = dependency_app.get("/admin")
    assert response.status_code == 403


def test_validate_settings_requires_secret(monkeypatch) -> None:
    monkeypatch.setenv("ADE_AUTH_DISABLED", "0")
    monkeypatch.delenv("ADE_JWT_SECRET_KEY", raising=False)
    config.reset_settings_cache()
    settings = config.get_settings()
    with pytest.raises(RuntimeError):
        auth_service.validate_settings(settings)
    config.reset_settings_cache()


def test_api_key_allows_access(app_client) -> None:
    client, _, _ = app_client
    session_factory = get_sessionmaker()
    with session_factory() as db:
        user = (
            db.query(User)
            .filter(User.email_canonical == canonicalize_email(DEFAULT_USER_EMAIL))
            .one()
        )
        raw_key, _ = auth_service.issue_api_key(db, user)
        db.commit()

    client.headers.pop("Authorization", None)
    client.headers["X-API-Key"] = raw_key
    response = client.get("/auth/me")
    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == DEFAULT_USER_EMAIL


def test_api_key_last_seen_throttled(monkeypatch, app_client_factory) -> None:
    monkeypatch.setenv("ADE_API_KEY_TOUCH_INTERVAL_SECONDS", "120")
    config.reset_settings_cache()

    with app_client_factory(None, None) as client:
        client.headers.pop("Authorization", None)
        session_factory = get_sessionmaker()
        with session_factory() as db:
            user = (
                db.query(User)
                .filter(User.email_canonical == canonicalize_email(DEFAULT_USER_EMAIL))
                .one()
            )
            raw_key, api_key = auth_service.issue_api_key(db, user)
            key_id = api_key.api_key_id
            db.commit()

        client.headers["X-API-Key"] = raw_key

        first = datetime(2025, 1, 1, tzinfo=timezone.utc)
        second = first + timedelta(seconds=60)
        third = first + timedelta(seconds=240)

        monkeypatch.setattr(auth_service, "_now", lambda: first)
        assert client.get("/auth/me").status_code == 200
        with session_factory() as db:
            stored = db.get(APIKey, key_id)
            first_seen = stored.last_seen_at

        monkeypatch.setattr(auth_service, "_now", lambda: second)
        assert client.get("/auth/me").status_code == 200
        with session_factory() as db:
            stored = db.get(APIKey, key_id)
            assert stored.last_seen_at == first_seen

        monkeypatch.setattr(auth_service, "_now", lambda: third)
        assert client.get("/auth/me").status_code == 200
        with session_factory() as db:
            stored = db.get(APIKey, key_id)
            assert stored.last_seen_at != first_seen


def test_sso_login_and_callback_creates_user(monkeypatch, app_client_factory) -> None:
    monkeypatch.setenv("ADE_SSO_CLIENT_ID", "demo-client")
    monkeypatch.setenv("ADE_SSO_CLIENT_SECRET", "demo-secret")
    monkeypatch.setenv("ADE_SSO_ISSUER", "https://issuer.example.com")
    monkeypatch.setenv("ADE_SSO_REDIRECT_URL", "https://ade.example.com/auth/sso/callback")
    monkeypatch.setenv("ADE_SSO_SCOPE", "openid email profile")
    monkeypatch.setenv("ADE_SSO_RESOURCE_AUDIENCE", "https://ade.example.com/api")
    config.reset_settings_cache()

    metadata = auth_service.OIDCProviderMetadata(
        authorization_endpoint="https://issuer.example.com/authorize",
        token_endpoint="https://issuer.example.com/token",
        jwks_uri="https://issuer.example.com/jwks",
    )

    async def fake_metadata(_settings: config.Settings) -> auth_service.OIDCProviderMetadata:
        return metadata

    async def fake_exchange(
        _settings: config.Settings, *, code: str, code_verifier: str
    ) -> dict[str, str]:
        assert code == "auth-code"
        assert code_verifier
        return {
            "id_token": "id.jwt",
            "access_token": "access.jwt",
            "token_type": "Bearer",
        }

    def fake_verify(
        token: str,
        jwks_uri: str,
        *,
        audience: str | None,
        issuer: str,
        nonce: str | None = None,
    ) -> dict[str, str]:
        assert jwks_uri == metadata.jwks_uri
        assert issuer == "https://issuer.example.com"
        if token == "id.jwt":
            payload: dict[str, str] = {
                "sub": "user-123",
                "email": "sso-user@example.com",
                "email_verified": True,
            }
            if audience:
                payload["aud"] = audience
            if nonce is not None:
                payload["nonce"] = nonce
            return payload
        if token == "access.jwt":
            return {"aud": audience or ""}
        raise AssertionError("Unexpected token")

    monkeypatch.setattr(auth_service, "get_oidc_metadata", fake_metadata)
    monkeypatch.setattr(auth_service, "exchange_authorization_code", fake_exchange)
    monkeypatch.setattr(auth_service, "verify_jwt_via_jwks", fake_verify)

    with app_client_factory(None, None) as client:
        response = client.get("/auth/sso/login", follow_redirects=False)
        assert response.status_code in (302, 307)
        location = response.headers["location"]
        params = parse_qs(urlparse(location).query)
        state = params["state"][0]
        assert auth_service.SSO_STATE_COOKIE in client.cookies

        callback = client.get(
            "/auth/sso/callback",
            params={"code": "auth-code", "state": state},
        )
        assert callback.status_code == 200
        payload = callback.json()
        assert "access_token" in payload

        token = payload["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        profile = client.get("/auth/me")
        assert profile.status_code == 200
        assert profile.json()["email"] == "sso-user@example.com"

        session_factory = get_sessionmaker()
    with session_factory() as db:
        user = (
            db.query(User)
            .filter(User.email_canonical == canonicalize_email("sso-user@example.com"))
            .one()
        )
        assert user.sso_provider == "https://issuer.example.com"
        assert user.sso_subject == "user-123"

        events = (
            db.query(Event)
            .filter(Event.event_type == "auth.sso.login.succeeded")
            .all()
        )
        assert len(events) == 1
        event = events[0]
        assert event.entity_id == user.user_id
        assert event.payload["provider"] == "https://issuer.example.com"
        assert event.actor_id == user.user_id
        assert event.actor_label == user.email


def test_list_api_keys_returns_metadata(app_client) -> None:
    client, _, _ = app_client
    create = client.post(
        "/auth/api-keys",
        json={"email": DEFAULT_USER_EMAIL},
    )
    assert create.status_code == 200, create.text
    issued = create.json()
    raw_key = issued["api_key"]
    prefix, _secret = raw_key.split(".", 1)

    admin_token = client.headers["Authorization"]
    client.headers.pop("Authorization", None)
    client.headers["X-API-Key"] = raw_key
    assert client.get("/auth/me").status_code == 200
    client.headers.pop("X-API-Key", None)
    client.headers["Authorization"] = admin_token

    response = client.get("/auth/api-keys")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    record = payload[0]
    assert record["token_prefix"] == prefix
    assert record["user_email"] == DEFAULT_USER_EMAIL
    assert record["last_seen_at"] is not None

    session_factory = get_sessionmaker()
    with session_factory() as db:
        admin = (
            db.query(User)
            .filter(User.email_canonical == canonicalize_email(DEFAULT_USER_EMAIL))
            .one()
        )
        events = (
            db.query(Event)
            .filter(Event.event_type == "auth.api_key.created")
            .all()
        )
        assert len(events) == 1
        event = events[0]
        assert event.entity_id == record["api_key_id"]
        assert event.payload["token_prefix"] == prefix
        assert event.payload["user_email"] == DEFAULT_USER_EMAIL
        assert event.actor_id == admin.user_id


def test_revoke_api_key_revokes_and_records_event(app_client) -> None:
    client, _, _ = app_client
    create = client.post(
        "/auth/api-keys",
        json={"email": DEFAULT_USER_EMAIL},
    )
    assert create.status_code == 200, create.text
    raw_key = create.json()["api_key"]

    listing = client.get("/auth/api-keys")
    assert listing.status_code == 200
    key_id = listing.json()[0]["api_key_id"]

    revoke = client.delete(f"/auth/api-keys/{key_id}")
    assert revoke.status_code == 204

    admin_token = client.headers["Authorization"]
    client.headers.pop("Authorization", None)
    client.headers["X-API-Key"] = raw_key
    denied = client.get("/auth/me")
    assert denied.status_code == 401
    client.headers.pop("X-API-Key", None)
    client.headers["Authorization"] = admin_token

    remaining = client.get("/auth/api-keys")
    assert remaining.status_code == 200
    assert remaining.json() == []

    session_factory = get_sessionmaker()
    with session_factory() as db:
        admin = (
            db.query(User)
            .filter(User.email_canonical == canonicalize_email(DEFAULT_USER_EMAIL))
            .one()
        )
        events = (
            db.query(Event)
            .filter(Event.event_type == "auth.api_key.revoked")
            .all()
        )
        assert len(events) == 1
        event = events[0]
        assert event.entity_id == key_id
        assert event.payload["user_email"] == DEFAULT_USER_EMAIL
        assert event.actor_id == admin.user_id


def test_sso_login_failure_records_event(monkeypatch, app_client_factory) -> None:
    monkeypatch.setenv("ADE_SSO_CLIENT_ID", "demo-client")
    monkeypatch.setenv("ADE_SSO_CLIENT_SECRET", "demo-secret")
    monkeypatch.setenv("ADE_SSO_ISSUER", "https://issuer.example.com")
    monkeypatch.setenv("ADE_SSO_REDIRECT_URL", "https://ade.example.com/auth/sso/callback")
    monkeypatch.setenv("ADE_SSO_SCOPE", "openid email profile")
    config.reset_settings_cache()

    metadata = auth_service.OIDCProviderMetadata(
        authorization_endpoint="https://issuer.example.com/authorize",
        token_endpoint="https://issuer.example.com/token",
        jwks_uri="https://issuer.example.com/jwks",
    )

    async def fake_metadata(_settings: config.Settings) -> auth_service.OIDCProviderMetadata:
        return metadata

    monkeypatch.setattr(auth_service, "get_oidc_metadata", fake_metadata)

    with app_client_factory(None, None) as client:
        login = client.get("/auth/sso/login", follow_redirects=False)
        assert login.status_code in (302, 307)
        assert auth_service.SSO_STATE_COOKIE in client.cookies

        callback = client.get(
            "/auth/sso/callback",
            params={"code": "auth-code", "state": "wrong-state"},
        )
        assert callback.status_code == 400

        session_factory = get_sessionmaker()
        with session_factory() as db:
            events = (
                db.query(Event)
                .filter(Event.event_type == "auth.sso.login.failed")
                .all()
            )
            assert len(events) == 1
            event = events[0]
            assert event.payload["provider"] == "https://issuer.example.com"
            assert event.payload["status_code"] == 400
            assert "State mismatch" in event.payload["detail"]
