from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app import config
from backend.app.db import get_sessionmaker
from backend.app.models import User, UserRole
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


def test_decode_access_token_with_expired_token_raises(monkeypatch) -> None:
    monkeypatch.setenv("ADE_JWT_SECRET_KEY", "expire-test-secret")
    config.reset_settings_cache()
    settings = config.get_settings()
    session_factory = get_sessionmaker()
    with session_factory() as db:
        user = db.query(User).filter(User.email == DEFAULT_USER_EMAIL).one()
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
