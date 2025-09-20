"""Command-line interface for ADE user management."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..db import Base, get_engine, get_sessionmaker
from ..models import User, UserRole
from . import passwords
from .events import cli_action

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage ADE user accounts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def _add_operator_argument(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--operator-email",
            help="Email address recorded as the actor for emitted events",
        )

    create = subparsers.add_parser("create-user", help="Create a new ADE user")
    create.add_argument("email", help="Email address of the user")
    create.add_argument("--password", help="Password for HTTP Basic authentication")
    create.add_argument(
        "--role",
        choices=[role.value for role in UserRole],
        default=UserRole.VIEWER.value,
        help="Role assigned to the user",
    )
    create.add_argument("--sso-provider", help="OIDC provider identifier")
    create.add_argument("--sso-subject", help="OIDC subject identifier")
    create.add_argument("--inactive", action="store_true", help="Create the account in a disabled state")

    _add_operator_argument(create)

    reset = subparsers.add_parser("reset-password", help="Set a new password for an existing user")
    reset.add_argument("email", help="Email address of the user")
    reset.add_argument("--password", required=True, help="New password value")

    _add_operator_argument(reset)

    deactivate = subparsers.add_parser("deactivate", help="Deactivate a user account")
    deactivate.add_argument("email", help="Email address of the user")

    _add_operator_argument(deactivate)

    promote = subparsers.add_parser("promote", help="Grant administrator privileges to a user")
    promote.add_argument("email", help="Email address of the user")

    _add_operator_argument(promote)

    list_users = subparsers.add_parser("list-users", help="Display all user accounts")
    list_users.add_argument("--show-inactive", action="store_true", help="Include deactivated accounts")

    return parser


def _ensure_schema() -> None:
    from .. import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())


def _normalise_email(email: str) -> str:
    candidate = email.strip().lower()
    if not candidate:
        raise ValueError("Email address cannot be empty")
    return candidate


def _load_user(db: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    return db.execute(statement).scalar_one_or_none()


def _enforce_admin_allowlist(settings: config.Settings, email: str) -> None:
    if not settings.admin_email_allowlist_enabled:
        return
    if email not in settings.admin_allowlist:
        raise ValueError(
            "Email address is not permitted to hold administrator privileges"
        )


def _create_user(db: Session, settings: config.Settings, args: argparse.Namespace) -> None:
    email = _normalise_email(args.email)
    if _load_user(db, email) is not None:
        raise ValueError("User already exists")

    role = UserRole(args.role)
    if role == UserRole.ADMIN:
        _enforce_admin_allowlist(settings, email)

    password_hash: str | None = None
    if args.password:
        password_hash = passwords.hash_password(args.password)
    elif not args.sso_subject:
        raise ValueError("Password or --sso-subject is required")

    user = User(
        email=email,
        password_hash=password_hash,
        role=role,
        is_active=not args.inactive,
        sso_provider=args.sso_provider,
        sso_subject=args.sso_subject,
    )
    db.add(user)
    db.flush()

    cli_action(
        db,
        user=user,
        event_type="user.created",
        operator_email=args.operator_email,
        payload={"role": role.value},
        commit=False,
    )
    db.commit()
    print(f"Created user {user.email} ({user.user_id})")


def _reset_password(db: Session, settings: config.Settings, args: argparse.Namespace) -> None:
    email = _normalise_email(args.email)
    user = _load_user(db, email)
    if user is None:
        raise ValueError("User not found")

    user.password_hash = passwords.hash_password(args.password)
    db.flush()
    cli_action(
        db,
        user=user,
        event_type="user.password.reset",
        operator_email=args.operator_email,
        commit=False,
    )
    db.commit()
    print(f"Password reset for {user.email}")


def _deactivate_user(db: Session, settings: config.Settings, args: argparse.Namespace) -> None:
    email = _normalise_email(args.email)
    user = _load_user(db, email)
    if user is None:
        raise ValueError("User not found")

    user.is_active = False
    db.flush()
    cli_action(
        db,
        user=user,
        event_type="user.deactivated",
        operator_email=args.operator_email,
        commit=False,
    )
    db.commit()
    print(f"Deactivated {user.email}")


def _promote_user(db: Session, settings: config.Settings, args: argparse.Namespace) -> None:
    email = _normalise_email(args.email)
    user = _load_user(db, email)
    if user is None:
        raise ValueError("User not found")

    _enforce_admin_allowlist(settings, email)
    user.role = UserRole.ADMIN
    db.flush()
    cli_action(
        db,
        user=user,
        event_type="user.promoted",
        operator_email=args.operator_email,
        payload={"role": UserRole.ADMIN.value},
        commit=False,
    )
    db.commit()
    print(f"Promoted {user.email} to administrator")


def _list_users(db: Session, settings: config.Settings, args: argparse.Namespace) -> None:
    statement = select(User).order_by(User.email)
    rows = db.execute(statement).scalars().all()
    for user in rows:
        if not args.show_inactive and not user.is_active:
            continue
        status = "active" if user.is_active else "inactive"
        sso_info = ""
        if user.sso_provider and user.sso_subject:
            sso_info = f" sso={user.sso_provider}:{user.sso_subject}"
        print(f"{user.email} [{user.role.value}] {status}{sso_info}")


def _with_session(func: Callable[[Session, config.Settings, argparse.Namespace], None], args: argparse.Namespace) -> None:
    settings = config.get_settings()
    session_factory = get_sessionmaker()
    with session_factory() as db:
        func(db, settings, args)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        _ensure_schema()
        command_map: dict[str, Callable[[Session, config.Settings, argparse.Namespace], None]] = {
            "create-user": _create_user,
            "reset-password": _reset_password,
            "deactivate": _deactivate_user,
            "promote": _promote_user,
            "list-users": _list_users,
        }
        handler = command_map[args.command]
        _with_session(handler, args)
        return 0
    except ValueError as exc:
        logger.error(str(exc))
        return 1
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("User management command failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
