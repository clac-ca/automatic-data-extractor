"""Authentication workflow tests."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

import httpx

from backend.app import config
from backend.app.auth.passwords import hash_password, verify_password
from backend.app.auth.sessions import hash_session_token
from backend.app.db import get_sessionmaker
from backend.app.models import User, UserRole, UserSession


def _all_sessions() -> list[UserSession]:
    session_factory = get_sessionmaker()
    with session_factory() as db:
        return list(db.query(UserSession).order_by(UserSession.issued_at).all())


def test_password_hashing_roundtrip() -> None:
    password = "s3cret!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("other", hashed)


def test_basic_login_issues_session_cookie(app_client) -> None:
    client, _, _ = app_client
    response = client.post("/auth/login")
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "admin@example.com"
    assert body["session"] is not None
    cookie = client.cookies.get(config.get_settings().session_cookie_name)
    assert cookie is not None
    assert hash_session_token(cookie)


def test_login_failure_records_event(app_client) -> None:
    client, _, _ = app_client
    response = client.post("/auth/login", auth=("unknown@example.com", "nope"))
    assert response.status_code == 401
    events = client.get(
        "/events",
        params={"entity_type": "user", "entity_id": "unknown@example.com"},
    ).json()
    assert any(item["event_type"] == "user.login.failed" for item in events["items"])


def test_session_refresh_extends_expiry(app_client) -> None:
    client, _, _ = app_client
    assert client.post("/auth/login").status_code == 200
    session = _all_sessions()[0]
    original_expiry = datetime.fromisoformat(session.expires_at)
    response = client.get("/auth/session")
    assert response.status_code == 200
    refreshed = _all_sessions()[0]
    refreshed_expiry = datetime.fromisoformat(refreshed.expires_at)
    assert refreshed_expiry > original_expiry


def test_session_endpoint_rejects_expired_cookie(app_client) -> None:
    client, _, _ = app_client
    assert client.post("/auth/login").status_code == 200
    session_factory = get_sessionmaker()
    with session_factory() as db:
        session = db.query(UserSession).first()
        session.expires_at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        db.commit()
    response = client.get("/auth/session")
    assert response.status_code == 401


def test_protected_routes_require_authentication(app_client_factory, tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "auth.sqlite"
    documents_dir = tmp_path / "docs"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("ADE_AUTH_MODES", "basic,session")
    monkeypatch.setenv("ADE_SESSION_COOKIE_SECURE", "0")
    with app_client_factory(database_url, documents_dir) as client:
        client.auth = None
        response = client.get("/documents")
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers
        health = client.get("/health")
        assert health.status_code == 200


def _encode_hs256_token(secret: bytes, issuer: str, audience: str, nonce: str) -> str:
    header = {"alg": "HS256", "typ": "JWT", "kid": "test-key"}
    now = int(time.time())
    payload = {
        "iss": issuer,
        "sub": "sso-user-1",
        "aud": audience,
        "nonce": nonce,
        "email": "sso@example.com",
        "iat": now,
        "exp": now + 3600,
    }

    def _b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

    signing_input = ".".join(
        [
            _b64(json.dumps(header, separators=(",", ":"), sort_keys=True).encode()),
            _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()),
        ]
    )
    signature = hmac.new(secret, signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64(signature)}"


def test_sso_callback_issues_session(app_client_factory, tmp_path, monkeypatch) -> None:
    issuer = "https://sso.example.com"
    db_path = tmp_path / "sso.sqlite"
    documents_dir = tmp_path / "docs"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("ADE_AUTH_MODES", "basic,session,sso")
    monkeypatch.setenv("ADE_SESSION_COOKIE_SECURE", "0")
    monkeypatch.setenv("ADE_SSO_CLIENT_ID", "client-123")
    monkeypatch.setenv("ADE_SSO_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("ADE_SSO_ISSUER", issuer)
    monkeypatch.setenv("ADE_SSO_REDIRECT_URL", "https://ade.internal/auth/sso/callback")

    discovery_url = f"{issuer}/.well-known/openid-configuration"
    token_endpoint = f"{issuer}/token"
    jwks_url = f"{issuer}/jwks"

    secret = b"client-secret"
    jwks = {
        "keys": [
            {
                "kty": "oct",
                "use": "sig",
                "alg": "HS256",
                "kid": "test-key",
                "k": base64.urlsafe_b64encode(secret).decode("ascii").rstrip("="),
            }
        ]
    }

    with app_client_factory(database_url, documents_dir) as client:
        session_factory = get_sessionmaker()
        with session_factory() as db:
            user = User(
                email="sso@example.com",
                password_hash=None,
                role=UserRole.VIEWER,
                is_active=True,
                sso_provider=issuer,
                sso_subject="sso-user-1",
            )
            db.add(user)
            db.commit()

        state_holder: dict[str, str] = {}

        def fake_get(url: str, *args, **kwargs) -> httpx.Response:
            if url == discovery_url:
                return httpx.Response(
                    200,
                    json={
                        "issuer": issuer,
                        "authorization_endpoint": f"{issuer}/authorize",
                        "token_endpoint": token_endpoint,
                        "jwks_uri": jwks_url,
                    },
                )
            if url == jwks_url:
                return httpx.Response(200, json=jwks)
            raise AssertionError(f"Unexpected GET {url}")

        def fake_post(url: str, *args, **kwargs) -> httpx.Response:
            assert url == token_endpoint
            nonce = state_holder["nonce"]
            token = _encode_hs256_token(secret, issuer, "client-123", nonce)
            return httpx.Response(200, json={"id_token": token})

        monkeypatch.setattr(httpx, "get", fake_get)
        monkeypatch.setattr(httpx, "post", fake_post)

        client.auth = None
        login_redirect = client.get("/auth/sso/login")
        assert login_redirect.status_code == 307
        location = login_redirect.headers["Location"]
        parsed = urllib.parse.urlparse(location)
        query = urllib.parse.parse_qs(parsed.query)
        state_holder["nonce"] = query["nonce"][0]
        state = query["state"][0]
        callback = client.get("/auth/sso/callback", params={"code": "abc", "state": state})
        assert callback.status_code == 200
        body = callback.json()
        assert body["user"]["email"] == "sso@example.com"
        cookie = client.cookies.get(config.get_settings().session_cookie_name)
        assert cookie is not None


def test_manage_cli_flows(tmp_path, monkeypatch) -> None:
    from backend.app.auth import manage

    db_path = tmp_path / "manage.sqlite"
    documents_dir = tmp_path / "docs"
    monkeypatch.setenv("ADE_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("ADE_DOCUMENTS_DIR", str(documents_dir))
    monkeypatch.setenv("ADE_AUTH_MODES", "basic")
    monkeypatch.setenv("ADE_SESSION_COOKIE_SECURE", "0")
    try:
        assert (
            manage.main([
                "create-user",
                "cli@example.com",
                "--password",
                "cli-pass",
                "--role",
                "viewer",
            ])
            == 0
        )
        assert manage.main(["promote", "cli@example.com"]) == 0
        assert manage.main(["reset-password", "cli@example.com", "--password", "new-pass"]) == 0
        assert manage.main(["deactivate", "cli@example.com"]) == 0

        session_factory = get_sessionmaker()
        with session_factory() as db:
            user = db.query(User).filter(User.email == "cli@example.com").one()
            assert user.role == UserRole.ADMIN
            assert not user.is_active
            assert verify_password("new-pass", user.password_hash)

        assert manage.main(["list-users"]) == 0
    finally:
        config.reset_settings_cache()
