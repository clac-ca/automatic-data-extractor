"""Business logic for user operations."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ade.features.roles.service import (
    get_global_permissions_for_user,
    get_global_role_slugs_for_user,
)

from ..auth.security import hash_password
from .models import User
from .repository import UsersRepository
from .schemas import UserProfile, UserSummary


class UsersService:
    """Expose read-oriented helpers for user accounts."""

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session
        self._repo = UsersRepository(session)

    async def get_profile(self, *, user: User) -> UserProfile:
        """Return the profile for the authenticated user."""

        return await self._build_profile(user)

    async def list_users(self) -> list[UserSummary]:
        """Return all users ordered by email."""

        users = await self._repo.list_users()
        summaries: list[UserSummary] = []
        for user in users:
            profile = await self._build_profile(user)
            summaries.append(
                UserSummary(
                    **profile.model_dump(),
                    created_at=user.created_at,
                    updated_at=user.updated_at,
                )
            )
        return summaries

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
