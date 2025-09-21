# 🔄 Next Task — Simplify get_authenticated_identity transaction handling

## Context
With credential resolution now fully inlined, `get_authenticated_identity` still carries `pending_commit` bookkeeping and defers raising session errors until after API key checks. This state machine is a holdover from the old helper and can be replaced with straightforward control flow that finalises database mutations immediately.

## Goals
1. Finalise session revocation (or rollbacks) inline so the dependency no longer tracks `pending_commit` state.
2. Raise session errors immediately when no API key token is provided, while still allowing an API key to rescue a failed session attempt when present.
3. Preserve the lazy commit semantics for session revocation and API key usage updates, and extend tests to cover the mixed-credential path (invalid session + valid API key).

## Definition of done
- `get_authenticated_identity` no longer relies on `pending_commit` or deferred exceptions.
- Tests cover both failure-only and mixed credential flows directly through the dependency.
- `pytest backend/tests/test_auth.py` passes.
