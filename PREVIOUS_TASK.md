# Current Task — Build the backend authentication baseline

## Objective
Stand up the first slice of ADE user management so the backend can authenticate requests with HTTP Basic credentials by default, mint browser-friendly sessions for the React UI, and optionally honour a standards-compliant OIDC single sign-on flow when environments toggle it on.

## Context absorbed from the repo
- ADE ships as a single Docker container with FastAPI, SQLite, and on-disk storage (`README.md`). The audience is internal teams that prize straightforward operations over cutting-edge infrastructure, so our auth plumbing must remain boring, observable, and easy to debug.
- ULIDs already back every table (`backend/app/models.py`), the event log captures every user-facing change, and docs stress deterministic behaviour. User records and session identifiers should follow the same conventions so monitoring and audit trails stay uniform.
- Existing routers are public except for `/health`. Once authentication lands we must protect configuration, document, job, and event endpoints without breaking automated scripts that will continue to use HTTP Basic.

## Design decisions (with rationale)
1. **Persist `users`, `sessions`, and `api_keys` tables using SQLAlchemy models.** ULID primary keys keep insert patterns append-friendly in SQLite and match the rest of the schema. Passwords are stored as Argon2id hashes (via `passlib.hash.argon2id`) with per-user salts; SSO identities map through immutable `sso_subject` + `sso_provider` fields. Sessions are opaque random tokens that are hashed at rest to tolerate cookie leaks. API keys stay out of scope for this task but the table lands now so we avoid a future breaking migration when automation needs long-lived credentials.
2. **Expose auth configuration solely through `ADE_` environment variables.** We add `auth_modes` (comma-separated: `basic`, `session`, `sso`), session TTL and cookie metadata, an admin email allowlist toggle, and OIDC settings. Startup validation fails fast if no modes are enabled, if SSO is requested without the minimum issuer/client/secret values, or if cookie/session settings are invalid. This mirrors the rest of the config module and keeps the docker image configurable without code edits.
3. **Prefer explicit service modules over “magic” dependencies.** A new `backend/app/auth/` package will hold:
   - `passwords.py` for hashing and verification helpers.
   - `sessions.py` to mint, persist, revoke, and validate hashed session tokens plus their expiry windows.
   - `sso.py` wrapping Authlib’s OIDC code-exchange and JWKS validation (pulling discovery documents with `httpx` and caching keys for the TTL).
   - `dependencies.py` defining a `CurrentUser` dependency. It checks for a valid session cookie first, then HTTP Basic credentials, and finally an `Authorization: Bearer` token when SSO is active. The first successful check attaches the user object to the request state for downstream logging.
   This structure mirrors existing `services/` modules: functions remain small, deterministic, and unit-testable.
4. **Bootstrap and maintain users through a tiny CLI.** We ship `python -m backend.app.auth.manage` commands for `create-user`, `reset-password`, `deactivate`, `list-users`, and `promote`. This avoids manual SQL for first-run setup, respects Argon2 hashing, and ensures operations can rotate credentials even when the API is down.
5. **Expose dedicated auth routes while keeping the rest of the API consistent.** New endpoints under `/auth` will handle:
   - `POST /auth/login`: exchange Basic credentials for a session cookie + JSON profile payload.
   - `POST /auth/logout`: revoke the session identified by the cookie.
   - `GET /auth/session`: refresh (extend) the cookie while confirming validity.
   - `GET /auth/me`: return the authenticated user’s profile and effective auth modes.
   - `GET /auth/sso/login` + `GET /auth/sso/callback`: optional OIDC redirect/callback pair that issues the same session cookie contract so the frontend never forks on auth type.
   All existing routers (except `/health`) adopt the `CurrentUser` dependency so requests fail with `401` + `WWW-Authenticate` headers when no mode succeeds.
6. **Emit rich events and request context.** Successful and failed logins (`user.login.succeeded` / `user.login.failed`), logouts, session refreshes, and CLI-driven account changes emit events through `services/events.py` with actor metadata. The dependency sets `request.state.auth_context` (user id, email, auth mode) so downstream handlers can forward actor info to services without re-validating credentials.
7. **Document and test thoroughly.** README, ADE_GLOSSARY, and `docs/` gain sections describing account provisioning, supported auth modes, cookie expectations, and SSO wiring steps. Pytest exercises cover password hashing invariants, login/logout flows, cookie expiry, config validation failures, SSO code exchange (using a mocked JWKS + discovery document), and the guarantee that `/health` remains public.

