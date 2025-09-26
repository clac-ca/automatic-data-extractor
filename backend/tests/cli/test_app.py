"""Smoke tests for the CLI argument parser."""

from __future__ import annotations

from cli.app import build_cli_app
from cli.commands import api_keys, users


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
