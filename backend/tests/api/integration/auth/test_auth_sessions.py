from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import anyio
import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select

from ade_api.common.time import utc_now
from ade_api.core.security import hash_opaque_token, mint_opaque_token
from ade_api.features.authn.service import AuthnService
from ade_api.features.authn.totp import totp_now
from ade_api.settings import Settings
from ade_db.models import AuthSession

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
    payload = response.json()
    assert payload["passwordChangeRequired"] is False
    assert async_client.cookies.get(settings.session_cookie_name)

    def _load_tokens():
        return (
            db_session.execute(select(AuthSession).where(AuthSession.user_id == admin.id))
            .scalars()
            .all()
        )

    tokens = await anyio.to_thread.run_sync(_load_tokens)
    assert len(tokens) == 1
    assert tokens[0].user_id == admin.id
    assert tokens[0].auth_method == "password"

    bootstrap = await async_client.get("/api/v1/me/bootstrap")
    assert bootstrap.status_code == 200, bootstrap.text
    payload = bootstrap.json()
    assert payload["user"]["email"] == admin.email


async def test_local_login_reports_recommended_mfa_setup_when_optional(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": member.email, "password": member.password},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["mfa_required"] is False
    assert payload["mfaSetupRecommended"] is True
    assert payload["mfaSetupRequired"] is False


async def test_local_login_reports_required_mfa_setup_when_enforced(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
    monkeypatch,
) -> None:
    member = seed_identity.member
    monkeypatch.setenv("ADE_AUTH_PASSWORD_MFA_REQUIRED", "true")

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": member.email, "password": member.password},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["mfa_required"] is False
    assert payload["mfaSetupRecommended"] is False
    assert payload["mfaSetupRequired"] is True


async def test_local_mfa_enforcement_blocks_profile_until_enrolled(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
    monkeypatch,
) -> None:
    member = seed_identity.member
    monkeypatch.setenv("ADE_AUTH_PASSWORD_MFA_REQUIRED", "true")

    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": member.email, "password": member.password},
    )
    assert login.status_code == 200, login.text
    csrf_cookie = async_client.cookies.get(settings.session_csrf_cookie_name)
    assert csrf_cookie

    blocked_profile = await async_client.get("/api/v1/me")
    assert blocked_profile.status_code == 403, blocked_profile.text
    blocked_payload = blocked_profile.json()
    error_codes = {
        item.get("code")
        for item in blocked_payload.get("errors", [])
        if isinstance(item, dict)
    }
    assert "mfa_setup_required" in error_codes

    bootstrap = await async_client.get("/api/v1/me/bootstrap")
    assert bootstrap.status_code == 200, bootstrap.text
    refreshed_csrf = async_client.cookies.get(settings.session_csrf_cookie_name)
    assert refreshed_csrf

    mfa_status = await async_client.get("/api/v1/auth/mfa/totp")
    assert mfa_status.status_code == 200, mfa_status.text
    status_payload = mfa_status.json()
    assert status_payload["onboardingRequired"] is True
    assert status_payload["skipAllowed"] is False

    enroll_start = await async_client.post(
        "/api/v1/auth/mfa/totp/enroll/start",
        headers={"X-CSRF-Token": refreshed_csrf},
    )
    assert enroll_start.status_code == 200, enroll_start.text
    otpauth_uri = enroll_start.json()["otpauthUri"]
    secret = parse_qs(urlparse(otpauth_uri).query)["secret"][0]

    enroll_confirm = await async_client.post(
        "/api/v1/auth/mfa/totp/enroll/confirm",
        json={"code": totp_now(secret)},
        headers={"X-CSRF-Token": refreshed_csrf},
    )
    assert enroll_confirm.status_code == 200, enroll_confirm.text

    unblocked_profile = await async_client.get("/api/v1/me")
    assert unblocked_profile.status_code == 200, unblocked_profile.text


