from __future__ import annotations

import pytest
from pydantic import ValidationError

from ade_api.features.admin_settings.service import (
    DEFAULT_SAFE_MODE_DETAIL,
    RuntimeSettingsV2,
    resolve_runtime_settings_from_env_defaults,
)
from ade_api.settings import Settings


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "database_url": "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable",
        "blob_container": "ade-test",
        "blob_connection_string": "UseDevelopmentStorage=true",
        "secret_key": "test-secret-key-for-tests-please-change",
    }
    values.update(overrides)
    return Settings(**values)


def _clear_runtime_override_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_key in (
        "ADE_SAFE_MODE",
        "ADE_SAFE_MODE_DETAIL",
        "ADE_AUTH_MODE",
        "ADE_AUTH_PASSWORD_RESET_ENABLED",
        "ADE_AUTH_PASSWORD_MFA_REQUIRED",
        "ADE_AUTH_PASSWORD_MIN_LENGTH",
        "ADE_AUTH_PASSWORD_REQUIRE_UPPERCASE",
        "ADE_AUTH_PASSWORD_REQUIRE_LOWERCASE",
        "ADE_AUTH_PASSWORD_REQUIRE_NUMBER",
        "ADE_AUTH_PASSWORD_REQUIRE_SYMBOL",
        "ADE_AUTH_PASSWORD_LOCKOUT_MAX_ATTEMPTS",
        "ADE_AUTH_PASSWORD_LOCKOUT_DURATION_SECONDS",
        "ADE_AUTH_IDP_PROVISIONING_MODE",
        "ADE_AUTH_IDP_JIT_PROVISIONING_ENABLED",
    ):
        monkeypatch.delenv(env_key, raising=False)


def test_resolve_runtime_settings_from_env_defaults_uses_defaults(monkeypatch) -> None:
    _clear_runtime_override_env(monkeypatch)

    resolved = resolve_runtime_settings_from_env_defaults(_settings(safe_mode=False))

    assert resolved.safe_mode.enabled is False
    assert resolved.safe_mode.detail == DEFAULT_SAFE_MODE_DETAIL
    assert resolved.auth.mode == "password_only"
    assert resolved.auth.password.reset_enabled is True
    assert resolved.auth.password.mfa_required is False
    assert resolved.auth.password.complexity.min_length == 12
    assert resolved.auth.password.lockout.max_attempts == 5
    assert resolved.auth.password.lockout.duration_seconds == 300
    assert resolved.auth.identity_provider.provisioning_mode == "jit"


def test_resolve_runtime_settings_from_env_defaults_applies_env_overrides(monkeypatch) -> None:
    _clear_runtime_override_env(monkeypatch)
    monkeypatch.setenv("ADE_SAFE_MODE", "false")
    monkeypatch.setenv("ADE_SAFE_MODE_DETAIL", "  Maintenance window  ")
    monkeypatch.setenv("ADE_AUTH_MODE", "idp_only")
    monkeypatch.setenv("ADE_AUTH_PASSWORD_RESET_ENABLED", "false")
    monkeypatch.setenv("ADE_AUTH_PASSWORD_MFA_REQUIRED", "true")
    monkeypatch.setenv("ADE_AUTH_PASSWORD_MIN_LENGTH", "14")
    monkeypatch.setenv("ADE_AUTH_PASSWORD_REQUIRE_UPPERCASE", "true")
    monkeypatch.setenv("ADE_AUTH_PASSWORD_REQUIRE_LOWERCASE", "true")
    monkeypatch.setenv("ADE_AUTH_PASSWORD_REQUIRE_NUMBER", "true")
    monkeypatch.setenv("ADE_AUTH_PASSWORD_REQUIRE_SYMBOL", "true")
    monkeypatch.setenv("ADE_AUTH_PASSWORD_LOCKOUT_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("ADE_AUTH_PASSWORD_LOCKOUT_DURATION_SECONDS", "900")
    monkeypatch.setenv("ADE_AUTH_IDP_PROVISIONING_MODE", "scim")

    resolved = resolve_runtime_settings_from_env_defaults(_settings(safe_mode=True))

    assert resolved.safe_mode.enabled is False
    assert resolved.safe_mode.detail == "Maintenance window"
    assert resolved.auth.mode == "idp_only"
    assert resolved.auth.password.reset_enabled is False
    assert resolved.auth.password.mfa_required is True
    assert resolved.auth.password.complexity.min_length == 14
    assert resolved.auth.password.complexity.require_uppercase is True
    assert resolved.auth.password.complexity.require_lowercase is True
    assert resolved.auth.password.complexity.require_number is True
    assert resolved.auth.password.complexity.require_symbol is True
    assert resolved.auth.password.lockout.max_attempts == 3
    assert resolved.auth.password.lockout.duration_seconds == 900
    assert resolved.auth.identity_provider.provisioning_mode == "scim"


def test_resolve_runtime_settings_from_env_defaults_normalizes_blank_detail(monkeypatch) -> None:
    _clear_runtime_override_env(monkeypatch)
    monkeypatch.setenv("ADE_SAFE_MODE_DETAIL", "   ")

    resolved = resolve_runtime_settings_from_env_defaults(_settings())

    assert resolved.safe_mode.detail == DEFAULT_SAFE_MODE_DETAIL


def test_runtime_settings_model_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RuntimeSettingsV2.model_validate(
            {
                "safe_mode": {
                    "enabled": True,
                    "detail": "x",
                    "unexpected": "value",
                },
                "auth": {
                    "mode": "password_only",
                    "password": {
                        "reset_enabled": True,
                        "mfa_required": False,
                        "complexity": {"min_length": 12},
                        "lockout": {"max_attempts": 5, "duration_seconds": 300},
                    },
                    "identity_provider": {
                        "provisioning_mode": "jit",
                    },
                },
            }
        )
