"""Smoke tests for the CLI argument parser."""

from __future__ import annotations

from cli.app import build_cli_app
from cli.commands import api_keys, reset as reset_command, settings as settings_command, users


def test_users_create_handler_resolution() -> None:
    parser = build_cli_app()
    args = parser.parse_args(
        [
            "users",
            "create",
            "--email",
            "example@example.com",
            "--password",
            "secret-value",
        ]
    )
    assert args.handler is users.create


def test_users_activate_accepts_email_identifier() -> None:
    parser = build_cli_app()
    args = parser.parse_args(
        [
            "users",
            "activate",
            "--email",
            "example@example.com",
        ]
    )
    assert args.handler is users.activate
    assert args.email == "example@example.com"
    assert args.user_id is None


def test_api_keys_issue_handler_resolution() -> None:
    parser = build_cli_app()
    args = parser.parse_args(
        [
            "api-keys",
            "issue",
            "--user-id",
            "user-123",
        ]
    )
    assert args.handler is api_keys.issue


def test_start_command_collects_env_overrides() -> None:
    parser = build_cli_app()
    args = parser.parse_args(
        [
            "start",
            "--env",
            "ADE_LOGGING_LEVEL=DEBUG",
            "--env",
            "ADE_API_DOCS_ENABLED=true",
        ]
    )

    assert args.env == ["ADE_LOGGING_LEVEL=DEBUG", "ADE_API_DOCS_ENABLED=true"]


def test_settings_command_handler_resolution() -> None:
    parser = build_cli_app()
    args = parser.parse_args(["settings"])

    assert args.handler is settings_command.dump


def test_reset_command_handler_resolution() -> None:
    parser = build_cli_app()
    args = parser.parse_args(["reset", "--yes"])

    assert args.handler is reset_command.reset
    assert args.yes is True
