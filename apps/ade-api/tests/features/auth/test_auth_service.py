from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.features.auth.models import APIKey
from ade_api.features.auth.repository import APIKeysRepository
from ade_api.features.auth.service import (
    ApiKeyService,
    AuthService,
    DevIdentityService,
    PasswordAuthService,
)
from ade_api.features.users.models import User
from ade_api.features.users.repository import UsersRepository
from ade_api.settings import Settings, get_settings
from ade_api.shared.db.session import get_sessionmaker


def _make_request(
    *,
    scheme: str = "http",
    headers: dict[str, str] | None = None,
) -> Request:
    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/",
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
        "scheme": scheme,
        "server": ("testserver", 443 if scheme == "https" else 80),
    }
    return Request(scope)


def test_is_secure_request_trusts_forwarded_proto_only_for_https() -> None:
    service = AuthService(session=MagicMock(), settings=Settings())

    request = _make_request(headers={"X-Forwarded-Proto": "https"})

    assert service.is_secure_request(request) is True


def test_is_secure_request_ignores_forwarded_proto_http_downgrade() -> None:
    service = AuthService(session=MagicMock(), settings=Settings())

    request = _make_request(scheme="https", headers={"X-Forwarded-Proto": "http"})

    assert service.is_secure_request(request) is True


def test_is_secure_request_uses_scope_scheme_when_available() -> None:
    service = AuthService(session=MagicMock(), settings=Settings())

    request = _make_request(scheme="https")

    assert service.is_secure_request(request) is True


def test_get_lockout_error_shapes_retry_after() -> None:
    settings = Settings()
    service = PasswordAuthService(
        session=MagicMock(spec=AsyncSession),
        settings=settings,
        users=MagicMock(),
    )
    user = User(email="locked@example.test", is_active=True)
    user.failed_login_count = 3
    user.locked_until = datetime.now(UTC) + timedelta(minutes=5)

    error = service.get_lockout_error(user)

    assert error is not None
    assert error.status_code == 403
    detail = error.detail
    assert isinstance(detail, dict)
    assert detail.get("failedAttempts") == 3
    assert isinstance(detail.get("retryAfterSeconds"), int)
    assert error.headers and "Retry-After" in error.headers


def test_get_lockout_error_returns_none_when_unlocked() -> None:
    service = PasswordAuthService(
        session=MagicMock(spec=AsyncSession),
        settings=Settings(),
        users=MagicMock(),
    )
    user = User(email="ok@example.test", is_active=True)
    user.failed_login_count = 0
    user.locked_until = None

    assert service.get_lockout_error(user) is None


@pytest.mark.asyncio
async def test_dev_identity_runs_expensive_steps_once(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    session_factory = get_sessionmaker(settings=settings)
    DevIdentityService._dev_setup_done = False
    DevIdentityService._dev_user_id = None

    calls: dict[str, int] = {"sync": 0, "assign": 0}

    async def fake_sync_permission_registry(*, session: AsyncSession) -> None:
        calls["sync"] += 1

    async def fake_assign(**kwargs) -> None:
        calls["assign"] += 1

    monkeypatch.setattr(
        "ade_api.features.auth.service.sync_permission_registry",
        fake_sync_permission_registry,
    )
    monkeypatch.setattr(
        "ade_api.features.auth.service._assign_global_role_if_missing_or_500",
        fake_assign,
    )

    try:
        async with session_factory() as session_one:
            service_one = AuthService(session=session_one, settings=settings)
            first_identity = await service_one.ensure_dev_identity()
            await session_one.commit()

        async with session_factory() as session_two:
            service_two = AuthService(session=session_two, settings=settings)
            second_identity = await service_two.ensure_dev_identity()

        assert calls["sync"] == 1
        assert calls["assign"] == 1
        assert first_identity.user.id == second_identity.user.id
    finally:
        DevIdentityService._dev_setup_done = False
        DevIdentityService._dev_user_id = None


@pytest.mark.asyncio
async def test_api_key_auth_resolves_user_without_relationship(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        users_repo = UsersRepository(session)
        api_repo = APIKeysRepository(session)
        api_service = ApiKeyService(
            session=session,
            settings=settings,
            users=users_repo,
            api_keys=api_repo,
        )

        user = await users_repo.create(
            email="robot@example.test",
            password_hash=None,
            is_active=True,
            is_service_account=True,
        )
        issue = await api_service.issue(user=user, label="Robot key")
        await session.flush()

        stored_id = issue.api_key.id

        async def fake_get_by_prefix(prefix: str) -> APIKey | None:
            record = await session.get(APIKey, stored_id)
            if record:
                record.user = None
            return record

        monkeypatch.setattr(api_repo, "get_by_prefix", fake_get_by_prefix)

        identity = await api_service.authenticate(issue.raw_key)

        assert identity.user.id == user.id
        assert identity.api_key is not None
