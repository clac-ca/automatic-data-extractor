"""Runtime settings resolver for admin-configurable settings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import status
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from pydantic_settings import BaseSettings
from sqlalchemy import select
from sqlalchemy.orm import Session

from ade_api.common.problem_details import ApiError, ProblemDetailsErrorItem
from ade_api.settings import Settings
from ade_db.models import ApplicationSetting, SsoProvider, SsoProviderStatus
from settings import ade_settings_config

from .repository import ApplicationSettingsRepository
from .schemas import (
    AdminSettingsPatchRequest,
    AdminSettingsReadResponse,
    AuthMode,
    RuntimeAuthMeta,
    RuntimeAuthValues,
    RuntimeIdentityProviderMeta,
    RuntimeIdentityProviderValues,
    RuntimePasswordComplexityMeta,
    RuntimePasswordComplexityValues,
    RuntimePasswordLockoutMeta,
    RuntimePasswordLockoutValues,
    RuntimePasswordMeta,
    RuntimePasswordValues,
    RuntimeSafeModeMeta,
    RuntimeSafeModeValues,
    RuntimeSettingFieldMeta,
    RuntimeSettingsMeta,
    RuntimeSettingsValues,
)

SUPPORTED_RUNTIME_SETTINGS_SCHEMA_VERSION = 2
DEFAULT_SAFE_MODE_DETAIL = (
    "ADE safe mode enabled; skipping engine execution until ADE_SAFE_MODE is disabled."
)

_FIELD_PATH = tuple[str, ...]

_FIELD_ENV_VARS: dict[_FIELD_PATH, str] = {
    ("safe_mode", "enabled"): "ADE_SAFE_MODE",
    ("safe_mode", "detail"): "ADE_SAFE_MODE_DETAIL",
    ("auth", "mode"): "ADE_AUTH_MODE",
    ("auth", "password", "reset_enabled"): "ADE_AUTH_PASSWORD_RESET_ENABLED",
    ("auth", "password", "mfa_required"): "ADE_AUTH_PASSWORD_MFA_REQUIRED",
    ("auth", "password", "complexity", "min_length"): "ADE_AUTH_PASSWORD_MIN_LENGTH",
    ("auth", "password", "complexity", "require_uppercase"): "ADE_AUTH_PASSWORD_REQUIRE_UPPERCASE",
    ("auth", "password", "complexity", "require_lowercase"): "ADE_AUTH_PASSWORD_REQUIRE_LOWERCASE",
    ("auth", "password", "complexity", "require_number"): "ADE_AUTH_PASSWORD_REQUIRE_NUMBER",
    ("auth", "password", "complexity", "require_symbol"): "ADE_AUTH_PASSWORD_REQUIRE_SYMBOL",
    ("auth", "password", "lockout", "max_attempts"): "ADE_AUTH_PASSWORD_LOCKOUT_MAX_ATTEMPTS",
    (
        "auth",
        "password",
        "lockout",
        "duration_seconds",
    ): "ADE_AUTH_PASSWORD_LOCKOUT_DURATION_SECONDS",
    (
        "auth",
        "identity_provider",
        "jit_provisioning_enabled",
    ): "ADE_AUTH_IDP_JIT_PROVISIONING_ENABLED",
}

_FIELD_API_PATHS: dict[_FIELD_PATH, str] = {
    ("safe_mode", "enabled"): "safeMode.enabled",
    ("safe_mode", "detail"): "safeMode.detail",
    ("auth", "mode"): "auth.mode",
    ("auth", "password", "reset_enabled"): "auth.password.resetEnabled",
    ("auth", "password", "mfa_required"): "auth.password.mfaRequired",
    ("auth", "password", "complexity", "min_length"): "auth.password.complexity.minLength",
    (
        "auth",
        "password",
        "complexity",
        "require_uppercase",
    ): "auth.password.complexity.requireUppercase",
    (
        "auth",
        "password",
        "complexity",
        "require_lowercase",
    ): "auth.password.complexity.requireLowercase",
    ("auth", "password", "complexity", "require_number"): "auth.password.complexity.requireNumber",
    ("auth", "password", "complexity", "require_symbol"): "auth.password.complexity.requireSymbol",
    ("auth", "password", "lockout", "max_attempts"): "auth.password.lockout.maxAttempts",
    ("auth", "password", "lockout", "duration_seconds"): "auth.password.lockout.durationSeconds",
    (
        "auth",
        "identity_provider",
        "jit_provisioning_enabled",
    ): "auth.identityProvider.jitProvisioningEnabled",
}


class SafeModeSettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    detail: str = DEFAULT_SAFE_MODE_DETAIL

    @field_validator("detail")
    @classmethod
    def _normalize_detail(cls, value: str) -> str:
        normalized = value.strip()
        return normalized or DEFAULT_SAFE_MODE_DETAIL


class PasswordComplexitySettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_length: int = Field(default=12, ge=8, le=128)
    require_uppercase: bool = False
    require_lowercase: bool = False
    require_number: bool = False
    require_symbol: bool = False


class PasswordLockoutSettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_attempts: int = Field(default=5, ge=1, le=20)
    duration_seconds: int = Field(default=300, ge=30, le=86_400)


class PasswordAuthSettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reset_enabled: bool = True
    mfa_required: bool = False
    complexity: PasswordComplexitySettingsModel = Field(
        default_factory=PasswordComplexitySettingsModel
    )
    lockout: PasswordLockoutSettingsModel = Field(default_factory=PasswordLockoutSettingsModel)


class IdentityProviderSettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jit_provisioning_enabled: bool = True


class AuthPolicySettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: AuthMode = "password_only"
    password: PasswordAuthSettingsModel = Field(default_factory=PasswordAuthSettingsModel)
    identity_provider: IdentityProviderSettingsModel = Field(
        default_factory=IdentityProviderSettingsModel
    )


class RuntimeSettingsV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    safe_mode: SafeModeSettingsModel = Field(default_factory=SafeModeSettingsModel)
    auth: AuthPolicySettingsModel = Field(default_factory=AuthPolicySettingsModel)


class RuntimeSettingsEnvOverrides(BaseSettings):
    """Optional env overrides for runtime settings fields."""

    model_config = ade_settings_config(enable_decoding=False, populate_by_name=True)

    safe_mode: bool | None = None
    safe_mode_detail: str | None = None
    auth_mode: AuthMode | None = None
    auth_password_reset_enabled: bool | None = None
    auth_password_mfa_required: bool | None = None
    auth_password_min_length: int | None = Field(default=None, ge=8, le=128)
    auth_password_require_uppercase: bool | None = None
    auth_password_require_lowercase: bool | None = None
    auth_password_require_number: bool | None = None
    auth_password_require_symbol: bool | None = None
    auth_password_lockout_max_attempts: int | None = Field(default=None, ge=1, le=20)
    auth_password_lockout_duration_seconds: int | None = Field(default=None, ge=30, le=86_400)
    auth_idp_jit_provisioning_enabled: bool | None = None

    @field_validator("safe_mode_detail")
    @classmethod
    def _normalize_safe_mode_detail(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or DEFAULT_SAFE_MODE_DETAIL


@dataclass(frozen=True, slots=True)
class ResolvedRuntimeSettings:
    schema_version: int
    revision: int
    values: RuntimeSettingsV2
    field_meta: dict[_FIELD_PATH, RuntimeSettingFieldMeta]
    updated_at: datetime
    updated_by: UUID | None


class RuntimeSettingsSchemaVersionError(RuntimeError):
    """Raised when the DB schema version does not match app support."""

    def __init__(self, *, expected: int, found: int) -> None:
        super().__init__(
            "Unsupported runtime settings schema version. "
            f"Expected {expected}, found {found}. "
            "Reset runtime settings data to the current schema."
        )
        self.expected = expected
        self.found = found


class RuntimeSettingsInvariantError(RuntimeError):
    """Raised when the runtime settings singleton row or payload is invalid."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class RuntimeSettingsService:
    """Read and mutate runtime settings with env-overrides and lock metadata."""

    def __init__(self, *, session: Session) -> None:
        self._session = session
        self._repo = ApplicationSettingsRepository(session)

    def assert_schema_supported(self) -> None:
        record = self._require_record()
        self._ensure_schema_supported(record.schema_version)
        self._validate_payload_shape(dict(record.data or {}))

    def resolve(self) -> ResolvedRuntimeSettings:
        record = self._require_record()
        return self._resolve_record(
            record_data=record.data,
            schema_version=record.schema_version,
            revision=record.revision,
            updated_at=record.updated_at,
            updated_by=record.updated_by,
        )

    def read(self) -> AdminSettingsReadResponse:
        return self._to_read_response(self.resolve())

    def get_effective_values(self) -> RuntimeSettingsV2:
        return self.resolve().values

    def update(
        self,
        *,
        payload: AdminSettingsPatchRequest,
        updated_by: UUID | None,
    ) -> AdminSettingsReadResponse:
        record = self._repo.get_for_update()
        if record is None:
            raise RuntimeSettingsInvariantError(
                "Missing application_settings singleton row. "
                "Run database migrations to initialize runtime settings."
            )

        self._ensure_schema_supported(record.schema_version)

        if int(record.revision) != int(payload.revision):
            raise ApiError(
                error_type="conflict",
                status_code=status.HTTP_409_CONFLICT,
                detail="Settings have changed since your last read. Refresh and retry.",
                errors=[
                    ProblemDetailsErrorItem(
                        message="Settings revision conflict.",
                        code="settings_revision_conflict",
                        path="revision",
                    )
                ],
            )

        current = self._resolve_record(
            record_data=record.data,
            schema_version=record.schema_version,
            revision=record.revision,
            updated_at=record.updated_at,
            updated_by=record.updated_by,
        )
        patch_payload = payload.changes.model_dump(exclude_none=True, by_alias=False)
        changed_paths = tuple(dict.fromkeys(_leaf_paths(patch_payload)))
        if not changed_paths:
            return self._to_read_response(current)

        locked = [path for path in changed_paths if current.field_meta[path].locked_by_env]
        if locked:
            raise ApiError(
                error_type="conflict",
                status_code=status.HTTP_409_CONFLICT,
                detail="One or more settings are managed by environment variables.",
                errors=[
                    ProblemDetailsErrorItem(
                        path=_FIELD_API_PATHS[path],
                        message=(f"{_FIELD_API_PATHS[path]} is locked by {_FIELD_ENV_VARS[path]}."),
                        code="setting_locked_by_env",
                    )
                    for path in locked
                ],
            )

        persisted_raw = dict(record.data or {})
        persisted_values = self._validate_payload_shape(persisted_raw)
        merged_payload = persisted_values.model_dump(mode="python")
        _deep_merge(merged_payload, patch_payload)
        validated = RuntimeSettingsV2.model_validate(merged_payload)
        self._validate_policy_constraints(validated)
        persisted_candidate = validated.model_dump(mode="python")

        if persisted_candidate == persisted_raw:
            return self._to_read_response(current)

        record.data = persisted_candidate
        record.revision = int(record.revision) + 1
        record.updated_by = updated_by
        self._session.flush()

        resolved = self._resolve_record(
            record_data=record.data,
            schema_version=record.schema_version,
            revision=record.revision,
            updated_at=record.updated_at,
            updated_by=record.updated_by,
        )
        return self._to_read_response(resolved)

    def _resolve_record(
        self,
        *,
        record_data: dict[str, Any] | None,
        schema_version: int,
        revision: int,
        updated_at: datetime | None,
        updated_by: UUID | None,
    ) -> ResolvedRuntimeSettings:
        self._ensure_schema_supported(schema_version)

        persisted_raw = dict(record_data or {})
        persisted = self._validate_payload_shape(persisted_raw)
        defaults = RuntimeSettingsV2()

        values = persisted.model_copy(deep=True)

        env = RuntimeSettingsEnvOverrides()
        env_map: dict[_FIELD_PATH, Any] = {
            ("safe_mode", "enabled"): env.safe_mode,
            ("safe_mode", "detail"): env.safe_mode_detail,
            ("auth", "mode"): env.auth_mode,
            ("auth", "password", "reset_enabled"): env.auth_password_reset_enabled,
            ("auth", "password", "mfa_required"): env.auth_password_mfa_required,
            ("auth", "password", "complexity", "min_length"): env.auth_password_min_length,
            (
                "auth",
                "password",
                "complexity",
                "require_uppercase",
            ): env.auth_password_require_uppercase,
            (
                "auth",
                "password",
                "complexity",
                "require_lowercase",
            ): env.auth_password_require_lowercase,
            ("auth", "password", "complexity", "require_number"): env.auth_password_require_number,
            ("auth", "password", "complexity", "require_symbol"): env.auth_password_require_symbol,
            ("auth", "password", "lockout", "max_attempts"): env.auth_password_lockout_max_attempts,
            (
                "auth",
                "password",
                "lockout",
                "duration_seconds",
            ): env.auth_password_lockout_duration_seconds,
            (
                "auth",
                "identity_provider",
                "jit_provisioning_enabled",
            ): env.auth_idp_jit_provisioning_enabled,
        }

        field_meta: dict[_FIELD_PATH, RuntimeSettingFieldMeta] = {}

        for path, env_var in _FIELD_ENV_VARS.items():
            env_value = env_map[path]
            if env_value is not None:
                _set_path(values, path, env_value)
                source = "env"
                locked = True
            elif _has_path(persisted_raw, path):
                source = "db"
                locked = False
            else:
                _set_path(values, path, _get_path(defaults, path))
                source = "default"
                locked = False

            field_meta[path] = RuntimeSettingFieldMeta(
                source=source,
                locked_by_env=locked,
                env_var=env_var,
                restart_required=locked,
            )

        timestamp = updated_at or datetime.now(tz=UTC)
        return ResolvedRuntimeSettings(
            schema_version=schema_version,
            revision=revision,
            values=values,
            field_meta=field_meta,
            updated_at=timestamp,
            updated_by=updated_by,
        )

    def _to_read_response(self, resolved: ResolvedRuntimeSettings) -> AdminSettingsReadResponse:
        values = RuntimeSettingsValues(
            safe_mode=RuntimeSafeModeValues(
                enabled=resolved.values.safe_mode.enabled,
                detail=resolved.values.safe_mode.detail,
            ),
            auth=RuntimeAuthValues(
                mode=resolved.values.auth.mode,
                password=RuntimePasswordValues(
                    reset_enabled=resolved.values.auth.password.reset_enabled,
                    mfa_required=resolved.values.auth.password.mfa_required,
                    complexity=RuntimePasswordComplexityValues(
                        min_length=resolved.values.auth.password.complexity.min_length,
                        require_uppercase=resolved.values.auth.password.complexity.require_uppercase,
                        require_lowercase=resolved.values.auth.password.complexity.require_lowercase,
                        require_number=resolved.values.auth.password.complexity.require_number,
                        require_symbol=resolved.values.auth.password.complexity.require_symbol,
                    ),
                    lockout=RuntimePasswordLockoutValues(
                        max_attempts=resolved.values.auth.password.lockout.max_attempts,
                        duration_seconds=resolved.values.auth.password.lockout.duration_seconds,
                    ),
                ),
                identity_provider=RuntimeIdentityProviderValues(
                    jit_provisioning_enabled=resolved.values.auth.identity_provider.jit_provisioning_enabled,
                ),
            ),
        )
        meta = RuntimeSettingsMeta(
            safe_mode=RuntimeSafeModeMeta(
                enabled=resolved.field_meta[("safe_mode", "enabled")],
                detail=resolved.field_meta[("safe_mode", "detail")],
            ),
            auth=RuntimeAuthMeta(
                mode=resolved.field_meta[("auth", "mode")],
                password=RuntimePasswordMeta(
                    reset_enabled=resolved.field_meta[("auth", "password", "reset_enabled")],
                    mfa_required=resolved.field_meta[("auth", "password", "mfa_required")],
                    complexity=RuntimePasswordComplexityMeta(
                        min_length=resolved.field_meta[
                            ("auth", "password", "complexity", "min_length")
                        ],
                        require_uppercase=resolved.field_meta[
                            ("auth", "password", "complexity", "require_uppercase")
                        ],
                        require_lowercase=resolved.field_meta[
                            ("auth", "password", "complexity", "require_lowercase")
                        ],
                        require_number=resolved.field_meta[
                            ("auth", "password", "complexity", "require_number")
                        ],
                        require_symbol=resolved.field_meta[
                            ("auth", "password", "complexity", "require_symbol")
                        ],
                    ),
                    lockout=RuntimePasswordLockoutMeta(
                        max_attempts=resolved.field_meta[
                            ("auth", "password", "lockout", "max_attempts")
                        ],
                        duration_seconds=resolved.field_meta[
                            ("auth", "password", "lockout", "duration_seconds")
                        ],
                    ),
                ),
                identity_provider=RuntimeIdentityProviderMeta(
                    jit_provisioning_enabled=resolved.field_meta[
                        ("auth", "identity_provider", "jit_provisioning_enabled")
                    ],
                ),
            ),
        )
        return AdminSettingsReadResponse(
            schema_version=resolved.schema_version,
            revision=resolved.revision,
            values=values,
            meta=meta,
            updated_at=resolved.updated_at,
            updated_by=resolved.updated_by,
        )

    @staticmethod
    def _ensure_schema_supported(found: int) -> None:
        expected = SUPPORTED_RUNTIME_SETTINGS_SCHEMA_VERSION
        if int(found) != int(expected):
            raise RuntimeSettingsSchemaVersionError(expected=expected, found=int(found))

    def _require_record(self) -> ApplicationSetting:
        record = self._repo.get()
        if record is None:
            raise RuntimeSettingsInvariantError(
                "Missing application_settings singleton row. "
                "Run database migrations to initialize runtime settings."
            )
        return record

    @staticmethod
    def _validate_payload_shape(payload: dict[str, Any]) -> RuntimeSettingsV2:
        try:
            return RuntimeSettingsV2.model_validate(payload)
        except ValidationError as exc:
            raise RuntimeSettingsInvariantError(
                "application_settings.data does not match RuntimeSettingsV2. "
                "Reset runtime settings data to the current schema."
            ) from exc

    def _validate_policy_constraints(self, values: RuntimeSettingsV2) -> None:
        mode = values.auth.mode
        if mode != "idp_only":
            return
        provider = (
            self._session
            .execute(
                select(SsoProvider)
                .where(SsoProvider.status == SsoProviderStatus.ACTIVE)
                .order_by(SsoProvider.updated_at.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        if provider is None:
            raise ApiError(
                error_type="validation_error",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "An active identity provider is required when authentication "
                    "mode includes identity provider sign-in."
                ),
                errors=[
                    ProblemDetailsErrorItem(
                        path="auth.mode",
                        message=(
                            "Add and activate at least one provider before using this "
                            "authentication mode."
                        ),
                        code="active_provider_required",
                    )
                ],
            )


def resolve_runtime_settings_from_env_defaults(settings: Settings) -> RuntimeSettingsV2:
    """Resolve runtime settings from defaults + env overrides without DB access."""

    values = RuntimeSettingsV2(
        safe_mode=SafeModeSettingsModel(enabled=bool(settings.safe_mode)),
        auth=AuthPolicySettingsModel(
            mode=settings.auth_mode,
            password=PasswordAuthSettingsModel(
                reset_enabled=bool(settings.auth_password_reset_enabled),
                mfa_required=bool(settings.auth_password_mfa_required),
                complexity=PasswordComplexitySettingsModel(
                    min_length=int(settings.auth_password_min_length),
                    require_uppercase=bool(settings.auth_password_require_uppercase),
                    require_lowercase=bool(settings.auth_password_require_lowercase),
                    require_number=bool(settings.auth_password_require_number),
                    require_symbol=bool(settings.auth_password_require_symbol),
                ),
                lockout=PasswordLockoutSettingsModel(
                    max_attempts=int(settings.auth_password_lockout_max_attempts),
                    duration_seconds=int(settings.auth_password_lockout_duration_seconds),
                ),
            ),
            identity_provider=IdentityProviderSettingsModel(
                jit_provisioning_enabled=bool(settings.auth_idp_jit_provisioning_enabled),
            ),
        ),
    )

    env = RuntimeSettingsEnvOverrides()
    env_map: dict[_FIELD_PATH, Any] = {
        ("safe_mode", "enabled"): env.safe_mode,
        ("safe_mode", "detail"): env.safe_mode_detail,
        ("auth", "mode"): env.auth_mode,
        ("auth", "password", "reset_enabled"): env.auth_password_reset_enabled,
        ("auth", "password", "mfa_required"): env.auth_password_mfa_required,
        ("auth", "password", "complexity", "min_length"): env.auth_password_min_length,
        (
            "auth",
            "password",
            "complexity",
            "require_uppercase",
        ): env.auth_password_require_uppercase,
        (
            "auth",
            "password",
            "complexity",
            "require_lowercase",
        ): env.auth_password_require_lowercase,
        ("auth", "password", "complexity", "require_number"): env.auth_password_require_number,
        ("auth", "password", "complexity", "require_symbol"): env.auth_password_require_symbol,
        ("auth", "password", "lockout", "max_attempts"): env.auth_password_lockout_max_attempts,
        (
            "auth",
            "password",
            "lockout",
            "duration_seconds",
        ): env.auth_password_lockout_duration_seconds,
        (
            "auth",
            "identity_provider",
            "jit_provisioning_enabled",
        ): env.auth_idp_jit_provisioning_enabled,
    }
    for path, env_value in env_map.items():
        if env_value is not None:
            _set_path(values, path, env_value)

    return values


def _has_path(payload: dict[str, Any], path: _FIELD_PATH) -> bool:
    cursor: Any = payload
    for segment in path:
        if not isinstance(cursor, dict) or segment not in cursor:
            return False
        cursor = cursor[segment]
    return True


def _get_path(model: BaseModel, path: _FIELD_PATH) -> Any:
    cursor: Any = model
    for segment in path:
        cursor = getattr(cursor, segment)
    return cursor


def _set_path(model: BaseModel, path: _FIELD_PATH, value: Any) -> None:
    cursor: Any = model
    for segment in path[:-1]:
        cursor = getattr(cursor, segment)
    setattr(cursor, path[-1], value)


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
            continue
        base[key] = value


def _leaf_paths(payload: dict[str, Any], prefix: tuple[str, ...] = ()) -> list[_FIELD_PATH]:
    paths: list[_FIELD_PATH] = []
    for key, value in payload.items():
        next_prefix = (*prefix, key)
        if isinstance(value, dict):
            paths.extend(_leaf_paths(value, prefix=next_prefix))
            continue
        paths.append(next_prefix)
    return paths


__all__ = [
    "DEFAULT_SAFE_MODE_DETAIL",
    "RuntimeSettingsInvariantError",
    "RuntimeSettingsSchemaVersionError",
    "RuntimeSettingsService",
    "RuntimeSettingsV2",
    "SUPPORTED_RUNTIME_SETTINGS_SCHEMA_VERSION",
    "resolve_runtime_settings_from_env_defaults",
]
