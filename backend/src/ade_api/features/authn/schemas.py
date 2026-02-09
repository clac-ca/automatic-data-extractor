"""Request/response schemas for ADE-owned authentication endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import EmailStr, Field, SecretStr

from ade_api.common.schema import BaseSchema


class AuthLoginRequest(BaseSchema):
    email: EmailStr
    password: SecretStr


class AuthLoginSuccess(BaseSchema):
    ok: bool = True
    mfa_required: bool = False
    mfa_setup_recommended: bool = Field(default=False, alias="mfaSetupRecommended")
    mfa_setup_required: bool = Field(default=False, alias="mfaSetupRequired")
    password_change_required: bool = Field(default=False, alias="passwordChangeRequired")


class AuthLoginMfaRequired(BaseSchema):
    ok: bool = True
    mfa_required: bool = True
    challenge_token: str = Field(..., alias="challengeToken")


class AuthPasswordForgotRequest(BaseSchema):
    email: EmailStr


class AuthPasswordResetRequest(BaseSchema):
    token: SecretStr
    new_password: SecretStr = Field(..., alias="newPassword")


class AuthPasswordChangeRequest(BaseSchema):
    current_password: SecretStr = Field(..., alias="currentPassword")
    new_password: SecretStr = Field(..., alias="newPassword")


class AuthMfaEnrollStartResponse(BaseSchema):
    otpauth_uri: str = Field(..., alias="otpauthUri")
    issuer: str
    account_name: str = Field(..., alias="accountName")


class AuthMfaEnrollConfirmRequest(BaseSchema):
    code: str = Field(min_length=6, max_length=8)


class AuthMfaEnrollConfirmResponse(BaseSchema):
    recovery_codes: list[str] = Field(..., alias="recoveryCodes")


class AuthMfaStatusResponse(BaseSchema):
    enabled: bool
    enrolled_at: datetime | None = Field(default=None, alias="enrolledAt")
    recovery_codes_remaining: int | None = Field(
        default=None,
        alias="recoveryCodesRemaining",
    )
    onboarding_recommended: bool = Field(
        default=False,
        alias="onboardingRecommended",
    )
    onboarding_required: bool = Field(
        default=False,
        alias="onboardingRequired",
    )
    skip_allowed: bool = Field(default=False, alias="skipAllowed")


class AuthMfaChallengeVerifyRequest(BaseSchema):
    challenge_token: str = Field(..., alias="challengeToken")
    code: str = Field(
        min_length=6,
        max_length=9,
        pattern=r"^(?:\d{6}|[A-Za-z0-9]{8}|[A-Za-z0-9]{4}-[A-Za-z0-9]{4})$",
    )


class AuthPolicyResponse(BaseSchema):
    mode: Literal["password_only", "idp_only", "password_and_idp"]
    password_reset_enabled: bool = Field(default=True, alias="passwordResetEnabled")
    password_mfa_required: bool = Field(default=False, alias="passwordMfaRequired")
    password_min_length: int = Field(default=12, alias="passwordMinLength")
    password_require_uppercase: bool = Field(default=False, alias="passwordRequireUppercase")
    password_require_lowercase: bool = Field(default=False, alias="passwordRequireLowercase")
    password_require_number: bool = Field(default=False, alias="passwordRequireNumber")
    password_require_symbol: bool = Field(default=False, alias="passwordRequireSymbol")
    password_lockout_max_attempts: int = Field(default=5, alias="passwordLockoutMaxAttempts")
    password_lockout_duration_seconds: int = Field(
        default=300, alias="passwordLockoutDurationSeconds"
    )
    idp_jit_provisioning_enabled: bool = Field(default=True, alias="idpJitProvisioningEnabled")


class AuthMfaRecoveryRegenerateRequest(BaseSchema):
    code: str = Field(
        min_length=6,
        max_length=9,
        pattern=r"^(?:\d{6}|[A-Za-z0-9]{8}|[A-Za-z0-9]{4}-[A-Za-z0-9]{4})$",
    )


__all__ = [
    "AuthLoginMfaRequired",
    "AuthLoginRequest",
    "AuthLoginSuccess",
    "AuthMfaChallengeVerifyRequest",
    "AuthMfaEnrollConfirmRequest",
    "AuthMfaEnrollConfirmResponse",
    "AuthMfaRecoveryRegenerateRequest",
    "AuthMfaStatusResponse",
    "AuthMfaEnrollStartResponse",
    "AuthPasswordForgotRequest",
    "AuthPasswordChangeRequest",
    "AuthPasswordResetRequest",
    "AuthPolicyResponse",
]
