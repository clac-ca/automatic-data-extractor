"""Business logic for user operations."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from ...core.service import BaseService, ServiceContext
from ..auth.security import hash_password
from .models import User, UserRole
from .repository import UsersRepository
from .schemas import UserProfile, UserSummary


class UsersService(BaseService):
    """Expose read-oriented helpers for user accounts."""

    def __init__(self, *, context: ServiceContext) -> None:
        super().__init__(context=context)
        if self.session is None:
            raise RuntimeError("UsersService requires a database session")
        self._repo = UsersRepository(self.session)

    async def get_profile(self) -> UserProfile:
        """Return the profile for the authenticated user."""

        user = self.current_user
        if user is None:
            raise RuntimeError("User context missing")
        return UserProfile.model_validate(user)

    async def list_users(self) -> list[UserSummary]:
        """Return all users ordered by email."""

        users = await self._repo.list_users()
        return [UserSummary.model_validate(user) for user in users]

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
                role=UserRole.ADMIN,
                is_active=True,
            )
        except IntegrityError as exc:  # pragma: no cover - defensive double check
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Email already in use",
            ) from exc
        return user


__all__ = ["UsersService"]
