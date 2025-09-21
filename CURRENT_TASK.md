# 🔄 Next Task — Simplify request authentication dependencies

## Context
`backend/app/services/auth.py` still resolves browser sessions and API keys inside a single monolithic dependency that manually juggles rollbacks, token revocation, and error handling. The flow is hard to audit and diverges from FastAPI's composable security patterns, making it expensive to extend or reason about failures.

## Goals
1. Break the current authentication dependency into smaller FastAPI dependencies that each resolve one credential type (session cookie, bearer token, API key header), leaning on the framework's `Security` utilities instead of hand-written parsing.
2. Remove manual transaction management from read-only code paths so the dependency uses straightforward `Session` semantics, only mutating state (and committing) when refreshing sessions or updating API key usage.
3. Update routes, CLI helpers, and tests to use the new dependencies while preserving existing behaviour and coverage for successful authentication and failure cases.

## Definition of done
- Authentication resolution is expressed through clear, composable dependencies without explicit `db.rollback()` calls on read-only paths.
- Tests demonstrate that session and API key authentication still succeed, invalid credentials still return the same HTTP errors, and audit events continue to fire when state changes.
