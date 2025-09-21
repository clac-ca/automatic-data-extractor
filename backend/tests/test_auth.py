"""Authentication workflow tests."""

from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib
import hmac
import json
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPBasicCredentials
from sqlalchemy.orm import Session

from backend.app import cli as ade_cli
from backend.app import config
import backend.app.services.auth as auth_service
from backend.app.db import get_sessionmaker
from backend.app.db_migrations import ensure_schema
from backend.app.models import ApiKey, Event, User, UserRole, UserSession


def _all_sessions() -> list[UserSession]:
    session_factory = get_sessionmaker()
    with session_factory() as db:
        return list(db.query(UserSession).order_by(UserSession.issued_at).all())


def _insert_api_key(user: User, token: str, *, name: str = "automation") -> None:
    session_factory = get_sessionmaker()
    with session_factory() as db:
        api_key = ApiKey(
            user_id=user.user_id,
            name=name,
            token_prefix=token[:12],
            token_hash=auth_service.hash_api_key_token(token),
        )
        db.add(api_key)
        db.commit()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


@contextmanager
def _configured_settings(monkeypatch, tmp_path, **overrides):
    from backend.app import db as db_module

    data_dir = tmp_path / "data"
    documents_dir = data_dir / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    defaults = {
        "ADE_DATA_DIR": str(data_dir),
        "ADE_AUTH_MODES": "basic",
        "ADE_SESSION_COOKIE_SECURE": "0",
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        monkeypatch.setenv(key, str(value))

    config.reset_settings_cache()
    db_module.reset_database_state()
    import backend.app.models  # noqa: F401

    ensure_schema()
    try:
        yield config.get_settings(), get_sessionmaker()
    finally:
        config.reset_settings_cache()
        db_module.reset_database_state()


_RSA_MODULUS_HEX = (
    "00c00df431856af1f7427bcd0ff35abb718d818e1318109a3a6905bab953a7cf7d840192596eb0e1b7437f6bc3c5e2870db70899efcd26008a38704bff0446bd"
    "71d72474e21a399695888e992b91dd54411dea36d57820edfda8fb0720dab985407afa6763cb6da623a33f40fdc0c788103db695649b8e89e23a448febdb4997"
    "3272267b8613c383c2e4701e5b2bdfc0d99782b959fa081bccd0d20b56887995aa906e56b066318cad62e0d4ebff956d2e977144c3034cf34791fcdc0250c228"
    "51862ce026871f35e4e48fecda37f4d36e76594d841b1f6dd9d5258c68faa65feb301448c789969d02a33012fc9e76fadafdcbbb6d4b686484b46895c0aeabee"
    "9f"
)
_RSA_PRIVATE_EXPONENT_HEX = (
    "56344d36072d443398776a496d117e4e4f566617a2f71ccaf805f6d4a5bc8e9147b5cee36ea05d883d774dbf3facd8b2eac3a518f28bcab53ff503df91235178"
    "6e39b26f249751c487d97dde052883df8096770b6552de903b8f859915242db00e2324523266e2aa5f658e7df7d077fdd63d849bf688c9d22e1645457815f593"
    "8b37a71a36b3010720cec089d0e28d6ed3d4cf11ed29c196196be0f5ff046233792aba23ac0493f63fcb079ba9c1420d0e6740c877b96dfa9ccebaafeb58d6fd"
    "87459f5472391ac5369ee173de6218fcc51f7b82cad41ea05d9f5350d1de9b26e05b02f8f0482eef1bd41933439b5ba23834237661dc7dcda47ebdeb48c39b99"
)


def _rsa_components() -> tuple[int, int, int, int]:
    modulus = int(_RSA_MODULUS_HEX, 16)
    private_exponent = int(_RSA_PRIVATE_EXPONENT_HEX, 16)
    public_exponent = 65537
    key_size = (modulus.bit_length() + 7) // 8
    return modulus, public_exponent, private_exponent, key_size


def _encode_rs256_token(
    issuer: str,
    audience: str,
    *,
    kid: str = "rs256-key",
    overrides: dict[str, object] | None = None,
) -> str:
    header = {"alg": "RS256", "typ": "JWT", "kid": kid}
    now = int(time.time())
    payload: dict[str, object] = {
        "iss": issuer,
        "sub": "sso-user-1",
        "aud": audience,
        "email": "sso@example.com",
        "iat": now,
        "exp": now + 3600,
    }
    if overrides:
        payload.update(overrides)

    signing_input = ".".join(
        [
            _b64url(json.dumps(header, separators=(",", ":"), sort_keys=True).encode()),
            _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()),
        ]
    )
    modulus, public_exponent, private_exponent, key_size = _rsa_components()
    digest = hashlib.sha256(signing_input.encode("ascii")).digest()
    digest_info = bytes.fromhex("3031300d060960864801650304020105000420") + digest
    padding_length = key_size - len(digest_info) - 3
    assert padding_length >= 8
    encoded_message = b"\x00\x01" + (b"\xff" * padding_length) + b"\x00" + digest_info
    signature_int = pow(int.from_bytes(encoded_message, "big"), private_exponent, modulus)
    signature = signature_int.to_bytes(key_size, "big")
    return f"{signing_input}.{_b64url(signature)}"


def _rs256_jwk(kid: str) -> dict[str, str]:
    modulus, public_exponent, _, key_size = _rsa_components()
    modulus_bytes = modulus.to_bytes(key_size, "big")
    exponent_bytes = public_exponent.to_bytes((public_exponent.bit_length() + 7) // 8, "big")
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": _b64url(modulus_bytes),
        "e": _b64url(exponent_bytes),
    }


def test_password_hashing_roundtrip() -> None:
    password = "s3cret!"
    hashed = auth_service.hash_password(password)
    assert hashed != password
    assert auth_service.verify_password(password, hashed)
    assert not auth_service.verify_password("other", hashed)


def _make_request_stub() -> SimpleNamespace:
    return SimpleNamespace(
        state=SimpleNamespace(),
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"user-agent": "pytest"},
        cookies={},
    )


