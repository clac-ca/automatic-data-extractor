"""Business logic for user operations."""

from __future__ import annotations

from ...core.service import BaseService, ServiceContext
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


__all__ = ["UsersService"]
