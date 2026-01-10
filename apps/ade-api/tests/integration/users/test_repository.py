"""Tests for the user repository helpers."""

from __future__ import annotations

from uuid import uuid4

from ade_api.features.users.repository import UsersRepository


def test_create_user_persists_password_hash(session) -> None:
    """Creating a user with a password should persist the hash."""

    repo = UsersRepository(session)

    user = repo.create(
        email=f"{uuid4().hex}@example.com",
        hashed_password="argon2id$example",
        display_name="  Example User  ",
    )

    assert user.hashed_password == "argon2id$example"
    assert user.failed_login_count == 0
    assert user.locked_until is None
    assert user.is_service_account is False


def test_list_users_returns_all_records(session) -> None:
    """The repository should return all users ordered by email."""

    repo = UsersRepository(session)

    first = repo.create(
        email=f"{uuid4().hex}@example.com",
        hashed_password="argon2id$first",
    )
    second = repo.create(
        email=f"{uuid4().hex}@example.com",
        hashed_password="argon2id$example",
    )

    users = repo.list_users()
    identifiers = {user.id for user in users}
    assert {first.id, second.id}.issubset(identifiers)


def test_create_service_account_sets_flag(session) -> None:
    """Creating a service account should store the flag."""

    repo = UsersRepository(session)

    user = repo.create(
        email=f"{uuid4().hex}@example.com",
        hashed_password="argon2id$example",
        is_service_account=True,
    )

    assert user.is_service_account is True


def test_set_password_updates_hash(session) -> None:
    """set_password should update the user's password hash."""

    repo = UsersRepository(session)

    user = repo.create(
        email=f"{uuid4().hex}@example.com",
        hashed_password="argon2id$example",
    )

    updated = repo.set_password(user, "argon2id$first")
    assert updated.hashed_password == "argon2id$first"

    updated_again = repo.set_password(user, "argon2id$second")
    assert updated_again.hashed_password == "argon2id$second"
    assert updated_again.id == updated.id
