# ✅ Completed Task — Simplify get_authenticated_identity transaction handling

## Context
`get_authenticated_identity` still carried deferred commit bookkeeping from the deprecated resolver helper, complicating control flow and delaying session errors.

## Outcome
- Finalised session revocation immediately within the dependency, removing the `pending_commit` state machine.
- Raised session authentication failures as soon as they occur unless an API key token is available to recover the request.
- Added coverage for the mixed credential path (invalid session + valid API key) and re-ran `pytest backend/tests/test_auth.py` to confirm behaviour.
