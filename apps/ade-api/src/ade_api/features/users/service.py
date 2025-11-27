"""Business logic for user operations."""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.features.roles.service import (
    get_global_permissions_for_user,
    get_global_role_slugs_for_user,
)
from ade_api.shared.core.logging import log_context
from ade_api.shared.pagination import paginate_sql
from ade_api.shared.types import OrderBy

from ..auth.security import hash_password
from .filters import UserFilters, apply_user_filters
from .models import User
from .repository import UsersRepository
from .schemas import UserOut, UserPage, UserProfile

logger = logging.getLogger(__name__)


class UsersService:
    """Expose read-oriented helpers for user accounts."""

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session
        self._repo = UsersRepository(session)

    async def get_profile(self, *, user: User) -> UserProfile:
        """Return the profile for the authenticated user."""
        logger.debug(
            "user.profile.get.start",
            extra=log_context(user_id=str(user.id)),
        )

        profile = await self._build_profile(user)

        logger.debug(
            "user.profile.get.success",
            extra=log_context(user_id=str(user.id)),
        )
        return profile

    async def list_users(
        self,
        *,
        page: int,
        page_size: int,
        include_total: bool,
        order_by: OrderBy,
        filters: UserFilters,
    ) -> UserPage:
        """Return paginated users according to the supplied parameters."""

        logger.debug(
            "users.list.start",
            extra=log_context(
                page=page,
                page_size=page_size,
                include_total=include_total,
                order_by=str(order_by),
            ),
        )

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

        items: list[UserOut] = []
        for user in page_result.items:
            profile = await self._build_profile(user)
            items.append(
                UserOut(
                    **profile.model_dump(),
                    created_at=user.created_at,
                    updated_at=user.updated_at,
                )
            )

        result = UserPage(
            items=items,
            page=page_result.page,
            page_size=page_result.page_size,
            has_next=page_result.has_next,
            has_previous=page_result.has_previous,
            total=page_result.total,
        )

        logger.info(
            "users.list.success",
            extra=log_context(
                page=result.page,
                page_size=result.page_size,
                count=len(result.items),
                total=result.total,
            ),
        )
        return result

    async def _build_profile(self, user: User) -> UserProfile:
        logger.debug(
            "user.profile.build",
            extra=log_context(user_id=str(user.id)),
        )

        permissions = await get_global_permissions_for_user(
            session=self._session,
            user=user,
        )
        roles = await get_global_role_slugs_for_user(
            session=self._session,
            user=user,
        )
        return UserProfile(
            id=str(user.id),
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
        # Avoid logging full email; optionally log the domain for debugging.
        email_domain: str | None = None
        if "@" in canonical_email:
            _, email_domain = canonical_email.rsplit("@", 1)

        logger.debug(
            "user.admin.create.start",
            extra=log_context(
                email_domain=email_domain,
                has_display_name=bool(display_name),
            ),
        )

        existing = await self._repo.get_by_email(canonical_email)
        if existing is not None:
            logger.warning(
                "user.admin.create.conflict_existing",
                extra=log_context(
                    user_id=str(existing.id),
                    email_domain=email_domain,
                ),
            )
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
            logger.warning(
                "user.admin.create.integrity_conflict",
                extra=log_context(
                    email_domain=email_domain,
                    has_display_name=bool(display_name),
                ),
            )
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Email already in use",
            ) from exc

        logger.info(
            "user.admin.create.success",
            extra=log_context(
                user_id=str(user.id),
                email_domain=email_domain,
                is_active=user.is_active,
                is_service_account=user.is_service_account,
                has_display_name=bool(cleaned_display_name),
            ),
        )
        return user


__all__ = ["UsersService"]
