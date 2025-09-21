# ✅ Completed Task — Restore simple settings access and centralise the auth CLI

## Context
FastAPI dependency injection for configuration felt heavier than necessary, and the user management CLI lived inside the auth
service module with no shared entry point. Aligning with the goal of simplicity required reverting the settings change and
making the CLI easier to discover across services.

## Outcome
- Reverted auth route handlers to call `config.get_settings()` directly, removing the dependency injection churn.
- Added a shared `backend/app/cli.py` entry point (and `python -m backend.app`) that will host CLI commands for every service.
- Updated the auth service to register its subcommands with the shared CLI so existing flows keep working while paving the way for future commands.
