"""Business logic for user operations."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.features.roles.service import (
    get_global_permissions_for_user,
    get_global_role_slugs_for_user,
)
from apps.api.app.shared.pagination import paginate_sql
from apps.api.app.shared.types import OrderBy

from ..auth.security import hash_password
from .models import User
from .repository import UsersRepository
from .schemas import UserListResponse, UserProfile, UserSummary
from .filters import UserFilters, apply_user_filters


class UsersService:
    """Expose read-oriented helpers for user accounts."""

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session
        self._repo = UsersRepository(session)

    async def get_profile(self, *, user: User) -> UserProfile:
        """Return the profile for the authenticated user."""

        return await self._build_profile(user)

    async def list_users(
        self,
        *,
        page: int,
        page_size: int,
        include_total: bool,
        order_by: OrderBy,
        filters: UserFilters,
    ) -> UserListResponse:
        """Return paginated users according to the supplied parameters."""

        stmt = select(User)
        stmt = apply_user_filters(stmt, filters)
        page_result = await paginate_sql(
            self._session,
            stmt,
            page=page,
            page_size=page_size,
            order_by=order_by,
            include_total=include_total,
        )

        items: list[UserSummary] = []
        for user in page_result.items:
            profile = await self._build_profile(user)
            items.append(
                UserSummary(
                    **profile.model_dump(),
                    created_at=user.created_at,
                    updated_at=user.updated_at,
                )
            )

        return UserListResponse(
            items=items,
            page=page_result.page,
            page_size=page_result.page_size,
            has_next=page_result.has_next,
            has_previous=page_result.has_previous,
            total=page_result.total,
        )

    async def _build_profile(self, user: User) -> UserProfile:
        permissions = await get_global_permissions_for_user(
            session=self._session, user=user
        )
        roles = await get_global_role_slugs_for_user(session=self._session, user=user)
        return UserProfile(
            user_id=str(user.id),
            email=user.email,
            is_active=user.is_active,
            is_service_account=user.is_service_account,
            display_name=user.display_name,
            roles=sorted(roles),
            permissions=sorted(permissions),
        )

    async def create_admin(
        self,
        *,
        email: str,
        password: str,
        display_name: str | None = None,
    ) -> User:
        """Create an administrator account with the supplied credentials."""

        canonical_email = email.strip().lower()
        existing = await self._repo.get_by_email(canonical_email)
        if existing is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Email already in use",
            )

        password_hash = hash_password(password)
        cleaned_display_name = display_name.strip() if display_name else None

        try:
            user = await self._repo.create(
                email=canonical_email,
                password_hash=password_hash,
                display_name=cleaned_display_name,
                is_active=True,
                is_service_account=False,
            )
        except IntegrityError as exc:  # pragma: no cover - defensive double check
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Email already in use",
            ) from exc
        return user


__all__ = ["UsersService"]