async def test_local_mfa_enforcement_does_not_apply_to_sso_sessions(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ADE_AUTH_PASSWORD_MFA_REQUIRED", "true")
    member = seed_identity.member

    raw_token = mint_opaque_token()
    db_session.add(
        AuthSession(
            user_id=member.id,
            token_hash=hash_opaque_token(raw_token),
            auth_method="sso",
            expires_at=utc_now() + settings.session_access_ttl,
            revoked_at=None,
        )
    )
    db_session.flush()
    async_client.cookies.set(settings.session_cookie_name, raw_token)

    response = await async_client.get("/api/v1/me")
    assert response.status_code == 200, response.text


async def test_cookie_login_sets_secure_flag_when_public_url_is_https(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
) -> None:
    admin = seed_identity.admin
    settings.public_web_url = "https://ade.example.test"

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": admin.password},
    )
    assert response.status_code == 200, response.text
    set_cookie_headers = response.headers.get_list("set-cookie")
    session_cookie_header = next(
        (header for header in set_cookie_headers if settings.session_cookie_name in header),
        "",
    )
    assert "Secure" in session_cookie_header


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
        return (
            db_session.execute(select(AuthSession).where(AuthSession.user_id == admin.id))
            .scalars()
            .all()
        )

    tokens = await anyio.to_thread.run_sync(_load_tokens)
    assert len(tokens) == 1
    assert tokens[0].revoked_at is not None


async def test_cookie_logout_requires_csrf_header(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": admin.password},
    )
    assert login_response.status_code == 200, login_response.text

    missing_csrf = await async_client.post("/api/v1/auth/logout")
    assert missing_csrf.status_code == 403


async def test_auth_providers_include_password_reset_enabled_flag(
    async_client: AsyncClient,
) -> None:
    response = await async_client.get("/api/v1/auth/providers")
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["mode"] == "password_only"
    assert payload["password_reset_enabled"] is True


