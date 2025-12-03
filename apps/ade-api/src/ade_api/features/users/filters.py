from __future__ import annotations

from pydantic import Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.sql import Select

from ade_api.common.filters import FilterBase
from ade_api.core.models import User
from ade_api.settings import MAX_SEARCH_LEN, MIN_SEARCH_LEN


class UserFilters(FilterBase):
    """Query parameters supported by the user listing endpoint."""

    q: str | None = Field(
        None,
        min_length=MIN_SEARCH_LEN,
        max_length=MAX_SEARCH_LEN,
        description="Free text search across email and display name.",
    )
    is_active: bool | None = Field(
        None,
        description="Filter by active/inactive status.",
    )
    is_service_account: bool | None = Field(
        None,
        description="Filter by service account flag.",
    )

    @field_validator("q")
    @classmethod
    def _trim_query(cls, value: str | None) -> str | None:
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
        stmt = stmt.where(User.is_active == filters.is_active)
    if filters.is_service_account is not None:
        stmt = stmt.where(User.is_service_account == filters.is_service_account)
    return stmt


__all__ = ["UserFilters", "apply_user_filters"]
