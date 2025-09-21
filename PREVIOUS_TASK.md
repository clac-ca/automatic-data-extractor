# ✅ Completed Task — Inline Authentication Event Logging

## Context
Event logging for authentication actions relied on thin helper wrappers in `services/auth.py`. Each routed call first invoked a helper that delegated to `record_event`, pushing event metadata away from the triggering behaviour and adding needless indirection. Simplifying these call sites keeps event payloads close to the logic that assembles them and removes redundant abstractions.

## Outcome
- Removed the `login_success`, `login_failure`, `logout`, `session_refreshed`, and `cli_action` helpers and emitted events directly where actions occur.
- Updated API routes and CLI commands to call `record_event` inline while preserving payload structure, actors, and sources.
- Refreshed authentication tests to align with the simplified logging paths; `pytest backend/tests/test_auth.py` passes.