## Deliverables (what to implement now)
1. **Schema + models**
   - Add `User`, `UserSession`, and `ApiKey` SQLAlchemy models with enums for roles (`viewer`, `editor`, `admin`) and unique indexes on `email` and `(sso_provider, sso_subject)`.
   - Store session tokens as SHA-256 hashes with issued/expiry timestamps, last-seen metadata (`ip_address`, `user_agent`), and a nullable `revoked_at` marker.
   - Update `Base.metadata.create_all` imports, expose the models in `__all__`, and add factory/test fixtures that seed tables without introducing Alembic migrations yet.

2. **Configuration surface**
   - Extend `Settings` with auth-related fields (`auth_modes`, `session_cookie_name`, `session_ttl_minutes`, `session_cookie_secure`, `session_cookie_domain`, `sso_client_id`, `sso_client_secret`, `sso_issuer`, `sso_redirect_url`, `sso_audience?`).
   - Implement startup validation inside `main.lifespan` (or a dedicated `auth.startup.validate_settings`) that raises a `RuntimeError` on invalid combinations. Ensure Basic Auth remains enabled unless explicitly removed so existing scripts keep working after upgrade.

3. **Auth services + dependencies**
   - Implement password hashing/verification helpers with timing-safe comparisons.
   - Provide `issue_session`, `get_session`, `revoke_session`, and `touch_session` helpers that operate with database transactions and deterministic token hashing.
   - Implement OIDC helpers that fetch discovery metadata once per issuer, retrieve & cache JWKS keys, verify ID tokens (`nonce`, `aud`, `iss`, `exp`), and map tokens back to ADE users (auto-provision optional, disabled by default to keep control explicit).
   - Implement `CurrentUser` and `require_admin` dependencies with structured exceptions that translate to FastAPI `HTTPException` responses.

4. **Routes + wiring**
   - Create `backend/app/routes/auth.py` covering login/logout/session/me/SSO endpoints, returning Pydantic response schemas.
   - Mount the router in `main.py`, add middleware to set cookies (HttpOnly, Secure configurable, SameSite `lax`), and update existing routers to depend on `CurrentUser`.
   - Ensure CLI and background tasks reuse the same helpers rather than duplicating logic.

5. **Events & logging**
   - Update `services/events.record_event` call sites (and add new ones) so login/logout/session refresh events carry `actor_type="user"`, the ADE user id, and request identifiers when available.
   - Ensure audit trails for CLI actions include `actor_type="system"` plus whichever operator email is supplied at invocation.

6. **Docs + tests**
   - Expand documentation with setup guides, `.env` examples, and operational notes (password resets, session revocation, failure modes).
   - Write pytest suites for: password hashing; login success/failure via Basic; session reuse/expiry; SSO callback using mocked JWKS; auth-required enforcement across routers; CLI bootstrap flows. Add fixtures for seeding a default admin user.

## Out of scope / deferred decisions
- Frontend login/logout experiences (the UI will be addressed after the backend contract stabilises).
- Role-based access control per endpoint beyond the admin requirement for CLI or future management routes.
- Account invitations, email verification, or password-reset emails (future enhancement once mail infrastructure exists).
- Automatic SSO user provisioning (left disabled until operations explicitly opt in and we agree on attribute mapping).

## Acceptance criteria
- Service refuses to boot when `auth_modes` resolves to an empty set or when `sso` is configured without issuer/client/secret/redirect values.
- Authenticated requests using HTTP Basic receive session cookies (when sessions are enabled) that unlock protected endpoints; unauthenticated requests return `401` with accurate `WWW-Authenticate` headers for the enabled modes.
- SSO-enabled environments successfully execute an OIDC code exchange in tests, validating the ID token signature and mapping it to an active ADE user.
- Login, logout, failed login, session refresh, and CLI user management events appear in the `events` table with populated actor metadata ready for timeline views.
