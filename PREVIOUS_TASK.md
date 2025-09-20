# Current Task — Harden authentication flows and edge cases

## Objective
Round out the new authentication stack so it behaves predictably under the real-world scenarios operations will care about: RSA-signed SSO tokens, concurrent session usage, and CLI-driven account management.

## Context carried forward
- Passwords now rely on `hashlib.scrypt` so we can ship without extra wheels. Settings, docs, and tests all assume the tighter dependency footprint.
- `backend/app/auth/sso.py` verifies HS256 tokens in tests, but the production path will see RS256/ES256 ID tokens with kid rotation and discovery caching.
- `backend/app/auth/sessions.py` handles issue/touch/revoke logic, yet pytest only covers the happy path. Revocation + expiry races should stay deterministic so background jobs can lean on the same helpers.
- The CLI emits `user.*` events, but we do not assert their shape and we do not exercise deactivated user authentication failures.

## Deliverables
1. **SSO hardening**
   - Add pytest coverage for RS256 tokens using a generated keypair. Confirm JWKS caching honours `kid`, rejects unknown keys, and surfaces clear errors for expired or audience-mismatched tokens.
   - Ensure discovery caching respects the configured TTL (e.g. simulated second request reuses cached metadata instead of hitting `httpx.get`).
2. **Session service edge cases**
   - Add focused unit tests for `revoke_session` and `touch_session`, covering already-revoked tokens, expired sessions, and commit=False flows.
   - Fix any bugs uncovered by the new tests (e.g. ensure revoked sessions stay revoked when touched, touching expired sessions should return `None` upstream, etc.).
3. **CLI and dependency behaviour**
   - Extend CLI tests to assert the emitted events include `actor_type="system"`, the operator email, and the expected payload fields.
   - Add a regression test confirming deactivated users cannot authenticate via HTTP Basic or sessions.
4. **Docs & operational notes**
   - Update `docs/authentication.md` (and README if useful) with explicit notes on scrypt parameters, RS256 expectations, and how caching behaves.

## Acceptance criteria
- Pytest includes RS256 and caching checks for the SSO flow, plus deterministic unit tests for session helpers and CLI events.
- Revoked or expired sessions no longer show up as valid through the dependencies.
- Auth documentation reflects the new hashing approach and SSO nuances without referencing Argon2/passlib.
