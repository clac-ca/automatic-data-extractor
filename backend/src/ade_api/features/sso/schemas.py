"""Request/response schemas for SSO provider management and public listings."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator

from ade_api.common.schema import BaseSchema
from ade_db.models import SsoProviderManagedBy, SsoProviderStatus, SsoProviderType

PROVIDER_ID_PATTERN = r"^[a-z0-9][a-z0-9-_]{2,63}$"


class SsoProviderAdminBase(BaseSchema):
    """Shared fields for provider create/update payloads."""

    type: SsoProviderType = Field(default=SsoProviderType.OIDC)
    label: str = Field(..., max_length=255)
    issuer: str
    client_id: str = Field(..., alias="clientId", max_length=255)
    status: SsoProviderStatus = Field(default=SsoProviderStatus.DISABLED)
    domains: list[str] = Field(default_factory=list)

    @field_validator("label")
    @classmethod
    def _clean_label(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Label must not be blank")
        return cleaned

    @field_validator("issuer")
    @classmethod
    def _clean_issuer(cls, value: str) -> str:
        cleaned = value.strip().rstrip("/")
        parsed = urlparse(cleaned)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Issuer must be an https URL")
        return parsed.geturl()

    @field_validator("client_id")
    @classmethod
    def _clean_client_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Client ID must not be blank")
        return cleaned


class SsoProviderCreate(SsoProviderAdminBase):
    """Payload to create a provider."""

    id: Annotated[str, Field(pattern=PROVIDER_ID_PATTERN)]
    client_secret: SecretStr = Field(..., alias="clientSecret")

    @field_validator("id")
    @classmethod
    def _clean_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Provider ID must not be blank")
        return cleaned

    @field_validator("client_secret")
    @classmethod
    def _clean_secret(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("Client secret must not be blank")
        return value


class SsoProviderUpdate(BaseSchema):
    """Payload to update a provider."""

    label: str | None = Field(default=None, max_length=255)
    issuer: str | None = None
    client_id: str | None = Field(default=None, alias="clientId", max_length=255)
    client_secret: SecretStr | None = Field(default=None, alias="clientSecret")
    status: SsoProviderStatus | None = None
    domains: list[str] | None = None

    @field_validator("label")
    @classmethod
    def _clean_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Label must not be blank")
        return cleaned

    @field_validator("issuer")
    @classmethod
    def _clean_issuer(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().rstrip("/")
        parsed = urlparse(cleaned)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Issuer must be an https URL")
        return parsed.geturl()

    @field_validator("client_id")
    @classmethod
    def _clean_client_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Client ID must not be blank")
        return cleaned

    @field_validator("client_secret")
    @classmethod
    def _clean_secret(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        if not value.get_secret_value().strip():
            raise ValueError("Client secret must not be blank")
        return value


class SsoProviderAdminOut(BaseSchema):
    """Provider details returned to administrators."""

    id: str
    type: SsoProviderType
    label: str
    issuer: str
    client_id: str = Field(..., alias="clientId")
    status: SsoProviderStatus
    domains: list[str]
    managed_by: SsoProviderManagedBy = Field(..., alias="managedBy")
    locked: bool
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")


class SsoProviderListResponse(BaseSchema):
    items: list[SsoProviderAdminOut]


class PublicSsoProvider(BaseSchema):
    """Provider summary returned to the login screen."""

    id: str
    label: str
    type: Literal["oidc"]
    start_url: str = Field(..., alias="startUrl")


class PublicSsoProviderListResponse(BaseSchema):
    providers: list[PublicSsoProvider]
    force_sso: bool = Field(default=False, alias="forceSso")


class SsoSettings(BaseSchema):
    enabled: bool = True
    enforce_sso: bool = Field(default=False, alias="enforceSso")
    allow_jit_provisioning: bool = Field(default=True, alias="allowJitProvisioning")


__all__ = [
    "PROVIDER_ID_PATTERN",
    "PublicSsoProvider",
    "PublicSsoProviderListResponse",
    "SsoProviderAdminOut",
    "SsoProviderCreate",
    "SsoProviderListResponse",
    "SsoProviderUpdate",
    "SsoSettings",
]
