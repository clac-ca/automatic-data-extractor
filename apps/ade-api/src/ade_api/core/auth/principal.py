"""Lightweight identity representation produced by the auth pipeline."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from uuid import UUID


class PrincipalType(str, enum.Enum):
    """Category for the authenticated actor."""

    USER = "user"
    SERVICE_ACCOUNT = "service_account"


class AuthVia(str, enum.Enum):
    """Transport used to authenticate the request."""

    SESSION = "session"
    API_KEY = "api_key"
    DEV = "dev"


@dataclass(slots=True)
class AuthenticatedPrincipal:
    """Identity information available to downstream handlers."""

    user_id: UUID
    principal_type: PrincipalType
    auth_via: AuthVia
    api_key_id: UUID | None = None

