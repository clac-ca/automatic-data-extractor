"""User management commands for the ADE CLI."""

from __future__ import annotations

from argparse import Namespace
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.security import hash_password
from app.features.roles.service import (
    assign_global_role,
    get_global_role_by_slug,
    sync_permission_registry,
)
from app.features.users.models import User
from app.features.users.repository import UsersRepository
from app.features.users.service import UsersService

from ..core.output import ColumnSpec, print_json, print_rows
from ..core.runtime import load_settings, normalise_email, open_session, read_secret

__all__ = [
    "create",
    "list_users",
    "activate",
    "deactivate",
    "set_password",
    "ROLE_CHOICES",
]


_ROLE_SLUGS = {
    "admin": "global-administrator",
    "user": "global-user",
}

ROLE_CHOICES = tuple(_ROLE_SLUGS.keys())


async def _serialise_user(session: AsyncSession, user: User) -> dict[str, Any]:
    profiles = UsersService(session=session)
    profile = await profiles.get_profile(user=user)
    return {
        "id": user.id,
        "email": profile.email,
        "display_name": profile.display_name,
        "global_roles": profile.roles,
        "global_permissions": profile.permissions,
        "is_service_account": bool(user.is_service_account),
        "is_active": bool(user.is_active),
        "failed_login_count": int(user.failed_login_count),
        "locked_until": user.locked_until.isoformat() if user.locked_until else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


def _user_columns() -> list[ColumnSpec]:
    return [
        ("ID", "id"),
        ("Email", "email"),
        (
            "Type",
            lambda row: "service_account" if row["is_service_account"] else "user",
        ),
        ("Global Roles", lambda row: ", ".join(row.get("global_roles", []))),
        (
            "Status",
            lambda row: (
                "locked"
                if row["locked_until"]
                else ("active" if row["is_active"] else "inactive")
            ),
        ),
        ("Failed Logins", "failed_login_count"),
    ]


def _resolve_password(args: Namespace) -> str:
    password = getattr(args, "password", None)
    password_file = getattr(args, "password_file", None)
    if password and password_file:
        msg = "Specify either --password or --password-file, not both"
        raise ValueError(msg)
    if password_file:
        return read_secret(password_file)
    if not password:
        msg = "Password is required"
        raise ValueError(msg)
    return password


async def _resolve_user(
    repo: UsersRepository,
    *,
    user_id: str | None,
    email: str | None,
) -> User:
    if user_id and email:
        msg = "Specify either a user ID argument or --email, not both"
        raise ValueError(msg)

    identifier: str
    if email:
        normalised = normalise_email(email)
        identifier = f"email '{normalised}'"
        user = await repo.get_by_email(normalised)
    else:
        if not user_id:
            msg = "User identifier required (provide an ID argument or --email)"
            raise ValueError(msg)
        identifier = f"id '{user_id}'"
        user = await repo.get_by_id(user_id)

    if user is None:
        msg = f"User {identifier} not found"
        raise ValueError(msg)
    return user


async def create(args: Namespace) -> None:
    settings = load_settings()
    email = normalise_email(args.email)
    password_text = _resolve_password(args)
    is_active = not args.inactive
    is_service_account = bool(args.service_account)
    role_choice = getattr(args, "role", "user")
    try:
        role_slug = _ROLE_SLUGS[role_choice]
    except KeyError as exc:
        msg = f"Unsupported role '{role_choice}'"
        raise ValueError(msg) from exc

    async with open_session(settings=settings) as session:
        await sync_permission_registry(session=session)
        repo = UsersRepository(session)
        existing = await repo.get_by_email(email)
        if existing is not None:
            msg = f"User with email '{email}' already exists"
            raise ValueError(msg)
        try:
            user = await repo.create(
                email=email,
                password_hash=hash_password(password_text),
                is_active=is_active,
                is_service_account=is_service_account,
            )
        except IntegrityError as exc:  # pragma: no cover - defensive guard
            msg = f"Failed to create user '{email}': {exc}"
            raise ValueError(msg) from exc

        role = await get_global_role_by_slug(session=session, slug=role_slug)
        if role is None:
            msg = f"Global role '{role_slug}' not found"
            raise ValueError(msg)
        await assign_global_role(session=session, user_id=user.id, role_id=role.id)
        serialised = await _serialise_user(session, user)

    if args.json:
        print_json({"user": serialised})
    else:
        print_rows([serialised], _user_columns())


async def list_users(args: Namespace) -> None:
    settings = load_settings()
    async with open_session(settings=settings) as session:
        repo = UsersRepository(session)
        users = await repo.list_users()
        serialised = [await _serialise_user(session, user) for user in users]
    if args.json:
        print_json({"users": serialised})
    else:
        print_rows(serialised, _user_columns())


async def activate(args: Namespace) -> None:
    await _toggle_active(args, should_activate=True)


async def deactivate(args: Namespace) -> None:
    await _toggle_active(args, should_activate=False)


async def _toggle_active(args: Namespace, *, should_activate: bool) -> None:
    settings = load_settings()
    async with open_session(settings=settings) as session:
        repo = UsersRepository(session)
        user = await _resolve_user(
            repo,
            user_id=getattr(args, "user_id", None),
            email=getattr(args, "email", None),
        )
        user.is_active = should_activate
        await session.flush()
        await session.refresh(user)
        serialised = await _serialise_user(session, user)
    if args.json:
        print_json({"user": serialised})
    else:
        print_rows([serialised], _user_columns())


async def set_password(args: Namespace) -> None:
    settings = load_settings()
    password_text = _resolve_password(args)
    async with open_session(settings=settings) as session:
        repo = UsersRepository(session)
        user = await _resolve_user(
            repo,
            user_id=getattr(args, "user_id", None),
            email=getattr(args, "email", None),
        )
        await repo.set_password(user, hash_password(password_text))
        await session.refresh(user)
        serialised = await _serialise_user(session, user)
    if args.json:
        print_json({"user": serialised})
    else:
        print_rows([serialised], _user_columns())
