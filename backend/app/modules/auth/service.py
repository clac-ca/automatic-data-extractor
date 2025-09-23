"""Authentication and authorisation services."""

from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException, status

from ...core.service import BaseService, ServiceContext
from ..users.models import User
from ..users.repository import UsersRepository
from .security import (
    TokenPayload,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def normalise_email(value: str) -> str:
    """Return a canonical representation for email comparisons."""

    candidate = value.strip()
    if not candidate:
        msg = "Email must not be empty"
        raise ValueError(msg)
    return candidate.lower()


class AuthService(BaseService):
    """Encapsulate login and token verification logic."""

    def __init__(self, *, context: ServiceContext) -> None:
        super().__init__(context=context)
        if self.session is None:
            raise RuntimeError("AuthService requires a database session")
        self._users = UsersRepository(self.session)

    async def authenticate(self, *, email: str, password: str) -> User:
        """Return the active user matching ``email``/``password``."""

        canonical = normalise_email(email)
        user = await self._users.get_by_email(canonical)
        if user is None or not user.password_hash:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if not verify_password(password, user.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="User inactive")
        return user

    async def issue_token(self, user: User) -> str:
        """Return a signed token for ``user``."""

        expires = timedelta(minutes=self.settings.auth_token_exp_minutes)
        return create_access_token(
            user_id=user.id,
            email=user.email,
            role=user.role,
            secret=self.settings.auth_token_secret,
            algorithm=self.settings.auth_token_algorithm,
            expires_delta=expires,
        )

    def decode_token(self, token: str) -> TokenPayload:
        """Decode ``token`` and return its payload."""

        return decode_access_token(
            token=token,
            secret=self.settings.auth_token_secret,
            algorithms=[self.settings.auth_token_algorithm],
        )

    async def resolve_user(self, payload: TokenPayload) -> User:
        """Return the user represented by ``payload`` if active."""

        user = await self._users.get_by_id(payload.user_id)
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="User inactive")
        return user


__all__ = ["AuthService", "hash_password", "normalise_email"]
