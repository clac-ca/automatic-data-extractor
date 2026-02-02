"""SSO provider, identity, and auth-state models."""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint, false
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ade_api.common.time import utc_now
from ade_db import GUID, Base, UTCDateTime, UUIDPrimaryKeyMixin, TimestampMixin


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class SsoProviderType(str, enum.Enum):
    """Supported SSO provider types."""

    OIDC = "oidc"


class SsoProviderStatus(str, enum.Enum):
    """Lifecycle status for SSO providers."""

    ACTIVE = "active"
    DISABLED = "disabled"
    DELETED = "deleted"


class SsoProviderManagedBy(str, enum.Enum):
    """Source-of-truth marker for provider configuration."""

    DB = "db"
    ENV = "env"


class SsoProvider(TimestampMixin, Base):
    """OIDC provider configuration stored in the database."""

    __tablename__ = "sso_providers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[SsoProviderType] = mapped_column(
        SAEnum(
            SsoProviderType,
            name="sso_provider_type",
            native_enum=False,
            length=20,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=SsoProviderType.OIDC,
        server_default=SsoProviderType.OIDC.value,
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    issuer: Mapped[str] = mapped_column(String(512), nullable=False)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    client_secret_enc: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[SsoProviderStatus] = mapped_column(
        SAEnum(
            SsoProviderStatus,
            name="sso_provider_status",
            native_enum=False,
            length=20,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=SsoProviderStatus.DISABLED,
        server_default=SsoProviderStatus.DISABLED.value,
    )
    managed_by: Mapped[SsoProviderManagedBy] = mapped_column(
        SAEnum(
            SsoProviderManagedBy,
            name="sso_provider_managed_by",
            native_enum=False,
            length=20,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=SsoProviderManagedBy.DB,
        server_default=SsoProviderManagedBy.DB.value,
    )
    locked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    domains: Mapped[list[SsoProviderDomain]] = relationship(
        "SsoProviderDomain",
        back_populates="provider",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    identities: Mapped[list[SsoIdentity]] = relationship(
        "SsoIdentity",
        back_populates="provider",
        lazy="selectin",
    )
    auth_states: Mapped[list[SsoAuthState]] = relationship(
        "SsoAuthState",
        back_populates="provider",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_sso_providers_status", "status"),
        Index("ix_sso_providers_issuer", "issuer"),
    )


class SsoProviderDomain(Base):
    """Mapping of email domains to providers."""

    __tablename__ = "sso_provider_domains"

    provider_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("sso_providers.id", ondelete="NO ACTION"),
        primary_key=True,
    )
    domain: Mapped[str] = mapped_column(String(255), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
    )

    provider: Mapped[SsoProvider] = relationship("SsoProvider", back_populates="domains")

    __table_args__ = (
        Index("ix_sso_provider_domains_domain", "domain"),
        Index("ix_sso_provider_domains_provider", "provider_id"),
        UniqueConstraint("domain", name="uq_sso_provider_domains_domain"),
    )


class SsoIdentity(UUIDPrimaryKeyMixin, Base):
    """Link from external subject to an ADE user."""

    __tablename__ = "sso_identities"

    provider_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("sso_providers.id", ondelete="NO ACTION"),
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=False,
    )
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    email_verified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
    )

    provider: Mapped[SsoProvider] = relationship("SsoProvider", back_populates="identities")

    __table_args__ = (
        Index("ix_sso_identities_user", "user_id"),
        Index("ix_sso_identities_provider_subject", "provider_id", "subject"),
        UniqueConstraint("provider_id", "subject", name="uq_sso_identities_provider_subject"),
        UniqueConstraint("provider_id", "user_id", name="uq_sso_identities_provider_user"),
    )


class SsoAuthState(Base):
    """Server-side auth state for OIDC flows."""

    __tablename__ = "sso_auth_states"

    state: Mapped[str] = mapped_column(String(255), primary_key=True)
    provider_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("sso_providers.id", ondelete="NO ACTION"),
        nullable=False,
    )
    nonce: Mapped[str] = mapped_column(String(255), nullable=False)
    pkce_verifier: Mapped[str] = mapped_column(String(255), nullable=False)
    return_to: Mapped[str] = mapped_column(String(2048), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    provider: Mapped[SsoProvider] = relationship("SsoProvider", back_populates="auth_states")

    __table_args__ = (
        Index("ix_sso_auth_states_expires", "expires_at"),
        Index("ix_sso_auth_states_provider", "provider_id"),
    )


__all__ = [
    "SsoProvider",
    "SsoProviderDomain",
    "SsoProviderManagedBy",
    "SsoProviderStatus",
    "SsoProviderType",
    "SsoIdentity",
    "SsoAuthState",
]
