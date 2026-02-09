"""API schemas for unified admin runtime settings."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from ade_api.common.schema import BaseSchema

AuthMode = Literal["password_only", "idp_only", "password_and_idp"]


class RuntimeSafeModeValues(BaseSchema):
    enabled: bool
    detail: str


class RuntimePasswordComplexityValues(BaseSchema):
    min_length: int = Field(alias="minLength")
    require_uppercase: bool = Field(alias="requireUppercase")
    require_lowercase: bool = Field(alias="requireLowercase")
    require_number: bool = Field(alias="requireNumber")
    require_symbol: bool = Field(alias="requireSymbol")


class RuntimePasswordLockoutValues(BaseSchema):
    max_attempts: int = Field(alias="maxAttempts")
    duration_seconds: int = Field(alias="durationSeconds")


class RuntimePasswordValues(BaseSchema):
    reset_enabled: bool = Field(alias="resetEnabled")
    mfa_required: bool = Field(alias="mfaRequired")
    complexity: RuntimePasswordComplexityValues
    lockout: RuntimePasswordLockoutValues


class RuntimeIdentityProviderValues(BaseSchema):
    jit_provisioning_enabled: bool = Field(alias="jitProvisioningEnabled")


class RuntimeAuthValues(BaseSchema):
    mode: AuthMode
    password: RuntimePasswordValues
    identity_provider: RuntimeIdentityProviderValues = Field(alias="identityProvider")


class RuntimeSettingsValues(BaseSchema):
    safe_mode: RuntimeSafeModeValues = Field(alias="safeMode")
    auth: RuntimeAuthValues


class RuntimeSettingFieldMeta(BaseSchema):
    source: Literal["env", "db", "default"]
    locked_by_env: bool = Field(alias="lockedByEnv")
    env_var: str | None = Field(default=None, alias="envVar")
    restart_required: bool = Field(default=False, alias="restartRequired")


class RuntimeSafeModeMeta(BaseSchema):
    enabled: RuntimeSettingFieldMeta
    detail: RuntimeSettingFieldMeta


class RuntimePasswordComplexityMeta(BaseSchema):
    min_length: RuntimeSettingFieldMeta = Field(alias="minLength")
    require_uppercase: RuntimeSettingFieldMeta = Field(alias="requireUppercase")
    require_lowercase: RuntimeSettingFieldMeta = Field(alias="requireLowercase")
    require_number: RuntimeSettingFieldMeta = Field(alias="requireNumber")
    require_symbol: RuntimeSettingFieldMeta = Field(alias="requireSymbol")


class RuntimePasswordLockoutMeta(BaseSchema):
    max_attempts: RuntimeSettingFieldMeta = Field(alias="maxAttempts")
    duration_seconds: RuntimeSettingFieldMeta = Field(alias="durationSeconds")


class RuntimePasswordMeta(BaseSchema):
    reset_enabled: RuntimeSettingFieldMeta = Field(alias="resetEnabled")
    mfa_required: RuntimeSettingFieldMeta = Field(alias="mfaRequired")
    complexity: RuntimePasswordComplexityMeta
    lockout: RuntimePasswordLockoutMeta


class RuntimeIdentityProviderMeta(BaseSchema):
    jit_provisioning_enabled: RuntimeSettingFieldMeta = Field(alias="jitProvisioningEnabled")


class RuntimeAuthMeta(BaseSchema):
    mode: RuntimeSettingFieldMeta
    password: RuntimePasswordMeta
    identity_provider: RuntimeIdentityProviderMeta = Field(alias="identityProvider")


class RuntimeSettingsMeta(BaseSchema):
    safe_mode: RuntimeSafeModeMeta = Field(alias="safeMode")
    auth: RuntimeAuthMeta


class AdminSettingsReadResponse(BaseSchema):
    schema_version: int = Field(alias="schemaVersion")
    revision: int
    values: RuntimeSettingsValues
    meta: RuntimeSettingsMeta
    updated_at: datetime = Field(alias="updatedAt")
    updated_by: UUID | None = Field(default=None, alias="updatedBy")


class RuntimeSafeModePatch(BaseSchema):
    enabled: bool | None = None
    detail: str | None = None


class RuntimePasswordComplexityPatch(BaseSchema):
    min_length: int | None = Field(default=None, alias="minLength")
    require_uppercase: bool | None = Field(default=None, alias="requireUppercase")
    require_lowercase: bool | None = Field(default=None, alias="requireLowercase")
    require_number: bool | None = Field(default=None, alias="requireNumber")
    require_symbol: bool | None = Field(default=None, alias="requireSymbol")


class RuntimePasswordLockoutPatch(BaseSchema):
    max_attempts: int | None = Field(default=None, alias="maxAttempts")
    duration_seconds: int | None = Field(default=None, alias="durationSeconds")


class RuntimePasswordPatch(BaseSchema):
    reset_enabled: bool | None = Field(default=None, alias="resetEnabled")
    mfa_required: bool | None = Field(default=None, alias="mfaRequired")
    complexity: RuntimePasswordComplexityPatch | None = None
    lockout: RuntimePasswordLockoutPatch | None = None


class RuntimeIdentityProviderPatch(BaseSchema):
    jit_provisioning_enabled: bool | None = Field(default=None, alias="jitProvisioningEnabled")


class RuntimeAuthPatch(BaseSchema):
    mode: AuthMode | None = None
    password: RuntimePasswordPatch | None = None
    identity_provider: RuntimeIdentityProviderPatch | None = Field(
        default=None,
        alias="identityProvider",
    )


class RuntimeSettingsPatch(BaseSchema):
    safe_mode: RuntimeSafeModePatch | None = Field(default=None, alias="safeMode")
    auth: RuntimeAuthPatch | None = None


class AdminSettingsPatchRequest(BaseSchema):
    revision: int = Field(ge=1)
    changes: RuntimeSettingsPatch


__all__ = [
    "AdminSettingsPatchRequest",
    "AdminSettingsReadResponse",
    "AuthMode",
    "RuntimeAuthMeta",
    "RuntimeAuthPatch",
    "RuntimeAuthValues",
    "RuntimeIdentityProviderMeta",
    "RuntimeIdentityProviderPatch",
    "RuntimeIdentityProviderValues",
    "RuntimePasswordComplexityMeta",
    "RuntimePasswordComplexityPatch",
    "RuntimePasswordComplexityValues",
    "RuntimePasswordLockoutMeta",
    "RuntimePasswordLockoutPatch",
    "RuntimePasswordLockoutValues",
    "RuntimePasswordMeta",
    "RuntimePasswordPatch",
    "RuntimePasswordValues",
    "RuntimeSafeModeMeta",
    "RuntimeSafeModePatch",
    "RuntimeSafeModeValues",
    "RuntimeSettingFieldMeta",
    "RuntimeSettingsMeta",
    "RuntimeSettingsPatch",
    "RuntimeSettingsValues",
]
