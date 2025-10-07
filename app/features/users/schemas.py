"""Pydantic schemas for user payloads."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.core.schema import BaseSchema

from .models import UserRole


class UserProfile(BaseSchema):
    """Minimal view of the authenticated user."""

    user_id: str = Field(serialization_alias="user_id", validation_alias="id")
    email: str
    role: UserRole
    is_active: bool
    is_service_account: bool


class UserSummary(UserProfile):
    """Extended representation with activation metadata."""

    created_at: datetime
    updated_at: datetime


__all__ = ["UserProfile", "UserSummary", "UserRole"]
