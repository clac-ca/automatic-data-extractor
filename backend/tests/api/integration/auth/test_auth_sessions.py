from __future__ import annotations

import anyio
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from urllib.parse import parse_qs, urlparse

from ade_api.features.authn.totp import totp_now
from ade_db.models import AuthSession
from ade_api.settings import Settings

pytestmark = pytest.mark.asyncio


async def test_cookie_login_sets_session_and_bootstrap(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
    db_session,
) -> None:
    admin = seed_identity.admin

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": admin.password},
    )
    assert response.status_code == 200, response.text
    assert async_client.cookies.get(settings.session_cookie_name)

    def _load_tokens():
        return db_session.execute(select(AuthSession)).scalars().all()

    tokens = await anyio.to_thread.run_sync(_load_tokens)
    assert len(tokens) == 1
    assert tokens[0].user_id == admin.id

    bootstrap = await async_client.get("/api/v1/me/bootstrap")
    assert bootstrap.status_code == 200, bootstrap.text
    payload = bootstrap.json()
    assert payload["user"]["email"] == admin.email


async def test_cookie_logout_revokes_access_tokens(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
    db_session,
) -> None:
    admin = seed_identity.admin

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": admin.password},
    )
    assert response.status_code == 200, response.text

    bootstrap = await async_client.get("/api/v1/me/bootstrap")
    assert bootstrap.status_code == 200, bootstrap.text
    csrf_cookie = async_client.cookies.get(settings.session_csrf_cookie_name)
    assert csrf_cookie

    logout = await async_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert logout.status_code == 204, logout.text
    assert not async_client.cookies.get(settings.session_cookie_name)

    def _load_tokens():
        return db_session.execute(select(AuthSession)).scalars().all()

    tokens = await anyio.to_thread.run_sync(_load_tokens)
    assert len(tokens) == 1
    assert tokens[0].revoked_at is not None


async def test_mfa_recovery_code_accepts_compact_and_hyphenated_formats(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
) -> None:
    admin = seed_identity.admin

    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": admin.password},
    )
    assert login.status_code == 200, login.text
    csrf_cookie = async_client.cookies.get(settings.session_csrf_cookie_name)
    assert csrf_cookie

    start = await async_client.post(
        "/api/v1/auth/mfa/totp/enroll/start",
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert start.status_code == 200, start.text
    otpauth_uri = start.json()["otpauthUri"]
    secret = parse_qs(urlparse(otpauth_uri).query)["secret"][0]
    code = totp_now(secret)

    confirm = await async_client.post(
        "/api/v1/auth/mfa/totp/enroll/confirm",
        json={"code": code},
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert confirm.status_code == 200, confirm.text
    recovery_codes = confirm.json()["recoveryCodes"]
    assert len(recovery_codes) >= 2
    compact_recovery = recovery_codes[0].replace("-", "")
    hyphenated_recovery = recovery_codes[1]

    logout = await async_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert logout.status_code == 204, logout.text

    login_for_compact = await async_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": admin.password},
    )
    assert login_for_compact.status_code == 200, login_for_compact.text
    compact_payload = login_for_compact.json()
    assert compact_payload["mfa_required"] is True
    compact_challenge = compact_payload.get("challengeToken") or compact_payload.get("challenge_token")
    assert compact_challenge

    compact_verify = await async_client.post(
        "/api/v1/auth/mfa/challenge/verify",
        json={"challengeToken": compact_challenge, "code": compact_recovery},
    )
    assert compact_verify.status_code == 200, compact_verify.text

    csrf_cookie_after_compact = async_client.cookies.get(settings.session_csrf_cookie_name)
    assert csrf_cookie_after_compact
    second_logout = await async_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_cookie_after_compact},
    )
    assert second_logout.status_code == 204, second_logout.text

    login_for_hyphen = await async_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": admin.password},
    )
    assert login_for_hyphen.status_code == 200, login_for_hyphen.text
    hyphen_payload = login_for_hyphen.json()
    assert hyphen_payload["mfa_required"] is True
    hyphen_challenge = hyphen_payload.get("challengeToken") or hyphen_payload.get("challenge_token")
    assert hyphen_challenge

    hyphen_verify = await async_client.post(
        "/api/v1/auth/mfa/challenge/verify",
        json={"challengeToken": hyphen_challenge, "code": hyphenated_recovery},
    )
    assert hyphen_verify.status_code == 200, hyphen_verify.text

    csrf_cookie_after_hyphen = async_client.cookies.get(settings.session_csrf_cookie_name)
    assert csrf_cookie_after_hyphen
    third_logout = await async_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_cookie_after_hyphen},
    )
    assert third_logout.status_code == 204, third_logout.text

    login_for_replay = await async_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": admin.password},
    )
    assert login_for_replay.status_code == 200, login_for_replay.text
    replay_payload = login_for_replay.json()
    assert replay_payload["mfa_required"] is True
    replay_challenge = replay_payload.get("challengeToken") or replay_payload.get("challenge_token")
    assert replay_challenge

    replay_verify = await async_client.post(
        "/api/v1/auth/mfa/challenge/verify",
        json={"challengeToken": replay_challenge, "code": hyphenated_recovery},
    )
    assert replay_verify.status_code == 400
