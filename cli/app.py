"""Argument parser wiring for the ADE CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

from backend.api.modules.users.models import UserRole

from cli.commands import api_keys as api_keys_commands
from cli.commands import settings as settings_command
from cli.commands import start as start_command
from cli.commands import users as user_commands

__all__ = ["build_cli_app"]


def _add_password_arguments(parser: argparse.ArgumentParser, *, required: bool) -> None:
    group = parser.add_mutually_exclusive_group(required=required)
    group.add_argument(
        "--password",
        help="Password value to use directly.",
    )
    group.add_argument(
        "--password-file",
        type=Path,
        help="Read password from the first line of the specified file.",
    )


def build_cli_app() -> argparse.ArgumentParser:
    """Return the configured ``argparse`` parser for the CLI."""

    parser = argparse.ArgumentParser(
        prog="ade",
        description="Administrative tooling for the Automatic Data Extractor platform.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Development workflow -------------------------------------------------
    start_parser = subparsers.add_parser(
        "start",
        help="Run the backend and frontend development servers.",
    )
    start_command.register_arguments(start_parser)
    start_parser.set_defaults(handler=start_command.start)

    settings_parser = subparsers.add_parser(
        "settings",
        help="Inspect ADE configuration.",
    )
    settings_parser.set_defaults(handler=settings_command.dump)

    # User management -----------------------------------------------------
    users_parser = subparsers.add_parser("users", help="Manage ADE user accounts.")
    users_subparsers = users_parser.add_subparsers(dest="users_command", required=True)

    create_parser = users_subparsers.add_parser(
        "create",
        help="Create a new ADE user.",
    )
    create_parser.add_argument("--email", required=True, help="Email address for the user.")
    create_parser.add_argument(
        "--role",
        choices=[role.value for role in UserRole],
        default=UserRole.MEMBER.value,
        help="Role assigned to the user (default: member).",
    )
    create_parser.add_argument(
        "--inactive",
        action="store_true",
        help="Create the user in an inactive state.",
    )
    create_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON output for scripting.",
    )
    _add_password_arguments(create_parser, required=True)
    create_parser.set_defaults(handler=user_commands.create)

    list_parser = users_subparsers.add_parser(
        "list",
        help="List existing ADE users.",
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON output for scripting.",
    )
    list_parser.set_defaults(handler=user_commands.list_users)

    activate_parser = users_subparsers.add_parser(
        "activate",
        help="Activate a user by identifier.",
    )
    activate_parser.add_argument(
        "user_id",
        nargs="?",
        help="Identifier of the user to activate.",
    )
    activate_parser.add_argument(
        "--email",
        help="Email address of the user to activate.",
    )
    activate_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON output for scripting.",
    )
    activate_parser.set_defaults(handler=user_commands.activate)

    deactivate_parser = users_subparsers.add_parser(
        "deactivate",
        help="Deactivate a user by identifier.",
    )
    deactivate_parser.add_argument(
        "user_id",
        nargs="?",
        help="Identifier of the user to deactivate.",
    )
    deactivate_parser.add_argument(
        "--email",
        help="Email address of the user to deactivate.",
    )
    deactivate_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON output for scripting.",
    )
    deactivate_parser.set_defaults(handler=user_commands.deactivate)

    password_parser = users_subparsers.add_parser(
        "set-password",
        help="Set the password for an existing user.",
    )
    password_parser.add_argument(
        "user_id",
        nargs="?",
        help="Identifier of the user to update.",
    )
    password_parser.add_argument(
        "--email",
        help="Email address of the user to update.",
    )
    password_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON output for scripting.",
    )
    _add_password_arguments(password_parser, required=True)
    password_parser.set_defaults(handler=user_commands.set_password)

    # API key management --------------------------------------------------
    keys_parser = subparsers.add_parser(
        "api-keys",
        help="Manage API keys for ADE service integrations.",
    )
    keys_subparsers = keys_parser.add_subparsers(dest="api_keys_command", required=True)

    issue_parser = keys_subparsers.add_parser(
        "issue",
        help="Issue an API key for a user.",
    )
    target_group = issue_parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument(
        "--user-id",
        help="Issue a key for the specified user identifier.",
    )
    target_group.add_argument(
        "--email",
        help="Issue a key for the specified email address.",
    )
    issue_parser.add_argument(
        "--expires-in",
        type=int,
        default=None,
        help="Number of days before the key expires.",
    )
    issue_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON output for scripting.",
    )
    issue_parser.set_defaults(handler=api_keys_commands.issue)

    list_keys_parser = keys_subparsers.add_parser(
        "list",
        help="List issued API keys.",
    )
    list_keys_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON output for scripting.",
    )
    list_keys_parser.set_defaults(handler=api_keys_commands.list_keys)

    revoke_parser = keys_subparsers.add_parser(
        "revoke",
        help="Revoke an API key by identifier.",
    )
    revoke_parser.add_argument("api_key_id", help="Identifier of the API key to revoke.")
    revoke_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON output for scripting.",
    )
    revoke_parser.set_defaults(handler=api_keys_commands.revoke)

    return parser
