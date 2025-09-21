# ✅ Completed Task — Simplify request authentication dependencies

## Context
Authenticating requests mixed session cookies, bearer tokens, and API keys inside a single dependency that manually managed SQLAlchemy transactions. The flow was difficult to follow and frequently opened transactions on the shared request session even when the call path should have been read-only.

## Outcome
- Split authentication into composable FastAPI dependencies that individually resolve session cookies and API/API bearer tokens, using SQLAlchemy session factories inside the dependency to avoid leaking transactions into route handlers.
- Introduced a small `CredentialResolution` dataclass and helper functions so that `get_authenticated_identity` now just orchestrates the dependency results and emits consistent HTTP errors without hand-written rollbacks.
- Updated the authentication tests to exercise the new helpers directly, keeping coverage for session refreshes, API key usage, and open-access mode while maintaining the existing behaviour under the simplified architecture.
