# 🔄 Next Task — Streamline Auth Dependency & FastAPI Security Wiring

## Context
The authentication regression tests now cover API keys, sessions, SSO auto-provisioning, and auth-disabled mode. With safety nets in place we can simplify the runtime dependency itself. The current `get_current_user` implementation manually parses headers/cookies and manages state; FastAPI offers first-class primitives for this logic. Aligning with the lighter architecture target will make ongoing maintenance easier and keep behaviour consistent with the new tests.

## Goals
1. Replace hand-rolled header parsing in `auth.dependencies` with FastAPI security utilities (`HTTPBearer`, `APIKeyHeader`, cookie extraction helpers) while keeping behaviour identical.
2. Trim duplicate session/API-key metadata lookups so the dependency issues exactly one DB transaction per request.
3. Preserve the request context contract (`request.state.auth_context`, `request.state.auth_session`, `request.state.api_key`) now validated by the test suite.
4. Ensure OpenAPI security metadata still reflects available modes (basic, sso, api-key, none).

## Implementation notes
- Reuse FastAPI's built-in security classes instead of parsing Authorization headers manually.
- Keep the synthetic admin user behaviour when `AUTH_DISABLED` is set; verify using the new tests.
- Make sure revoked sessions/api keys still return 403, and that logout clears only cookies.
- Update or extend tests only if the refactor requires different assertions; prefer adapting the dependency to satisfy existing expectations.
- Avoid introducing new abstractions—prefer clear, direct functions.

## Definition of done
- `auth.dependencies` delegates header/cookie parsing to FastAPI primitives and contains minimal control flow.
- All regression tests in `backend/tests/test_auth.py` pass without changes to their intent.
- No new dependencies added; OpenAPI schema remains accurate.