async def test_password_reset_forgot_accepts_request_when_enabled(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    response = await async_client.post(
        "/api/v1/auth/password/forgot",
        json={"email": seed_identity.member.email},
    )
    assert response.status_code == 202, response.text


async def test_password_reset_forgot_rejects_when_disabled(
    async_client: AsyncClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ADE_AUTH_PASSWORD_RESET_ENABLED", "false")

    response = await async_client.post(
        "/api/v1/auth/password/forgot",
        json={"email": "user@example.com"},
    )
    assert response.status_code == 403, response.text


async def test_password_reset_service_respects_disable_toggle(
    db_session,
    settings: Settings,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ADE_AUTH_PASSWORD_RESET_ENABLED", "false")
    service = AuthnService(session=db_session, settings=settings)

    with pytest.raises(HTTPException) as forgot_exc:
        service.forgot_password(email="user@example.com")
    assert forgot_exc.value.status_code == 403
    assert forgot_exc.value.detail == "Password reset is unavailable."

    with pytest.raises(HTTPException) as reset_exc:
        service.reset_password(token="reset-token", new_password="notsecret3!Ab")
    assert reset_exc.value.status_code == 403
    assert reset_exc.value.detail == "Password reset is unavailable."


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
    compact_challenge = compact_payload.get("challengeToken") or compact_payload.get(
        "challenge_token"
    )
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
    hyphen_challenge = hyphen_payload.get("challengeToken") or hyphen_payload.get(
        "challenge_token"
    )
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
    replay_challenge = replay_payload.get("challengeToken") or replay_payload.get(
        "challenge_token"
    )
    assert replay_challenge

    replay_verify = await async_client.post(
        "/api/v1/auth/mfa/challenge/verify",
        json={"challengeToken": replay_challenge, "code": hyphenated_recovery},
    )
    assert replay_verify.status_code == 400


async def test_local_login_lockout_blocks_valid_password_until_expiry(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
) -> None:
    admin = seed_identity.admin
    for _ in range(int(settings.auth_password_lockout_max_attempts)):
        failed_login = await async_client.post(
            "/api/v1/auth/login",
            json={"email": admin.email, "password": "incorrect-test-credential"},
        )
        assert failed_login.status_code == 401

    blocked_valid_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": admin.password},
    )
    assert blocked_valid_login.status_code == 423, blocked_valid_login.text


async def test_sso_enforcement_blocks_non_admin_and_preserves_global_admin_local_login(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
) -> None:
    admin = seed_identity.admin
    member = seed_identity.member

    admin_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": admin.password},
    )
    assert admin_login.status_code == 200, admin_login.text
    csrf_cookie = async_client.cookies.get(settings.session_csrf_cookie_name)
    assert csrf_cookie

    enroll_start = await async_client.post(
        "/api/v1/auth/mfa/totp/enroll/start",
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert enroll_start.status_code == 200, enroll_start.text
    otpauth_uri = enroll_start.json()["otpauthUri"]
    secret = parse_qs(urlparse(otpauth_uri).query)["secret"][0]
    current_code = totp_now(secret)

    enroll_confirm = await async_client.post(
        "/api/v1/auth/mfa/totp/enroll/confirm",
        json={"code": current_code},
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert enroll_confirm.status_code == 200, enroll_confirm.text

    create_provider = await async_client.post(
        "/api/v1/admin/sso/providers",
        json={
            "id": "entra-authn-hardening",
            "label": "Entra Test",
            "issuer": "https://login.microsoftonline.com/example/v2.0",
            "clientId": "client-id",
            "clientSecret": "client-secret",
            "status": "active",
            "domains": ["authn-hardening.local"],
        },
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert create_provider.status_code == 201, create_provider.text

    settings_read = await async_client.get("/api/v1/admin/settings")
    assert settings_read.status_code == 200, settings_read.text
    current_revision = settings_read.json()["revision"]

    enforce_mode = await async_client.patch(
        "/api/v1/admin/settings",
        json={
            "revision": current_revision,
            "changes": {
                "auth": {
                    "mode": "idp_only",
                    "identityProvider": {"jitProvisioningEnabled": True},
                }
            },
        },
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert enforce_mode.status_code == 200, enforce_mode.text

    providers = await async_client.get("/api/v1/auth/providers")
    assert providers.status_code == 200, providers.text
    providers_payload = providers.json()
    assert providers_payload["mode"] == "idp_only"
    assert providers_payload["password_reset_enabled"] is False

    forgot_while_enforced = await async_client.post(
        "/api/v1/auth/password/forgot",
        json={"email": member.email},
    )
    assert forgot_while_enforced.status_code == 403, forgot_while_enforced.text

    logout = await async_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert logout.status_code == 204, logout.text

    member_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": member.email, "password": member.password},
    )
    assert member_login.status_code == 403, member_login.text
    member_detail = member_login.json().get("detail")
    if isinstance(member_detail, dict):
        assert member_detail.get("error") == "sso_enforced"
    else:
        assert "Single sign-on is enforced" in str(member_detail)

    admin_local_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": admin.password},
    )
    assert admin_local_login.status_code == 200, admin_local_login.text
    admin_payload = admin_local_login.json()
    assert admin_payload["mfa_required"] is True
    assert (admin_payload.get("challengeToken") or admin_payload.get("challenge_token"))


async def test_mfa_status_and_recovery_regeneration(
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

    status_before = await async_client.get("/api/v1/auth/mfa/totp")
    assert status_before.status_code == 200, status_before.text
    before_payload = status_before.json()
    assert before_payload["enabled"] is False
    assert before_payload["recoveryCodesRemaining"] is None
    assert before_payload["onboardingRecommended"] is True
    assert before_payload["onboardingRequired"] is False
    assert before_payload["skipAllowed"] is True

    enroll_start = await async_client.post(
        "/api/v1/auth/mfa/totp/enroll/start",
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert enroll_start.status_code == 200, enroll_start.text
    otpauth_uri = enroll_start.json()["otpauthUri"]
    secret = parse_qs(urlparse(otpauth_uri).query)["secret"][0]

    enroll_confirm = await async_client.post(
        "/api/v1/auth/mfa/totp/enroll/confirm",
        json={"code": totp_now(secret)},
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert enroll_confirm.status_code == 200, enroll_confirm.text
    original_recovery_codes = enroll_confirm.json()["recoveryCodes"]
    assert len(original_recovery_codes) >= 2

    status_after_enroll = await async_client.get("/api/v1/auth/mfa/totp")
    assert status_after_enroll.status_code == 200, status_after_enroll.text
    enrolled_payload = status_after_enroll.json()
    assert enrolled_payload["enabled"] is True
    assert enrolled_payload["enrolledAt"]
    assert enrolled_payload["recoveryCodesRemaining"] == len(original_recovery_codes)
    assert enrolled_payload["onboardingRecommended"] is False
    assert enrolled_payload["onboardingRequired"] is False
    assert enrolled_payload["skipAllowed"] is False

    regenerate = await async_client.post(
        "/api/v1/auth/mfa/totp/recovery/regenerate",
        json={"code": totp_now(secret)},
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert regenerate.status_code == 200, regenerate.text
    regenerated_codes = regenerate.json()["recoveryCodes"]
    assert regenerated_codes
    assert regenerated_codes != original_recovery_codes

    status_after_regenerate = await async_client.get("/api/v1/auth/mfa/totp")
    assert status_after_regenerate.status_code == 200, status_after_regenerate.text
    regenerated_payload = status_after_regenerate.json()
    assert regenerated_payload["enabled"] is True
    assert regenerated_payload["recoveryCodesRemaining"] == len(regenerated_codes)


async def test_mfa_recovery_regeneration_rejects_invalid_code(
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

    enroll_start = await async_client.post(
        "/api/v1/auth/mfa/totp/enroll/start",
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert enroll_start.status_code == 200, enroll_start.text
    otpauth_uri = enroll_start.json()["otpauthUri"]
    secret = parse_qs(urlparse(otpauth_uri).query)["secret"][0]

    enroll_confirm = await async_client.post(
        "/api/v1/auth/mfa/totp/enroll/confirm",
        json={"code": totp_now(secret)},
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert enroll_confirm.status_code == 200, enroll_confirm.text

    regenerate = await async_client.post(
        "/api/v1/auth/mfa/totp/recovery/regenerate",
        json={"code": "ZZZZ-ZZZZ"},
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert regenerate.status_code == 400, regenerate.text


async def test_password_change_requirement_blocks_routes_until_password_is_updated(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
) -> None:
    admin = seed_identity.admin

    admin_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": admin.password},
    )
    assert admin_login.status_code == 200, admin_login.text
    admin_csrf = async_client.cookies.get(settings.session_csrf_cookie_name)
    assert admin_csrf

    create_user = await async_client.post(
        "/api/v1/users",
        headers={"X-CSRF-Token": admin_csrf},
        json={
            "email": "forced-change@example.com",
            "displayName": "Forced Change",
            "passwordProfile": {
                "mode": "explicit",
                "password": "notsecret1!Ab",
                "forceChangeOnNextSignIn": True,
            },
        },
    )
    assert create_user.status_code == 201, create_user.text

    logout_admin = await async_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert logout_admin.status_code == 204, logout_admin.text

    login_forced_user = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "forced-change@example.com", "password": "notsecret1!Ab"},
    )
    assert login_forced_user.status_code == 200, login_forced_user.text
    login_payload = login_forced_user.json()
    assert login_payload["passwordChangeRequired"] is True

    user_csrf = async_client.cookies.get(settings.session_csrf_cookie_name)
    assert user_csrf

    bootstrap_allowed = await async_client.get("/api/v1/me/bootstrap")
    assert bootstrap_allowed.status_code == 200, bootstrap_allowed.text
    user_csrf = async_client.cookies.get(settings.session_csrf_cookie_name)
    assert user_csrf

    blocked = await async_client.get("/api/v1/me")
    assert blocked.status_code == 403, blocked.text
    blocked_payload = blocked.json()
    error_codes = {
        item.get("code")
        for item in blocked_payload.get("errors", [])
        if isinstance(item, dict)
    }
    assert "password_change_required" in error_codes

    bad_change = await async_client.post(
        "/api/v1/auth/password/change",
        headers={"X-CSRF-Token": user_csrf},
        json={
            "currentPassword": "wrong-password",
            "newPassword": "notsecret2!Ab",
        },
    )
    assert bad_change.status_code == 400, bad_change.text

    apply_change = await async_client.post(
        "/api/v1/auth/password/change",
        headers={"X-CSRF-Token": user_csrf},
        json={
            "currentPassword": "notsecret1!Ab",
            "newPassword": "notsecret2!Ab",
        },
    )
    assert apply_change.status_code == 204, apply_change.text

    allowed = await async_client.get("/api/v1/me")
    assert allowed.status_code == 200, allowed.text
