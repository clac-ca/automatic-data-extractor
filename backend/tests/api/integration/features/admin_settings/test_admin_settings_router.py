from __future__ import annotations

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.orm import Session

from ade_api.features.admin_settings.service import DEFAULT_SAFE_MODE_DETAIL
from ade_db.models import (
    ApplicationSetting,
    SsoAuthState,
    SsoProvider,
    SsoProviderDomain,
)
from tests.api.utils import login

pytestmark = pytest.mark.asyncio


def _error_codes(payload: dict[str, object]) -> set[str]:
    errors = payload.get("errors")
    if not isinstance(errors, list):
        return set()
    return {
        item.get("code")
        for item in errors
        if isinstance(item, dict) and isinstance(item.get("code"), str)
    }


@pytest.fixture(autouse=True)
def _reset_runtime_state(db_session: Session) -> None:
    db_session.execute(sa.delete(SsoAuthState))
    db_session.execute(sa.delete(SsoProviderDomain))
    db_session.execute(sa.delete(SsoProvider))

    record = db_session.get(ApplicationSetting, 1)
    if record is not None:
        record.schema_version = 2
        record.data = {}
        record.revision = 1
        record.updated_by = None
    db_session.flush()


async def test_read_admin_settings_defaults(async_client: AsyncClient, seed_identity) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.get(
        "/api/v1/admin/settings",
        headers={"X-API-Key": token},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["schemaVersion"] == 2
    assert payload["revision"] >= 1
    assert payload["values"]["safeMode"] == {
        "enabled": False,
        "detail": DEFAULT_SAFE_MODE_DETAIL,
    }
    assert payload["values"]["auth"]["mode"] == "password_only"
    assert payload["values"]["auth"]["password"]["resetEnabled"] is True
    assert payload["values"]["auth"]["identityProvider"]["provisioningMode"] == "jit"
    assert payload["meta"]["auth"]["mode"]["restartRequired"] is False


async def test_patch_admin_settings_and_revision_conflict(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)
    headers = {"X-API-Key": token}

    initial = await async_client.get("/api/v1/admin/settings", headers=headers)
    assert initial.status_code == 200, initial.text
    revision = initial.json()["revision"]

    updated = await async_client.patch(
        "/api/v1/admin/settings",
        json={
            "revision": revision,
            "changes": {
                "safeMode": {
                    "enabled": True,
                    "detail": "Maintenance window",
                }
            },
        },
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["values"]["safeMode"]["enabled"] is True

    stale = await async_client.patch(
        "/api/v1/admin/settings",
        json={
            "revision": revision,
            "changes": {
                "safeMode": {
                    "enabled": False,
                }
            },
        },
        headers=headers,
    )
    assert stale.status_code == 409, stale.text
    assert "settings_revision_conflict" in _error_codes(stale.json())


async def test_patch_noop_changes_do_not_advance_revision(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)
    headers = {"X-API-Key": token}

    initial = await async_client.get("/api/v1/admin/settings", headers=headers)
    assert initial.status_code == 200, initial.text
    revision = initial.json()["revision"]

    updated = await async_client.patch(
        "/api/v1/admin/settings",
        json={
            "revision": revision,
            "changes": {
                "safeMode": {},
            },
        },
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["revision"] == revision


async def test_patch_rejects_env_locked_field(
    async_client: AsyncClient,
    seed_identity,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ADE_SAFE_MODE", "true")

    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)
    headers = {"X-API-Key": token}

    current = await async_client.get("/api/v1/admin/settings", headers=headers)
    assert current.status_code == 200, current.text
    payload = current.json()
    assert payload["meta"]["safeMode"]["enabled"]["lockedByEnv"] is True
    assert payload["meta"]["safeMode"]["enabled"]["restartRequired"] is True

    blocked = await async_client.patch(
        "/api/v1/admin/settings",
        json={
            "revision": payload["revision"],
            "changes": {
                "safeMode": {
                    "enabled": False,
                }
            },
        },
        headers=headers,
    )
    assert blocked.status_code == 409, blocked.text
    assert "setting_locked_by_env" in _error_codes(blocked.json())


async def test_patch_rejects_idp_only_without_active_provider(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)
    headers = {"X-API-Key": token}

    current = await async_client.get("/api/v1/admin/settings", headers=headers)
    assert current.status_code == 200, current.text
    revision = current.json()["revision"]

    response = await async_client.patch(
        "/api/v1/admin/settings",
        json={
            "revision": revision,
            "changes": {
                "auth": {
                    "mode": "idp_only",
                }
            },
        },
        headers=headers,
    )
    assert response.status_code == 422, response.text
    assert "active_provider_required" in _error_codes(response.json())


async def test_patch_allows_idp_only_with_active_provider(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)
    headers = {"X-API-Key": token}

    create_provider = await async_client.post(
        "/api/v1/admin/sso/providers",
        headers=headers,
        json={
            "id": "okta-primary",
            "label": "Okta",
            "issuer": "https://issuer.example.com",
            "clientId": "demo-client",
            "clientSecret": "notsecret-client",
            "status": "active",
            "domains": ["example.com"],
        },
    )
    assert create_provider.status_code == 201, create_provider.text

    current = await async_client.get("/api/v1/admin/settings", headers=headers)
    assert current.status_code == 200, current.text
    revision = current.json()["revision"]

    response = await async_client.patch(
        "/api/v1/admin/settings",
        json={
            "revision": revision,
            "changes": {
                "auth": {
                    "mode": "idp_only",
                    "identityProvider": {
                        "provisioningMode": "disabled",
                    },
                }
            },
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["values"]["auth"]["mode"] == "idp_only"
    assert payload["values"]["auth"]["identityProvider"]["provisioningMode"] == "disabled"


async def test_patch_rejects_locked_and_unlocked_changes_atomically(
    async_client: AsyncClient,
    seed_identity,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ADE_SAFE_MODE", "true")

    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)
    headers = {"X-API-Key": token}

    current = await async_client.get("/api/v1/admin/settings", headers=headers)
    assert current.status_code == 200, current.text
    before = current.json()

    blocked = await async_client.patch(
        "/api/v1/admin/settings",
        headers=headers,
        json={
            "revision": before["revision"],
            "changes": {
                "safeMode": {"enabled": False},
                "auth": {"mode": "password_and_idp"},
            },
        },
    )
    assert blocked.status_code == 409, blocked.text
    assert "setting_locked_by_env" in _error_codes(blocked.json())

    after = await async_client.get("/api/v1/admin/settings", headers=headers)
    assert after.status_code == 200, after.text
    payload = after.json()
    assert payload["revision"] == before["revision"]
    assert payload["values"]["auth"]["mode"] == before["values"]["auth"]["mode"]
    assert payload["values"]["safeMode"]["enabled"] is True


async def test_patch_blank_safe_mode_detail_normalizes_to_default(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)
    headers = {"X-API-Key": token}

    current = await async_client.get("/api/v1/admin/settings", headers=headers)
    assert current.status_code == 200, current.text
    revision = current.json()["revision"]

    response = await async_client.patch(
        "/api/v1/admin/settings",
        headers=headers,
        json={
            "revision": revision,
            "changes": {
                "safeMode": {
                    "enabled": True,
                    "detail": "   ",
                }
            },
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["values"]["safeMode"]["enabled"] is True
    assert payload["values"]["safeMode"]["detail"] == DEFAULT_SAFE_MODE_DETAIL


async def test_patch_updates_password_policy_fields(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)
    headers = {"X-API-Key": token}

    current = await async_client.get("/api/v1/admin/settings", headers=headers)
    assert current.status_code == 200, current.text
    revision = current.json()["revision"]

    response = await async_client.patch(
        "/api/v1/admin/settings",
        headers=headers,
        json={
            "revision": revision,
            "changes": {
                "auth": {
                    "password": {
                        "resetEnabled": False,
                        "mfaRequired": True,
                        "complexity": {
                            "minLength": 16,
                            "requireUppercase": True,
                            "requireLowercase": True,
                            "requireNumber": True,
                            "requireSymbol": True,
                        },
                        "lockout": {
                            "maxAttempts": 4,
                            "durationSeconds": 1200,
                        },
                    }
                }
            },
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["values"]["auth"]["password"]["resetEnabled"] is False
    assert payload["values"]["auth"]["password"]["mfaRequired"] is True
    assert payload["values"]["auth"]["password"]["complexity"]["minLength"] == 16
    assert payload["values"]["auth"]["password"]["lockout"]["maxAttempts"] == 4


async def test_patch_rejects_env_locked_password_reset_setting(
    async_client: AsyncClient,
    seed_identity,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ADE_AUTH_PASSWORD_RESET_ENABLED", "true")

    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)
    headers = {"X-API-Key": token}

    current = await async_client.get("/api/v1/admin/settings", headers=headers)
    assert current.status_code == 200, current.text
    payload = current.json()
    assert payload["meta"]["auth"]["password"]["resetEnabled"]["lockedByEnv"] is True

    blocked = await async_client.patch(
        "/api/v1/admin/settings",
        headers=headers,
        json={
            "revision": payload["revision"],
            "changes": {
                "auth": {
                    "password": {
                        "resetEnabled": False,
                    }
                }
            },
        },
    )
    assert blocked.status_code == 409, blocked.text
    assert "setting_locked_by_env" in _error_codes(blocked.json())


async def test_read_admin_settings_normalizes_legacy_jit_flag(
    async_client: AsyncClient,
    seed_identity,
    db_session: Session,
) -> None:
    record = db_session.get(ApplicationSetting, 1)
    assert record is not None
    record.data = {
        "safe_mode": {
            "enabled": False,
            "detail": DEFAULT_SAFE_MODE_DETAIL,
        },
        "auth": {
            "mode": "password_and_idp",
            "password": {
                "reset_enabled": True,
                "mfa_required": False,
                "complexity": {
                    "min_length": 12,
                    "require_uppercase": False,
                    "require_lowercase": False,
                    "require_number": False,
                    "require_symbol": False,
                },
                "lockout": {
                    "max_attempts": 5,
                    "duration_seconds": 300,
                },
            },
            "identity_provider": {
                "jit_provisioning_enabled": False,
            },
        },
    }
    db_session.flush()

    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.get(
        "/api/v1/admin/settings",
        headers={"X-API-Key": token},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["values"]["auth"]["identityProvider"]["provisioningMode"] == "disabled"
