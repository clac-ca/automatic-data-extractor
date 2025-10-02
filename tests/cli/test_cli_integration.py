"""Integration coverage for the ADE CLI commands."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603,S607 - executed against local module
        [sys.executable, "-m", "app.cli", *args],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.usefixtures("_configure_database")
def test_user_and_api_key_workflow(tmp_path: Path) -> None:
    email = f"cli-{uuid4().hex}@example.test"

    created = _run_cli(
        "users",
        "create",
        "--email",
        email,
        "--password",
        "TempP@ssw0rd",
        "--json",
    )
    assert created.returncode == 0, created.stderr
    create_payload = json.loads(created.stdout)
    user = create_payload["user"]
    user_id = user["id"]

    listed = _run_cli("users", "list", "--json")
    assert listed.returncode == 0, listed.stderr
    users_payload = json.loads(listed.stdout)
    emails = {entry["email"] for entry in users_payload["users"]}
    assert email in emails

    deactivated = _run_cli("users", "deactivate", "--email", email, "--json")
    assert deactivated.returncode == 0, deactivated.stderr
    deactivate_payload = json.loads(deactivated.stdout)
    assert deactivate_payload["user"]["is_active"] is False

    secret_file = tmp_path / "password.txt"
    secret_file.write_text("N3wPassword!\n", encoding="utf-8")
    updated = _run_cli(
        "users",
        "set-password",
        "--email",
        email,
        "--password-file",
        str(secret_file),
        "--json",
    )
    assert updated.returncode == 0, updated.stderr

    activated = _run_cli("users", "activate", user_id, "--json")
    assert activated.returncode == 0, activated.stderr
    activate_payload = json.loads(activated.stdout)
    assert activate_payload["user"]["is_active"] is True

    issued = _run_cli(
        "api-keys",
        "issue",
        "--user-id",
        user_id,
        "--expires-in",
        "7",
        "--json",
    )
    assert issued.returncode == 0, issued.stderr
    issued_payload = json.loads(issued.stdout)
    api_key_id = issued_payload["api_key"]["id"]
    raw_key = issued_payload["raw_key"]
    assert raw_key.startswith(issued_payload["api_key"]["token_prefix"])

    keys_list = _run_cli("api-keys", "list", "--json")
    assert keys_list.returncode == 0, keys_list.stderr
    keys_payload = json.loads(keys_list.stdout)
    key_ids = {entry["id"] for entry in keys_payload["api_keys"]}
    assert api_key_id in key_ids

    revoked = _run_cli("api-keys", "revoke", api_key_id, "--json")
    assert revoked.returncode == 0, revoked.stderr
    revoke_payload = json.loads(revoked.stdout)
    assert revoke_payload["revoked"] == api_key_id

    keys_list_after = _run_cli("api-keys", "list", "--json")
    assert keys_list_after.returncode == 0, keys_list_after.stderr
    keys_payload_after = json.loads(keys_list_after.stdout)
    assert keys_payload_after["api_keys"] == []


@pytest.mark.usefixtures("_configure_database")
def test_user_identifier_validation_errors() -> None:
    missing_identifier = _run_cli("users", "activate")
    assert missing_identifier.returncode == 1
    assert "User identifier required" in missing_identifier.stderr

    both_identifiers = _run_cli(
        "users",
        "deactivate",
        "user-123",
        "--email",
        "user@example.test",
    )
    assert both_identifiers.returncode == 1
    assert "Specify either a user ID" in both_identifiers.stderr
