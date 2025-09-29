"""Query helpers for working with ``User`` records."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User, UserRole


def _canonical_email(value: str) -> str:
    return value.strip().lower()


class UsersRepository:
    """High-level persistence helpers for the unified user model."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: str) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email_canonical == _canonical_email(email))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_sso_identity(self, provider: str, subject: str) -> User | None:
        stmt = select(User).where(
            User.sso_provider == provider, User.sso_subject == subject
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_users(
        self, *, include_service_accounts: bool = True
    ) -> list[User]:
        stmt = select(User).order_by(User.email_canonical)
        if not include_service_accounts:
            stmt = stmt.where(User.is_service_account.is_(False))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_service_accounts(self) -> list[User]:
        stmt = (
            select(User)
            .where(User.is_service_account.is_(True))
            .order_by(User.email_canonical)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_admins(self) -> int:
        stmt = select(func.count()).where(User.role == UserRole.ADMIN)
        result = await self._session.execute(stmt)
        count = result.scalar_one()
        return int(count or 0)

    async def create(
        self,
        *,
        email: str,
        password_hash: str | None = None,
        display_name: str | None = None,
        description: str | None = None,
        is_service_account: bool = False,
        created_by_user_id: str | None = None,
        role: UserRole = UserRole.MEMBER,
        is_active: bool = True,
    ) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            description=description,
            is_service_account=is_service_account,
            created_by_user_id=created_by_user_id,
            role=role,
            is_active=is_active,
        )
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user

__all__ = ["UsersRepository"]
