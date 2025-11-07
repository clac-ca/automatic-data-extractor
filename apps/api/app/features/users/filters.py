from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.sql import Select

from apps.api.app.settings import MAX_SEARCH_LEN, MIN_SEARCH_LEN
from apps.api.app.shared.filters import FilterBase

from .models import User


class UserFilters(FilterBase):
    """Query parameters supported by the user listing endpoint."""

    q: Optional[str] = Field(
        None,
        min_length=MIN_SEARCH_LEN,
        max_length=MAX_SEARCH_LEN,
        description="Free text search across email and display name.",
    )
    is_active: Optional[bool] = Field(
        None,
        description="Filter by active/inactive status.",
    )
    is_service_account: Optional[bool] = Field(
        None,
        description="Filter by service account flag.",
    )

    @field_validator("q")
    @classmethod
    def _trim_query(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        candidate = value.strip()
        return candidate or None


def apply_user_filters(stmt: Select, filters: UserFilters) -> Select:
    """Apply ``filters`` to a user query."""

    if filters.q:
        pattern = f"%{filters.q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(User.email).like(pattern),
                func.lower(User.display_name).like(pattern),
            )
        )
    if filters.is_active is not None:
        stmt = stmt.where(User.is_active.is_(filters.is_active))
    if filters.is_service_account is not None:
        stmt = stmt.where(User.is_service_account.is_(filters.is_service_account))
    return stmt


__all__ = ["UserFilters", "apply_user_filters"]
