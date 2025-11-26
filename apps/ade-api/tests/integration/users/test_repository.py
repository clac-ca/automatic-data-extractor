"""Tests for the user repository helpers."""

from __future__ import annotations

from uuid import uuid4

import pytest

from ade_api.features.users.models import UserCredential
from ade_api.features.users.repository import UsersRepository
from ade_api.shared.db.session import get_sessionmaker

pytestmark = pytest.mark.asyncio


async def test_create_user_persists_password_hash() -> None:
    """Creating a user with a password should persist a credential row."""

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        repo = UsersRepository(session)

        user = await repo.create(
            email=f"{uuid4().hex}@example.test",
            password_hash="argon2id$example",
            display_name="  Example User  ",
        )

        assert user.credential is not None
        assert isinstance(user.credential, UserCredential)
        assert user.credential.password_hash == "argon2id$example"
        assert user.failed_login_count == 0
        assert user.locked_until is None
        assert user.is_service_account is False


async def test_list_users_returns_all_records() -> None:
    """The repository should return all users ordered by email."""

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        repo = UsersRepository(session)

        first = await repo.create(
            email=f"{uuid4().hex}@example.test",
            password_hash=None,
        )
        second = await repo.create(
            email=f"{uuid4().hex}@example.test",
            password_hash="argon2id$example",
        )

        users = await repo.list_users()
        identifiers = {user.id for user in users}
        assert {first.id, second.id}.issubset(identifiers)


async def test_create_service_account_sets_flag() -> None:
    """Creating a service account should store the flag."""

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        repo = UsersRepository(session)

        user = await repo.create(
            email=f"{uuid4().hex}@example.test",
            password_hash=None,
            is_service_account=True,
        )

        assert user.is_service_account is True


async def test_set_password_creates_or_updates_credential() -> None:
    """set_password should upsert the user's credential record."""

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        repo = UsersRepository(session)

        user = await repo.create(
            email=f"{uuid4().hex}@example.test",
            password_hash=None,
        )

        credential = await repo.set_password(user, "argon2id$first")
        assert credential.password_hash == "argon2id$first"

        updated = await repo.set_password(user, "argon2id$second")
        assert updated.password_hash == "argon2id$second"
        assert updated.id == credential.id
