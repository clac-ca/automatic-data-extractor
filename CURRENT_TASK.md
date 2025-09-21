# 🔄 Next Task — Inline Authentication Event Logging

## Context
With `AuthenticatedIdentity` in place, the remaining auth service complexity comes from helper functions such as `login_success`, `login_failure`, `logout`, `session_refreshed`, and `cli_action`. Each wraps `record_event` with lightly customised payloads, forcing every caller to hop through indirection instead of building the event alongside the behaviour that triggered it. Simplifying these helpers will cut duplication and bring the event logging in line with the "no unnecessary abstraction" guideline.

## Goals
1. Remove the thin event helpers in `services/auth.py` (or collapse them into a single minimal helper) and update all call sites to emit events inline.
2. Keep the generated event payloads and types consistent with today's behaviour so downstream analytics/tests remain valid.
3. Ensure the CLI commands under `auth.py` continue to log operator actions without relying on the removed helpers.
4. Refresh the unit tests (especially `backend/tests/test_auth.py`) to cover the revised event logging paths.

## Implementation notes
- Prefer direct `record_event` calls within the routes and CLI handlers so context stays close to the behaviour being logged.
- Update or add deterministic assertions to confirm events are still persisted with the expected metadata.
- While refactoring, prune any dead imports or constants that become unused after the helpers are removed.

## Definition of done
- Event logging in auth routes and CLI commands no longer depends on the removed helper functions.
- All updated code paths emit the same event types, sources, and payload keys as before the refactor.
- Associated tests reflect the new structure and continue to validate event emission.
- `pytest backend/tests/test_auth.py` passes.