def _resolve_identity(
    request: SimpleNamespace,
    *,
    settings: config.Settings,
    db: Session,
    session_token: str | None = None,
    header_token: str | None = None,
    bearer_token: str | None = None,
) -> auth_service.AuthenticatedIdentity:
    if session_token is not None:
        session_result = auth_service._resolve_session_identity_with_db(
            db,
            request=request,
            token=session_token,
            settings=settings,
        )
    else:
        session_result = auth_service.CredentialResolution()

    token: str | None = None
    if bearer_token is not None:
        token = bearer_token
    elif header_token is not None:
        token = header_token

    if token is not None:
        api_key_result = auth_service._resolve_api_key_identity_with_db(
            db,
            token=token,
            settings=settings,
        )
    else:
        api_key_result = auth_service.CredentialResolution()

    return auth_service.get_authenticated_identity(
        settings=settings,
        session_result=session_result,
        api_key_result=api_key_result,
    )


def test_cli_main_auth_group_invokes_commands(monkeypatch, tmp_path, capsys) -> None:
    with _configured_settings(monkeypatch, tmp_path) as (_, session_factory):
        operator = "ops@example.com"
        assert (
            ade_cli.main(
                [
                    "auth",
                    "create-user",
                    "cli@example.com",
                    "--password",
                    "cli-pass",
                    "--operator-email",
                    operator,
                ]
            )
            == 0
        )

        capsys.readouterr()  # discard creation log lines

        assert ade_cli.main(["auth", "list-users"]) == 0
        listed = capsys.readouterr().out
        assert "cli@example.com" in listed

        with session_factory() as db:
            user = db.query(User).filter(User.email == "cli@example.com").one()
            assert user.is_active
            assert user.role == UserRole.VIEWER
            assert auth_service.verify_password("cli-pass", user.password_hash)


def test_cli_api_key_commands_manage_lifecycle(
    monkeypatch, tmp_path, capsys
) -> None:
    with _configured_settings(monkeypatch, tmp_path) as (_, session_factory):
        operator_email = "admin@example.com"
        service_email = "service@example.com"

        assert (
            ade_cli.main(
                [
                    "auth",
                    "create-user",
                    operator_email,
                    "--password",
                    "operator-pass",
                    "--role",
                    UserRole.ADMIN.value,
                ]
            )
            == 0
        )
        capsys.readouterr()

        assert (
            ade_cli.main(
                [
                    "auth",
                    "create-user",
                    service_email,
                    "--password",
                    "service-pass",
                    "--operator-email",
                    operator_email,
                ]
            )
            == 0
        )
        capsys.readouterr()

        assert (
            ade_cli.main(
                [
                    "auth",
                    "create-api-key",
                    service_email,
                    "automation",
                    "--operator-email",
                    operator_email,
                ]
            )
            == 0
        )
        creation_output = capsys.readouterr().out.splitlines()
        token_line = next(line for line in creation_output if line.startswith("Token: "))
        token = token_line.split("Token: ", 1)[1].strip()
        assert token

        with session_factory() as db:
            api_key = (
                db.query(ApiKey)
                .join(User, ApiKey.user_id == User.user_id)
                .filter(User.email == service_email)
                .one()
            )
            api_key_id = api_key.api_key_id

        assert ade_cli.main(["auth", "list-api-keys"]) == 0
        list_output = capsys.readouterr().out
        assert api_key_id in list_output
        assert token not in list_output

        with session_factory() as db:
            stored_key = auth_service.get_api_key(db, token)
            assert stored_key is not None
            assert stored_key.api_key_id == api_key_id

        assert (
            ade_cli.main(
                [
                    "auth",
                    "revoke-api-key",
                    api_key_id,
                    "--operator-email",
                    operator_email,
                    "--reason",
                    "rotation",
                ]
            )
            == 0
        )
        revoke_output = capsys.readouterr().out
        assert "Revoked API key" in revoke_output

        with session_factory() as db:
            assert auth_service.get_api_key(db, token) is None

            events = (
                db.query(Event)
                .filter(Event.entity_id == api_key_id)
                .order_by(Event.occurred_at)
                .all()
            )
            event_types = [event.event_type for event in events]
            assert "api-key.created" in event_types
            assert "api-key.revoked" in event_types
            for event in events:
                if event.event_type.startswith("api-key."):
                    assert event.source == "cli"
                    assert event.actor_label == operator_email


