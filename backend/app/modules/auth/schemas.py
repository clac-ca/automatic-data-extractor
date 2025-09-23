"""Schemas exposed by the auth module."""

from __future__ import annotations

from ...core.schema import BaseSchema


class TokenResponse(BaseSchema):
    """Issued bearer token."""

    access_token: str
    token_type: str = "bearer"


__all__ = ["TokenResponse"]
