"""Query helpers for working with ``User`` records."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import User, UserCredential, UserIdentity


def _canonical_email(value: str) -> str:
    return value.strip().lower()


class UsersRepository:
    """High-level persistence helpers for the unified user model."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: str) -> User | None:
        stmt = (
            select(User)
            .options(
                selectinload(User.credential),
                selectinload(User.identities),
            )
            .where(User.id == user_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_basic(self, user_id: str) -> User | None:
        """Lightweight lookup without eager-loading relationships."""

        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .options(
                selectinload(User.credential),
                selectinload(User.identities),
            )
            .where(User.email_canonical == _canonical_email(email))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_identity(self, provider: str, subject: str) -> UserIdentity | None:
        stmt = (
            select(UserIdentity)
            .options(selectinload(UserIdentity.user))
            .where(
                UserIdentity.provider == provider,
                UserIdentity.subject == subject,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_users(self) -> list[User]:
        stmt = (
            select(User)
            .options(selectinload(User.credential))
            .order_by(User.email_canonical)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        *,
        email: str,
        password_hash: str | None = None,
        display_name: str | None = None,
        is_active: bool = True,
        is_service_account: bool = False,
    ) -> User:
        user = User(
            email=email,
            display_name=display_name,
            is_active=is_active,
            is_service_account=is_service_account,
            failed_login_count=0,
        )
        self._session.add(user)
        await self._session.flush()

        if password_hash:
            credential = UserCredential(
                user_id=user.id,
                password_hash=password_hash,
                last_rotated_at=datetime.now(tz=UTC),
            )
            self._session.add(credential)
            await self._session.flush()
        await self._session.refresh(user)
        return user

    async def set_password(self, user: User, password_hash: str) -> UserCredential:
        credential = await self.get_credential(user.id)
        now = datetime.now(tz=UTC)
        if credential is None:
            credential = UserCredential(
                user_id=user.id,
                password_hash=password_hash,
                last_rotated_at=now,
            )
            self._session.add(credential)
        else:
            credential.password_hash = password_hash
            credential.last_rotated_at = now
        await self._session.flush()
        await self._session.refresh(credential)
        return credential

    async def get_credential(
        self, user_id: str
    ) -> UserCredential | None:
        stmt = (
            select(UserCredential)
            .where(UserCredential.user_id == user_id)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_identity(
        self, *, user: User, provider: str, subject: str
    ) -> UserIdentity:
        identity = UserIdentity(
            user_id=user.id,
            provider=provider,
            subject=subject,
        )
        self._session.add(identity)
        await self._session.flush()
        await self._session.refresh(identity)
        return identity

__all__ = ["UsersRepository"]