def test_get_authenticated_identity_for_session(monkeypatch, tmp_path) -> None:
    with _configured_settings(monkeypatch, tmp_path) as (settings, session_factory):
        with session_factory() as db:
            user = User(
                email="identity@example.com",
                password_hash=auth_service.hash_password("secret"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            session_model, raw_token = auth_service.issue_session(
                db,
                user,
                settings=settings,
            )

            request = _make_request_stub()
            request.cookies[settings.session_cookie_name] = raw_token

            identity = _resolve_identity(
                request,
                settings=settings,
                db=db,
                session_token=raw_token,
            )

            assert identity.user.user_id == user.user_id
            assert identity.session is not None
            assert identity.session.session_id == session_model.session_id
            assert identity.session_id == session_model.session_id
            assert identity.api_key is None
            assert identity.mode == "session"


def test_get_authenticated_identity_for_api_key(monkeypatch, tmp_path) -> None:
    with _configured_settings(monkeypatch, tmp_path) as (settings, session_factory):
        with session_factory() as db:
            user = User(
                email="apikey@example.com",
                password_hash=None,
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            user_id = user.user_id

        token = "identity-api-token"
        _insert_api_key(user, token)

        with session_factory() as db:
            request = _make_request_stub()
            identity = _resolve_identity(
                request,
                settings=settings,
                db=db,
                header_token=token,
            )

        assert identity.user.user_id == user_id
        assert identity.session is None
        assert identity.api_key is not None
        assert identity.api_key.token_prefix == token[:12]
        assert identity.api_key_id == identity.api_key.api_key_id
        assert identity.mode == "api-key"


def test_complete_login_helper_commits_session(monkeypatch, tmp_path) -> None:
    overrides = {
        "ADE_DATABASE_URL": f"sqlite:///{tmp_path / 'complete-login.sqlite'}",
        "ADE_AUTH_MODES": "basic,sso",
        "ADE_SESSION_COOKIE_SECURE": "0",
    }

    with _configured_settings(monkeypatch, tmp_path, **overrides) as (settings, session_factory):
        with session_factory() as db:
            user = User(
                email="helper@example.com",
                password_hash=auth_service.hash_password("secret"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            session_model, raw_token = auth_service.complete_login(
                db,
                settings,
                user,
                mode="basic",
                source="api",
                ip_address="127.0.0.1",
                user_agent="pytest-client",
            )

            user_id = user.user_id
            assert raw_token
            assert session_model.last_seen_ip == "127.0.0.1"
            assert session_model.last_seen_user_agent == "pytest-client"
            assert user.last_login_at is not None

        with session_factory() as db:
            events = (
                db.query(Event)
                .filter(Event.entity_id == user_id, Event.event_type == "user.login.succeeded")
                .order_by(Event.occurred_at)
                .all()
            )
            assert events
            payload = events[-1].payload
            assert payload["mode"] == "basic"
            assert payload["ip"] == "127.0.0.1"
            assert payload["user_agent"] == "pytest-client"
            assert "subject" not in payload

        with session_factory() as db:
            user = db.query(User).filter(User.user_id == user_id).one()
            auth_service.complete_login(
                db,
                settings,
                user,
                mode="sso",
                source="api",
                ip_address=None,
                user_agent=None,
                subject=None,
                include_subject=True,
            )

        with session_factory() as db:
            final_event = (
                db.query(Event)
                .filter(Event.entity_id == user_id, Event.event_type == "user.login.succeeded")
                .order_by(Event.occurred_at.desc())
                .first()
            )
            assert final_event is not None
            assert "subject" in final_event.payload
            assert final_event.payload["subject"] is None


def test_basic_login_issues_session_cookie(app_client) -> None:
    client, _, _ = app_client
    response = client.post("/auth/login/basic")
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "admin@example.com"
    assert body["session"] is not None
    cookie = client.cookies.get(config.get_settings().session_cookie_name)
    assert cookie is not None
    assert auth_service.hash_session_token(cookie)


def test_login_failure_records_event(app_client) -> None:
    client, _, _ = app_client
    response = client.post("/auth/login/basic", auth=("unknown@example.com", "nope"))
    assert response.status_code == 401
    events = client.get(
        "/events",
        params={"entity_type": "user", "entity_id": "unknown@example.com"},
    ).json()
    assert any(item["event_type"] == "user.login.failed" for item in events["items"])


def test_basic_auth_dependency_returns_user(monkeypatch, tmp_path) -> None:
    with _configured_settings(monkeypatch, tmp_path) as (settings, session_factory):
        with session_factory() as db:
            user = User(
                email="basic-user@example.com",
                password_hash=auth_service.hash_password("valid-pass"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(user)
            db.commit()

        with session_factory() as db:
            credentials = HTTPBasicCredentials(
                username="basic-user@example.com",
                password="valid-pass",
            )
            resolved = auth_service.require_basic_auth_user(
                credentials=credentials,
                db=db,
                settings=settings,
            )
            assert resolved.user_id == user.user_id

        with session_factory() as db:
            assert db.query(Event).count() == 0


def test_basic_auth_dependency_records_failure(monkeypatch, tmp_path) -> None:
    with _configured_settings(monkeypatch, tmp_path) as (settings, session_factory):
        with session_factory() as db:
            user = User(
                email="basic-user@example.com",
                password_hash=auth_service.hash_password("valid-pass"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(user)
            db.commit()

        with session_factory() as db:
            credentials = HTTPBasicCredentials(
                username="basic-user@example.com",
                password="wrong-pass",
            )
            with pytest.raises(HTTPException) as exc_info:
                auth_service.require_basic_auth_user(
                    credentials=credentials,
                    db=db,
                    settings=settings,
                )
            assert exc_info.value.status_code == 401

        with session_factory() as db:
            events = (
                db.query(Event)
                .filter(Event.entity_id == "basic-user@example.com")
                .all()
            )
            assert len(events) == 1
            assert events[0].event_type == "user.login.failed"
            assert events[0].payload["reason"] == "invalid-password"


def test_session_refresh_extends_expiry(app_client) -> None:
    client, _, _ = app_client
    assert client.post("/auth/login/basic").status_code == 200
    session = _all_sessions()[-1]
    original_expiry = datetime.fromisoformat(session.expires_at)
    response = client.get("/auth/session")
    assert response.status_code == 200
    refreshed = _all_sessions()[-1]
    refreshed_expiry = datetime.fromisoformat(refreshed.expires_at)
    assert refreshed_expiry > original_expiry


def test_session_endpoint_rejects_expired_cookie(app_client) -> None:
    client, _, _ = app_client
    assert client.post("/auth/login/basic").status_code == 200
    session_factory = get_sessionmaker()
    with session_factory() as db:
        session = db.query(UserSession).order_by(UserSession.issued_at.desc()).first()
        session.expires_at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        db.commit()
    response = client.get("/auth/session")
    assert response.status_code == 403


def test_revoke_session_is_idempotent(app_client) -> None:
    client, _, _ = app_client
    del client
    settings = config.get_settings()
    session_factory = get_sessionmaker()
    with session_factory() as db:
        user = db.query(User).filter(User.email == "admin@example.com").one()
        session_model, _ = auth_service.issue_session(
            db,
            user,
            settings=settings,
            commit=False,
        )
        session_id = session_model.session_id
        auth_service.revoke_session(db, session_model, commit=False)
        first_revoked = session_model.revoked_at
        assert first_revoked is not None
        auth_service.revoke_session(db, session_model, commit=False)
        assert session_model.revoked_at == first_revoked
        db.commit()

    with session_factory() as db:
        persisted = db.get(UserSession, session_id)
        assert persisted.revoked_at == first_revoked


def test_touch_session_updates_metadata_commit_false(app_client) -> None:
    client, _, _ = app_client
    del client
    settings = config.get_settings()
    session_factory = get_sessionmaker()
    with session_factory() as db:
        user = db.query(User).filter(User.email == "admin@example.com").one()
        session_model, _ = auth_service.issue_session(
            db,
            user,
            settings=settings,
            commit=False,
        )
        original_expiry = datetime.fromisoformat(session_model.expires_at)
        agent = "Mozilla/5.0" * 40
        refreshed = auth_service.touch_session(
            db,
            session_model,
            settings=settings,
            ip_address="10.0.0.1",
            user_agent=agent,
            commit=False,
        )
        assert refreshed is session_model
        assert refreshed.last_seen_ip == "10.0.0.1"
        assert refreshed.last_seen_user_agent == agent[:255]
        assert datetime.fromisoformat(refreshed.expires_at) > original_expiry
        db.commit()

    with session_factory() as db:
        reloaded = db.get(UserSession, session_model.session_id)
        assert reloaded.last_seen_ip == "10.0.0.1"
        assert reloaded.last_seen_user_agent == agent[:255]


def test_touch_session_rejects_revoked_and_expired(app_client) -> None:
    client, _, _ = app_client
    del client
    settings = config.get_settings()
    session_factory = get_sessionmaker()
    with session_factory() as db:
        user = db.query(User).filter(User.email == "admin@example.com").one()
        revoked_session, _ = auth_service.issue_session(
            db,
            user,
            settings=settings,
            commit=True,
        )
        expired_session, _ = auth_service.issue_session(
            db,
            user,
            settings=settings,
            commit=True,
        )

    now = datetime.now(timezone.utc)
    with session_factory() as db:
        record = db.get(UserSession, revoked_session.session_id)
        record.revoked_at = now.isoformat()
        db.commit()

    with session_factory() as db:
        record = db.get(UserSession, revoked_session.session_id)
        result = auth_service.touch_session(
            db,
            record,
            settings=settings,
            ip_address="10.0.0.2",
            user_agent="Revoked",
            commit=False,
        )
        assert result is None
        assert record.last_seen_ip is None

    expired_at = now - timedelta(minutes=5)
    with session_factory() as db:
        record = db.get(UserSession, expired_session.session_id)
        record.expires_at = expired_at.isoformat()
        db.commit()

    with session_factory() as db:
        record = db.get(UserSession, expired_session.session_id)
        result = auth_service.touch_session(
            db,
            record,
            settings=settings,
            ip_address="10.0.0.3",
            user_agent="Expired",
            commit=False,
        )
        assert result is None
        assert record.last_seen_ip is None
        assert record.expires_at == expired_at.isoformat()


def test_deactivated_user_cannot_use_basic_or_session(app_client) -> None:
    client, _, _ = app_client
    settings = config.get_settings()
    login = client.post("/auth/login/basic")
    assert login.status_code == 200
    cookie = client.cookies.get(settings.session_cookie_name)
    assert cookie is not None

    session_factory = get_sessionmaker()
    with session_factory() as db:
        user = db.query(User).filter(User.email == "admin@example.com").one()
        user.is_active = False
        db.commit()

    session_response = client.get("/auth/session")
    assert session_response.status_code == 403

    retry_login = client.post("/auth/login/basic")
    assert retry_login.status_code in {401, 403}


def test_session_request_updates_last_seen_metadata(app_client) -> None:
    client, _, _ = app_client
    settings = config.get_settings()
    cookie_value = client.cookies.get(settings.session_cookie_name)
    assert cookie_value is not None

    token_hash = auth_service.hash_session_token(cookie_value)
    session_factory = get_sessionmaker()
    with session_factory() as db:
        record = (
            db.query(UserSession)
            .filter(UserSession.token_hash == token_hash)
            .one()
        )
        original_seen = datetime.fromisoformat(record.last_seen_at)
        record.last_seen_ip = None
        record.last_seen_user_agent = None
        db.commit()

    headers = {"User-Agent": "pytest-session-check"}
    response = client.get("/documents", headers=headers)
    assert response.status_code == 200

    with session_factory() as db:
        refreshed = (
            db.query(UserSession)
            .filter(UserSession.token_hash == token_hash)
            .one()
        )
        assert refreshed.last_seen_ip == "testclient"
        assert refreshed.last_seen_user_agent == "pytest-session-check"
        assert datetime.fromisoformat(refreshed.last_seen_at) > original_seen


def test_get_authenticated_identity_session_success(app_client) -> None:
    client, _, _ = app_client
    settings = config.get_settings()
    cookie_value = client.cookies.get(settings.session_cookie_name)
    assert cookie_value is not None

    session_factory = get_sessionmaker()
    with session_factory() as db:
        request = _make_request_stub()
        request.client.host = "resolver-test"
        request.headers["user-agent"] = "pytest-agent"
        identity = _resolve_identity(
            request,
            settings=settings,
            db=db,
            session_token=cookie_value,
        )

    assert identity.user is not None
    assert identity.mode == "session"
    assert identity.session is not None
    assert identity.session.last_seen_ip == "resolver-test"
    assert identity.session.last_seen_user_agent == "pytest-agent"


def test_get_authenticated_identity_invalid_session(app_client) -> None:
    client, _, _ = app_client
    del client
    settings = config.get_settings()

    session_factory = get_sessionmaker()
    with session_factory() as db:
        request = _make_request_stub()
        request.client.host = "resolver-test"
        request.headers["user-agent"] = "pytest-agent"
        with pytest.raises(HTTPException) as exc_info:
            _resolve_identity(
                request,
                settings=settings,
                db=db,
                session_token="invalid-token",
            )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Invalid session token"


def test_get_authenticated_identity_invalid_session_rescued_by_api_key(app_client) -> None:
    client, _, _ = app_client
    settings = config.get_settings()

    session_factory = get_sessionmaker()
    with session_factory() as db:
        user = db.query(User).filter(User.email == "admin@example.com").one()

    token = "resolver-mixed-credentials"
    _insert_api_key(user, token)

    with session_factory() as db:
        request = _make_request_stub()
        request.client.host = "resolver-test"
        request.headers["user-agent"] = "pytest-agent"
        identity = _resolve_identity(
            request,
            settings=settings,
            db=db,
            session_token="invalid-token",
            header_token=token,
        )

    assert identity.user.user_id == user.user_id
    assert identity.mode == "api-key"
    assert identity.session is None
    assert identity.session_id is None
    assert identity.api_key is not None


def test_get_authenticated_identity_api_key_success(app_client) -> None:
    client, _, _ = app_client
    settings = config.get_settings()

    session_factory = get_sessionmaker()
    with session_factory() as db:
        user = db.query(User).filter(User.email == "admin@example.com").one()

    token = "resolver-api-token"
    _insert_api_key(user, token)

    with session_factory() as db:
        request = _make_request_stub()
        request.client.host = "resolver-test"
        request.headers["user-agent"] = "pytest-agent"
        identity = _resolve_identity(
            request,
            settings=settings,
            db=db,
            header_token=token,
        )

    assert identity.user is not None
    assert identity.mode == "api-key"
    assert identity.api_key is not None
    assert identity.api_key.last_used_at is not None


def test_protected_routes_require_authentication(app_client_factory, tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "auth.sqlite"
    documents_dir = tmp_path / "docs"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("ADE_AUTH_MODES", "basic")
    monkeypatch.setenv("ADE_SESSION_COOKIE_SECURE", "0")
    with app_client_factory(database_url, documents_dir) as client:
        client.auth = None
        client.cookies.clear()
        response = client.get("/documents")
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers
        health = client.get("/health")
        assert health.status_code == 200


def test_api_key_allows_access(app_client) -> None:
    client, _, _ = app_client
    session_factory = get_sessionmaker()
    with session_factory() as db:
        user = db.query(User).filter(User.email == "admin@example.com").one()
    token = "machine-token-1234567890"
    _insert_api_key(user, token)
    client.auth = None
    client.cookies.clear()
    response = client.get(
        "/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


def test_invalid_api_key_returns_403(app_client) -> None:
    client, _, _ = app_client
    client.auth = None
    client.cookies.clear()
    response = client.get(
        "/documents",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 403


def test_api_key_logout_only_clears_cookies(app_client) -> None:
    client, _, _ = app_client
    session_factory = get_sessionmaker()
    with session_factory() as db:
        user = db.query(User).filter(User.email == "admin@example.com").one()

    token = "machine-token-logout"
    _insert_api_key(user, token)
    client.auth = None
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {token}"}

    first = client.get("/documents", headers=headers)
    assert first.status_code == 200

    logout = client.post("/auth/logout", headers=headers)
    assert logout.status_code == 204

    repeat = client.get("/documents", headers=headers)
    assert repeat.status_code == 200

    with session_factory() as db:
        api_key = (
            db.query(ApiKey)
            .filter(ApiKey.token_hash == auth_service.hash_api_key_token(token))
            .one()
        )
        assert api_key.revoked_at is None


def test_api_key_usage_updates_last_used_at(app_client) -> None:
    client, _, _ = app_client
    session_factory = get_sessionmaker()
    with session_factory() as db:
        user = db.query(User).filter(User.email == "admin@example.com").one()

    token = "machine-token-usage"
    _insert_api_key(user, token)
    client.auth = None
    client.cookies.clear()
    before = datetime.now(timezone.utc)

    response = client.get(
        "/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    with session_factory() as db:
        api_key = (
            db.query(ApiKey)
            .filter(ApiKey.token_hash == auth_service.hash_api_key_token(token))
            .one()
        )
        assert api_key.last_used_at is not None
        recorded = datetime.fromisoformat(api_key.last_used_at)
        assert recorded >= before - timedelta(seconds=5)
        assert recorded <= datetime.now(timezone.utc) + timedelta(seconds=5)


def test_api_key_provisioning_flow(app_client) -> None:
    client, _, _ = app_client
    session_factory = get_sessionmaker()

    with session_factory() as db:
        user = db.query(User).filter(User.email == "admin@example.com").one()
        user_id = user.user_id

    create = client.post(
        "/auth/api-keys",
        json={"user_id": user_id, "name": "Automation"},
    )
    assert create.status_code == 201
    body = create.json()
    assert body["user"]["user_id"] == user_id
    assert body["name"] == "Automation"
    assert body["token_prefix"] == body["token"][:12]

    raw_token = body["token"]
    api_key_id = body["api_key_id"]
    token_prefix = body["token_prefix"]

    with session_factory() as db:
        stored = db.get(ApiKey, api_key_id)
        assert stored is not None
        assert stored.token_prefix == token_prefix
        assert stored.token_hash == auth_service.hash_api_key_token(raw_token)

    listing = client.get("/auth/api-keys")
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert any(item["api_key_id"] == api_key_id for item in items)
    listed = next(item for item in items if item["api_key_id"] == api_key_id)
    assert listed["user"]["email"] == "admin@example.com"
    assert listed["token_prefix"] == token_prefix
    assert "token" not in listed

    revoke = client.post(
        f"/auth/api-keys/{api_key_id}/revoke",
        json={"reason": "rotation"},
    )
    assert revoke.status_code == 200
    revoked = revoke.json()
    assert revoked["revoked_at"] is not None
    assert revoked["revoked_reason"] == "rotation"

    with session_factory() as db:
        events = (
            db.query(Event)
            .filter(Event.entity_type == "api-key", Event.entity_id == api_key_id)
            .order_by(Event.occurred_at)
            .all()
        )
        assert [event.event_type for event in events] == [
            "api-key.created",
            "api-key.revoked",
        ]
        assert events[1].payload.get("reason") == "rotation"

    client.auth = None
    client.cookies.clear()
    denied = client.get(
        "/documents",
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    assert denied.status_code == 403


def test_revoked_api_key_is_rejected(app_client) -> None:
    client, _, _ = app_client
    session_factory = get_sessionmaker()
    with session_factory() as db:
        user = db.query(User).filter(User.email == "admin@example.com").one()

    token = "machine-token-revoked"
    _insert_api_key(user, token)

    with session_factory() as db:
        api_key = (
            db.query(ApiKey)
            .filter(ApiKey.token_hash == auth_service.hash_api_key_token(token))
            .one()
        )
        api_key.revoked_at = datetime.now(timezone.utc).isoformat()
        db.commit()

    client.auth = None
    client.cookies.clear()
    response = client.get(
        "/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_open_access_mode_disables_auth(app_client_factory, tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "open.sqlite"
    documents_dir = tmp_path / "docs"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("ADE_SESSION_COOKIE_SECURE", "0")
    monkeypatch.setenv("AUTH_DISABLED", "1")
    with app_client_factory(database_url, documents_dir) as client:
        client.auth = None
        login = client.post("/auth/login/basic")
        assert login.status_code == 404

        documents = client.get("/documents")
        assert documents.status_code == 200

        request = _make_request_stub()
        settings = config.get_settings()
        session_factory = get_sessionmaker()
        with session_factory() as db:
            identity = _resolve_identity(
                request,
                settings=settings,
                db=db,
            )

        assert identity.user.email == "open-access@ade.local"
        assert identity.mode == "none"
        assert identity.session_id is None
        assert identity.api_key_id is None

        profile = client.get("/auth/me")
        assert profile.status_code == 200
        body = profile.json()
        assert body["modes"] == ["none"]
        assert body["user"]["role"] == "admin"
        assert body["user"]["email"] == "open-access@ade.local"

        logout = client.post("/auth/logout")
        assert logout.status_code == 204


def test_basic_login_disabled_when_mode_missing(app_client_factory, tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "sso-only.sqlite"
    documents_dir = tmp_path / "docs"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("ADE_AUTH_MODES", "sso")
    monkeypatch.setenv("ADE_SESSION_COOKIE_SECURE", "0")
    monkeypatch.setenv("ADE_SSO_CLIENT_ID", "client-123")
    monkeypatch.setenv("ADE_SSO_CLIENT_SECRET", "secret")
    monkeypatch.setenv("ADE_SSO_ISSUER", "https://auth_service.example.com")
    monkeypatch.setenv("ADE_SSO_REDIRECT_URL", "https://ade.example.com/auth/callback")
    with app_client_factory(database_url, documents_dir) as client:
        response = client.post("/auth/login/basic", auth=("admin@example.com", "password123"))
        assert response.status_code == 404


def _encode_hs256_token(
    secret: bytes,
    issuer: str,
    audience: str,
    nonce: str,
    *,
    overrides: dict[str, object] | None = None,
) -> str:
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

    if overrides:
        payload.update(overrides)

    signing_input = ".".join(
        [
            _b64url(json.dumps(header, separators=(",", ":"), sort_keys=True).encode()),
            _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()),
        ]
    )
    signature = hmac.new(secret, signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(signature)}"


def test_sso_callback_issues_session(app_client_factory, tmp_path, monkeypatch) -> None:
    issuer = "https://auth_service.example.com"
    db_path = tmp_path / "auth_service.sqlite"
    documents_dir = tmp_path / "docs"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("ADE_AUTH_MODES", "basic,sso")
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
        get_calls: list[str] = []
        post_calls = 0

        def fake_get(url: str, *args, **kwargs) -> httpx.Response:
            get_calls.append(url)
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
            nonlocal post_calls
            assert url == token_endpoint
            post_calls += 1
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
        assert get_calls == [discovery_url, jwks_url]
        assert post_calls == 1

        client.cookies.clear()
        second_redirect = client.get("/auth/sso/login")
        assert second_redirect.status_code == 307
        second_location = second_redirect.headers["Location"]
        second_query = urllib.parse.parse_qs(urllib.parse.urlparse(second_location).query)
        state_holder["nonce"] = second_query["nonce"][0]
        second_state = second_query["state"][0]
        second_callback = client.get(
            "/auth/sso/callback",
            params={"code": "def", "state": second_state},
        )
        assert second_callback.status_code == 200
        assert post_calls == 2
        assert get_calls == [discovery_url, jwks_url]


def test_sso_callback_auto_provisions_user(app_client_factory, tmp_path, monkeypatch) -> None:
    issuer = "https://auth_service.example.com"
    db_path = tmp_path / "sso-auto.sqlite"
    documents_dir = tmp_path / "docs"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("ADE_AUTH_MODES", "sso")
    monkeypatch.setenv("ADE_SESSION_COOKIE_SECURE", "0")
    monkeypatch.setenv("ADE_SSO_CLIENT_ID", "client-123")
    monkeypatch.setenv("ADE_SSO_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("ADE_SSO_ISSUER", issuer)
    monkeypatch.setenv("ADE_SSO_REDIRECT_URL", "https://ade.internal/auth/sso/callback")
    monkeypatch.setenv("ADE_SSO_AUTO_PROVISION", "1")

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
            assert (
                db.query(User)
                .filter(User.email == "auto@example.com")
                .count()
                == 0
            )

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
            token = _encode_hs256_token(
                secret,
                issuer,
                "client-123",
                nonce,
                overrides={"email": "auto@example.com", "sub": "oidc-auto"},
            )
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

        callback = client.get("/auth/sso/callback", params={"code": "auto", "state": state})
        assert callback.status_code == 200
        body = callback.json()
        assert body["user"]["email"] == "auto@example.com"
        assert body["user"]["role"] == "viewer"

        cookie = client.cookies.get(config.get_settings().session_cookie_name)
        assert cookie is not None

        with session_factory() as db:
            user = db.query(User).filter(User.email == "auto@example.com").one()
            assert user.sso_provider == issuer
            assert user.sso_subject == "oidc-auto"
            assert user.password_hash is None
            session_record = (
                db.query(UserSession)
                .filter(UserSession.user_id == user.user_id)
                .order_by(UserSession.issued_at.desc())
                .first()
            )
            assert session_record is not None

    auth_service.clear_caches()


def test_sso_callback_rejects_unexpected_nonce(app_client_factory, tmp_path, monkeypatch) -> None:
    issuer = "https://auth_service.example.com"
    db_path = tmp_path / "sso-nonce.sqlite"
    documents_dir = tmp_path / "docs"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("ADE_AUTH_MODES", "basic,sso")
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
            token = _encode_hs256_token(secret, issuer, "client-123", "unexpected")
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
        assert callback.status_code == 400
        assert callback.json()["detail"] == "Unexpected nonce in ID token"

    auth_service.clear_caches()


def test_sso_state_token_accepts_signature_with_dot(monkeypatch, tmp_path) -> None:
    issuer = "https://auth_service.example.com"
    overrides = {
        "ADE_AUTH_MODES": "sso",
        "ADE_SSO_CLIENT_SECRET": "compat-secret",
        "ADE_SSO_CLIENT_ID": "client-123",
        "ADE_SSO_ISSUER": issuer,
        "ADE_SSO_REDIRECT_URL": "https://ade.internal/auth/callback",
    }

    with _configured_settings(monkeypatch, tmp_path, **overrides) as (settings, _):
        assert settings.sso_client_secret == "compat-secret"
        secret = settings.sso_client_secret.encode("utf-8")
        expiry = int(time.time()) + 300

        for attempt in range(1024):
            nonce = f"nonce-{attempt}"
            payload = {"exp": expiry, "nonce": nonce}
            body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
            signature = hmac.new(secret, body, hashlib.sha256).digest()
            if b"." not in signature:
                continue

            legacy = base64.urlsafe_b64encode(body + b"." + signature).decode("ascii").rstrip("=")
            parsed = auth_service._verify_state_token(settings, legacy)
            assert parsed["nonce"] == nonce
            assert parsed["exp"] == expiry
            break
        else:  # pragma: no cover - defensive
            pytest.fail("Unable to generate signature containing dot byte")


def test_verify_bearer_token_rs256(monkeypatch, tmp_path) -> None:
    issuer = "https://auth_service.example.com"
    discovery_url = f"{issuer}/.well-known/openid-configuration"
    jwks_url = f"{issuer}/jwks"
    auth_service.clear_caches()
    jwks_payload = {"keys": [_rs256_jwk("rs256-key")]} 
    get_calls: list[str] = []

    def fake_get(url: str, *args, **kwargs) -> httpx.Response:
        get_calls.append(url)
        if url == discovery_url:
            return httpx.Response(
                200,
                json={
                    "issuer": issuer,
                    "authorization_endpoint": f"{issuer}/authorize",
                    "token_endpoint": f"{issuer}/token",
                    "jwks_uri": jwks_url,
                },
            )
        if url == jwks_url:
            return httpx.Response(200, json=jwks_payload)
        raise AssertionError(f"Unexpected GET {url}")

    monkeypatch.setenv("ADE_SSO_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("ADE_SSO_CLIENT_ID", "client-123")
    monkeypatch.setenv("ADE_SSO_ISSUER", issuer)
    monkeypatch.setenv("ADE_SSO_REDIRECT_URL", "https://ade.internal/auth/callback")
    monkeypatch.setenv("ADE_SSO_CACHE_TTL_SECONDS", "60")
    monkeypatch.setenv("ADE_AUTH_MODES", "basic,sso")
    monkeypatch.setenv("ADE_SESSION_COOKIE_SECURE", "0")
    monkeypatch.setattr(httpx, "get", fake_get)

    overrides = {
        "ADE_DATABASE_URL": f"sqlite:///{tmp_path / 'rs256.sqlite'}",
        "ADE_AUTH_MODES": "basic,sso",
    }

    with _configured_settings(monkeypatch, tmp_path, **overrides) as (settings, session_factory):
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

        token = _encode_rs256_token(issuer, "client-123")

        with session_factory() as db:
            resolved, claims = auth_service.verify_bearer_token(settings, token=token, db=db)
            first_user_id = resolved.user_id
            assert claims["sub"] == "sso-user-1"

        assert get_calls == [discovery_url, jwks_url]

        with session_factory() as db:
            second, _ = auth_service.verify_bearer_token(settings, token=token, db=db)
            assert second.user_id == first_user_id

        assert get_calls == [discovery_url, jwks_url]
    auth_service.clear_caches()


def test_verify_bearer_token_rejects_unknown_kid(monkeypatch, tmp_path) -> None:
    issuer = "https://auth_service.example.com"
    discovery_url = f"{issuer}/.well-known/openid-configuration"
    jwks_url = f"{issuer}/jwks"
    auth_service.clear_caches()
    jwks_payload = {"keys": [_rs256_jwk("rs256-key")]}
    get_calls: list[str] = []

    def fake_get(url: str, *args, **kwargs) -> httpx.Response:
        get_calls.append(url)
        if url == discovery_url:
            return httpx.Response(
                200,
                json={
                    "issuer": issuer,
                    "authorization_endpoint": f"{issuer}/authorize",
                    "token_endpoint": f"{issuer}/token",
                    "jwks_uri": jwks_url,
                },
            )
        if url == jwks_url:
            return httpx.Response(200, json=jwks_payload)
        raise AssertionError(f"Unexpected GET {url}")

    monkeypatch.setattr(httpx, "get", fake_get)

    overrides = {
        "ADE_DATABASE_URL": f"sqlite:///{tmp_path / 'rs256-kid.sqlite'}",
        "ADE_AUTH_MODES": "basic,sso",
        "ADE_SSO_CLIENT_SECRET": "client-secret",
        "ADE_SSO_CLIENT_ID": "client-123",
        "ADE_SSO_ISSUER": issuer,
        "ADE_SSO_REDIRECT_URL": "https://ade.internal/auth/callback",
        "ADE_SSO_CACHE_TTL_SECONDS": "60",
    }

    with _configured_settings(monkeypatch, tmp_path, **overrides) as (settings, session_factory):
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

        valid = _encode_rs256_token(issuer, "client-123", kid="rs256-key")
        with session_factory() as db:
            auth_service.verify_bearer_token(settings, token=valid, db=db)

        assert get_calls == [discovery_url, jwks_url]

        unknown = _encode_rs256_token(issuer, "client-123", kid="other-key")
        with session_factory() as db:
            with pytest.raises(auth_service.SSOExchangeError, match="Signing key not found"):
                auth_service.verify_bearer_token(settings, token=unknown, db=db)

        assert get_calls == [discovery_url, jwks_url]
    auth_service.clear_caches()


def test_verify_bearer_token_rejects_expired_token(monkeypatch, tmp_path) -> None:
    issuer = "https://auth_service.example.com"
    discovery_url = f"{issuer}/.well-known/openid-configuration"
    jwks_url = f"{issuer}/jwks"
    auth_service.clear_caches()
    jwks_payload = {"keys": [_rs256_jwk("rs256-key")]} 

    def fake_get(url: str, *args, **kwargs) -> httpx.Response:
        if url == discovery_url:
            return httpx.Response(
                200,
                json={
                    "issuer": issuer,
                    "authorization_endpoint": f"{issuer}/authorize",
                    "token_endpoint": f"{issuer}/token",
                    "jwks_uri": jwks_url,
                },
            )
        if url == jwks_url:
            return httpx.Response(200, json=jwks_payload)
        raise AssertionError(f"Unexpected GET {url}")

    monkeypatch.setattr(httpx, "get", fake_get)

    overrides = {
        "ADE_DATABASE_URL": f"sqlite:///{tmp_path / 'rs256-expired.sqlite'}",
        "ADE_AUTH_MODES": "basic,sso",
        "ADE_SSO_CLIENT_SECRET": "client-secret",
        "ADE_SSO_CLIENT_ID": "client-123",
        "ADE_SSO_ISSUER": issuer,
        "ADE_SSO_REDIRECT_URL": "https://ade.internal/auth/callback",
        "ADE_SSO_CACHE_TTL_SECONDS": "60",
    }

    with _configured_settings(monkeypatch, tmp_path, **overrides) as (settings, session_factory):
        token = _encode_rs256_token(
            issuer,
            "client-123",
            overrides={"exp": int(time.time()) - 10},
        )
        with session_factory() as db:
            with pytest.raises(auth_service.SSOExchangeError, match="ID token expired"):
                auth_service.verify_bearer_token(settings, token=token, db=db)
    auth_service.clear_caches()


def test_verify_bearer_token_rejects_audience_mismatch(monkeypatch, tmp_path) -> None:
    issuer = "https://auth_service.example.com"
    discovery_url = f"{issuer}/.well-known/openid-configuration"
    jwks_url = f"{issuer}/jwks"
    auth_service.clear_caches()
    jwks_payload = {"keys": [_rs256_jwk("rs256-key")]} 

    def fake_get(url: str, *args, **kwargs) -> httpx.Response:
        if url == discovery_url:
            return httpx.Response(
                200,
                json={
                    "issuer": issuer,
                    "authorization_endpoint": f"{issuer}/authorize",
                    "token_endpoint": f"{issuer}/token",
                    "jwks_uri": jwks_url,
                },
            )
        if url == jwks_url:
            return httpx.Response(200, json=jwks_payload)
        raise AssertionError(f"Unexpected GET {url}")

    monkeypatch.setattr(httpx, "get", fake_get)

    overrides = {
        "ADE_DATABASE_URL": f"sqlite:///{tmp_path / 'rs256-aud.sqlite'}",
        "ADE_AUTH_MODES": "basic,sso",
        "ADE_SSO_CLIENT_SECRET": "client-secret",
        "ADE_SSO_CLIENT_ID": "client-123",
        "ADE_SSO_ISSUER": issuer,
        "ADE_SSO_REDIRECT_URL": "https://ade.internal/auth/callback",
        "ADE_SSO_CACHE_TTL_SECONDS": "60",
    }

    with _configured_settings(monkeypatch, tmp_path, **overrides) as (settings, session_factory):
        token = _encode_rs256_token(issuer, "client-123", overrides={"aud": "other-audience"})
        with session_factory() as db:
            with pytest.raises(auth_service.SSOExchangeError, match="audience mismatch"):
                auth_service.verify_bearer_token(settings, token=token, db=db)
    auth_service.clear_caches()


def test_manage_cli_flows(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "manage.sqlite"
    documents_dir = tmp_path / "docs"
    monkeypatch.setenv("ADE_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("ADE_DOCUMENTS_DIR", str(documents_dir))
    monkeypatch.setenv("ADE_AUTH_MODES", "basic")
    monkeypatch.setenv("ADE_SESSION_COOKIE_SECURE", "0")
    operator = "ops@example.com"
    try:
        assert (
            auth_service.main([
                "create-user",
                "cli@example.com",
                "--password",
                "cli-pass",
                "--role",
                "viewer",
                "--operator-email",
                operator,
            ])
            == 0
        )
        assert (
            auth_service.main([
                "promote",
                "cli@example.com",
                "--operator-email",
                operator,
            ])
            == 0
        )
        assert (
            auth_service.main(
                [
                    "reset-password",
                    "cli@example.com",
                    "--password",
                    "new-pass",
                    "--operator-email",
                    operator,
                ]
            )
            == 0
        )
        assert (
            auth_service.main([
                "deactivate",
                "cli@example.com",
                "--operator-email",
                operator,
            ])
            == 0
        )

        session_factory = get_sessionmaker()
        with session_factory() as db:
            user = db.query(User).filter(User.email == "cli@example.com").one()
            assert user.role == UserRole.ADMIN
            assert not user.is_active
            assert auth_service.verify_password("new-pass", user.password_hash)
            user_id = user.user_id

        with session_factory() as db:
            events = (
                db.query(Event)
                .filter(Event.entity_type == "user", Event.entity_id == user_id)
                .order_by(Event.occurred_at)
                .all()
            )

        assert [event.event_type for event in events] == [
            "user.created",
            "user.promoted",
            "user.password.reset",
            "user.deactivated",
        ]
        for event in events:
            assert event.actor_type == "system"
            assert event.actor_label == operator
            assert event.actor_id == operator
            assert event.source == "cli"
            assert event.payload["email"] == "cli@example.com"

        assert events[0].payload == {"email": "cli@example.com", "role": UserRole.VIEWER.value}
        assert events[1].payload == {"email": "cli@example.com", "role": UserRole.ADMIN.value}
        assert events[2].payload == {"email": "cli@example.com"}
        assert events[3].payload == {"email": "cli@example.com"}

        assert auth_service.main(["list-users"]) == 0
    finally:
        config.reset_settings_cache()
