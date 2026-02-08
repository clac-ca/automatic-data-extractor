"""Request/response schemas for ADE-owned authentication endpoints."""

from __future__ import annotations

from pydantic import EmailStr, Field, SecretStr

from ade_api.common.schema import BaseSchema


class AuthLoginRequest(BaseSchema):
    email: EmailStr
    password: SecretStr


class AuthLoginSuccess(BaseSchema):
    ok: bool = True
    mfa_required: bool = False


class AuthLoginMfaRequired(BaseSchema):
    ok: bool = True
    mfa_required: bool = True
    challenge_token: str = Field(..., alias="challengeToken")


class AuthPasswordForgotRequest(BaseSchema):
    email: EmailStr


class AuthPasswordResetRequest(BaseSchema):
    token: SecretStr
    new_password: SecretStr = Field(..., alias="newPassword")


class AuthMfaEnrollStartResponse(BaseSchema):
    otpauth_uri: str = Field(..., alias="otpauthUri")
    issuer: str
    account_name: str = Field(..., alias="accountName")


class AuthMfaEnrollConfirmRequest(BaseSchema):
    code: str = Field(min_length=6, max_length=8)


class AuthMfaEnrollConfirmResponse(BaseSchema):
    recovery_codes: list[str] = Field(..., alias="recoveryCodes")


class AuthMfaChallengeVerifyRequest(BaseSchema):
    challenge_token: str = Field(..., alias="challengeToken")
    code: str = Field(
        min_length=6,
        max_length=9,
        pattern=r"^(?:\d{6}|[A-Za-z0-9]{8}|[A-Za-z0-9]{4}-[A-Za-z0-9]{4})$",
    )


class AuthPolicyResponse(BaseSchema):
    external_enabled: bool = Field(default=False, alias="externalEnabled")
    enforce_sso: bool = Field(default=False, alias="enforceSso")
    allow_jit_provisioning: bool = Field(default=True, alias="allowJitProvisioning")


class AuthPolicyUpdateRequest(BaseSchema):
    external_enabled: bool = Field(alias="externalEnabled")
    enforce_sso: bool = Field(alias="enforceSso")
    allow_jit_provisioning: bool = Field(alias="allowJitProvisioning")


__all__ = [
    "AuthLoginMfaRequired",
    "AuthLoginRequest",
    "AuthLoginSuccess",
    "AuthMfaChallengeVerifyRequest",
    "AuthMfaEnrollConfirmRequest",
    "AuthMfaEnrollConfirmResponse",
    "AuthMfaEnrollStartResponse",
    "AuthPasswordForgotRequest",
    "AuthPasswordResetRequest",
    "AuthPolicyResponse",
    "AuthPolicyUpdateRequest",
]
