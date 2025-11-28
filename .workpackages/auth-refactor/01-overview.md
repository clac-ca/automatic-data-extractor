## `.workpackages/auth-refactor/01-overview.md`

````markdown
> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (there shouldn’t be any `{{LIKE_THIS}}` left — they’ve all been filled in here) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

* [x] Implement new `AuthService` façade and internal subservices (`SessionService`, `PasswordAuthService`, `ApiKeyService`, `SsoService`, `DevIdentityService`) in `service.py`
* [x] Refactor dev-identity (`auth_disabled` mode) to use `DevIdentityService` and remove per-request registry sync / global-role writes
* [x] Refactor session / password / API key / SSO logic to use subservices and update `router.py` to depend on `AuthService`
* [x] Update shared dependencies (`shared.dependency.py`) and `require_*` helpers to resolve identities via `AuthService` (including CSRF + session payload paths)
* [x] Update tests for auth (`tests/features/auth/test_service.py` and any others) to target the new architecture and keep them green
* [x] Standardise transaction boundaries so auth services do **not** call `commit()` / `refresh()` in hot paths (failed-login / lockout helpers should use `flush()` only and rely on the outer unit-of-work to commit)
* [x] Ensure API key auth does **not** rely on async lazy-loaded relationships (avoid implicit IO on `record.user`; use repository calls or eager loading instead)

> **Agent note:**
> Add or remove checklist items as needed. Keep brief status notes inline, e.g.:
> `- [x] Implement new AuthService façade — 123abc4`

---

# Re‑architect ADE Auth & Identity System

## 1. Objective

**Goal:**
Re‑architect the ADE authentication system so it follows a clean, standard FastAPI/SQLAlchemy architecture, eliminates per‑request dev-identity DB writes, and centralises auth logic behind a single `AuthService` façade — **without** worrying about Python‑level backwards compatibility.

You will:

* Introduce focused internal services for sessions, password auth, API keys, SSO, and dev identity inside `service.py`, and compose them via a single `AuthService`.
* Refactor the auth router and shared dependencies to depend on `AuthService` rather than ad‑hoc helpers and dev-identity shortcuts.
* Preserve the existing database schema while tightening the auth hot paths to be read‑only and cache-friendly wherever possible.

The result should:

* Avoid slow per‑request dev-identity/role setup when `auth_disabled=True`, even on a slow SQL Server.
* Be easy to navigate and extend: clear separation of concerns, predictable naming, and a simple mental model (`AuthService` is the main entry point for all auth concerns).

---

## 2. Context (What you are starting from)

The existing auth code lives under `ade_api/features/auth/` and related dependency modules. It works but has several architectural and performance issues, especially around dev identity and SSO.

**Existing structure:**

* `apps/ade-api/src/ade_api/features/auth/`
  * `__init__.py` – re‑exports routers.
  * `models.py` – `APIKey` ORM model.
  * `repository.py` – `APIKeysRepository` with basic CRUD.
  * `schemas.py` – Pydantic models for setup, login, session, API keys, provider discovery.
  * `security.py` – password hashing, JWT, API key hashing, CSRF hashing.
  * `service.py` – a large `AuthService` class with many responsibilities (password login, dev identity, SSO, session cookies, CSRF, API keys, etc.).
  * `router.py` – endpoints for setup, session, `/me`, API keys, SSO.
  * `utils.py` – email and API key label normalisation.
  * Tests under `apps/ade-api/tests/features/auth/` (e.g., `test_service.py`).

**Current behavior / expectations:**

* **Dev identity (`auth_disabled=True`)**:
  * Every request that needs an identity goes through a dev-identity path that:
    * ensures the dev user exists,
    * runs `sync_permission_registry`,
    * checks/assigns global admin role,
    * ensures a principal.
  * This hits the DB (and the slow SQL Server) on every request.  When auth_disabled = True we essentially just want all routes to not require auth.
* **Auth-enabled mode**:
  * Password login verifies credentials, updates failed login counters and lockouts, and writes DB state inside the hot path.
  * Session management (JWT + cookies) is mixed into the main `AuthService`.
  * SSO/OIDC logic (discovery, token exchange, JWKS, user provisioning) lives in `AuthService` and re-fetches metadata/JWKS more often than necessary.
  * API keys are issued via `AuthService` using `APIKeysRepository`.
* **Shared dependencies** (in `shared.dependency.py`):
  * Resolve the current identity, enforce authentication, CSRF, and roles by manually calling pieces of `AuthService` as well as some dev-identity logic.

**Known issues / pain points with the legacy code:**

* **Performance**:
  * With `ADE_AUTH_DISABLED=true` on a slow SQL Server, each request does expensive work:
    * dev user creation/lookup,
    * registry sync,
    * global role assignment,
    * principal ensure.
  * In logs you’ve seen `/bootstrap` and `/documents` dominated by this dev-identity/role path even though the business queries are fast.
* **Monolithic `AuthService`**:
  * Many responsibilities in a single class make it hard to understand, test, or swap out individual behaviours (like session handling vs. SSO).
* **SSO metadata/JWKS fetching**:
  * OIDC discovery and JWKS fetching do not have a clearly defined, cross-request cache.
  * There’s no explicit separation between “remote IdP operations” and “local user provisioning”.
* **Tight coupling to environment toggles**:
  * `auth_disabled` is implemented by making the dev-identity path emulate a logged-in user, but it still touches the DB heavily.
* **Inconsistent transaction boundaries and lazy-loads**:
  * Some helpers (e.g. failed-login bookkeeping) call `commit()` / `refresh()` inside the service, while most other code relies on an outer unit-of-work.
  * API key auth reads `record.user` on ORM instances, which can trigger lazy IO in async mode if not carefully loaded.

**Hard constraints (APIs, platforms, consumers):**

* API surface of HTTP endpoints should remain semantically similar (same URLs and general behaviour).
* DB schema is defined by `0001_initial_schema`:
  * You *can* change indexes later if needed, but this work package assumes **no schema change**.
* The system uses:
  * FastAPI
  * Pydantic
  * SQLAlchemy (async)
  * JWT + scrypt password hashing
* Other parts of the code base (e.g. workspaces, documents, system settings) depend on:
  * `get_current_identity` and `require_authenticated` semantics.
  * `BootstrapEnvelope` structure.

---

## 3. Target architecture / structure (ideal)

We want a **layered** auth module where:

* All HTTP‑level logic goes through **one façade** (`AuthService`).
* Internal auth concerns are **separated**:
  * sessions & CSRF,
  * password login & lockout,
  * dev identity,
  * API keys,
  * SSO/OIDC.
* Dev identity is an **explicit service** that performs heavy work only once per process, not per request.
* SSO uses **cached** metadata/JWKS across requests.

```text
apps/ade-api/
  src/
    ade_api/
      features/
        auth/
          __init__.py          # re-export routers / types
          models.py            # APIKey ORM model
          repository.py        # ApiKeyRepository
          schemas.py           # Pydantic DTOs for auth flows
          security.py          # JWT, password hashing, API key/CSRF hashing
          service.py           # AuthService façade + internal services:
                               #   SessionService
                               #   PasswordAuthService
                               #   ApiKeyService
                               #   SsoService
                               #   DevIdentityService
          router.py            # FastAPI routes for setup, session, /me, api-keys, SSO
          utils.py             # Email / label normalisation helpers
      shared/
        dependency.py          # Uses AuthService to resolve identities & require auth
  tests/
    features/
      auth/
        test_service.py        # Tests for is_secure_request and other behaviours
`````

Key points:

* **AuthService**:

  * Single “entry point” the rest of the app should depend on.
  * Exposes stable methods like:

    * `authenticate`, `start_session`, `refresh_session`, `decode_token`,
    * `get_initial_setup_status`, `complete_initial_setup`,
    * `ensure_dev_identity`,
    * `get_provider_discovery`, `resolve_user`,
    * `issue_api_key_*`, `revoke_api_key`, `authenticate_api_key`,
    * `prepare_sso_login`, `complete_sso_login`.
  * Internally delegates to subservices.
* **Internal services**:

  * `SessionService` – token creation/decoding, cookies, CSRF, secure detection.
  * `PasswordAuthService` – email/password login + lockout logic + user resolution with lockout checks.
  * `ApiKeyService` – API key lifecycle & auth (no lazy loads in async; uses repository or eager-load patterns).
  * `SsoService` – OIDC discovery, PKCE, JWKS, SSO user resolution, caching.
  * `DevIdentityService` – dev user & principal provisioning in `auth_disabled` mode.

---

## 4. Design (for this workpackage)

### 4.1 Design goals

* **Clarity**
  Make auth behaviour easy to understand by grouping related concerns into small services and exposing a small, consistent façade.

* **Maintainability**
  Avoid a monolithic `AuthService` class that mixes unrelated responsibilities; make it easy to test and change dev identity, SSO, and API keys independently.

* **Scalability / performance**
  Ensure hot paths (especially in prod and in `auth_disabled` mode) are **read-only where possible**, avoid repeated registry/role writes, and introduce caching for SSO metadata/JWKS to minimise remote calls.

### 4.2 Key components / modules

* **`SessionService`** —
  Responsible for JWT token issuing, decoding, and cookie/CSRF handling.

  * Creates access/refresh tokens tied to a session ID and CSRF hash.
  * Applies and clears cookies with consistent paths/domains.
  * Validates CSRF tokens for mutating HTTP methods.
  * Provides `is_secure_request` using `X-Forwarded-Proto` + `scope["scheme"]`.
  * Does **not** call `commit()` / `rollback()` itself; it only mutates ORM state and relies on the outer unit-of-work.

* **`PasswordAuthService`** —
  Responsible for username/password login and account lockout behaviour.

  * Validates credentials against `UsersRepository`.
  * Applies lockout thresholds and durations based on settings.
  * Resets counters and timestamps on successful login.
  * Exposes a `get_lockout_error` helper used by SSO and `resolve_user`.
  * Resolves users from JWT payloads (read-only lookup + lockout checks).
  * Only calls `flush()` where necessary; **never** `commit()` / `refresh()` in its helpers.

* **`ApiKeyService`** —
  Responsible for API key lifecycle and authentication.

  * Generates prefix/secret pairs and hashed secrets.
  * Persists keys via `ApiKeyRepository`, attaches to users.
  * Checks expiry/revocation and hashes secrets on auth.
  * Touches last-seen metadata with configurable rate limiting.
  * Avoids async lazy-loads: when resolving the user for an API key, it uses repository methods (e.g. eager loading or separate user query) rather than relying on `record.user` triggering implicit IO in async mode.

* **`SsoService`** —
  Responsible for OIDC discovery, PKCE, token exchange, JWKS verification, and SSO user provisioning.

  * Caches OIDC metadata and JWKS across requests using class-level caches with TTL.
  * Prepares SSO login challenge (authorization URL, state token, PKCE verifier).
  * Verifies ID tokens with JWKS (`kid` + alg selection), enforcing nonce, issuer, audience.
  * Resolves or auto-provisions users (honouring `auth_sso_auto_provision`) and ensures they’re not locked out.
  * Uses a consistent HTTP client pattern (per-request clients for now; see §4.4) and centralised error handling.

* **`DevIdentityService`** —
  Responsible for dev identity when `auth_disabled=True`.

  * Creates/activates a dev user once per process.
  * Runs `sync_permission_registry` and assigns the global admin role **once**.
  * Ensures a principal and returns an `AuthenticatedIdentity` with `credentials="development"`.

* **`AuthService` façade** —
  Responsible for orchestrating all of the above and providing a simple interface for routers and dependencies.

  * Composes repositories (`UsersRepository`, `ApiKeyRepository`, `SystemSettingsRepository`) and all subservices.
  * Exposes high-level operations (login, session handling, setup, API keys, SSO, dev identity) without leaking low-level details.
  * Does **not** manage transactions itself; it assumes the FastAPI dependency that creates the `AsyncSession` is responsible for commit/rollback.

### 4.3 Key flows / pipelines

#### Flow 1 — Password login + session

**Name:** `Password login & session creation`

**Steps:**

1. `POST /auth/session` receives `LoginRequest` (email, password).
2. `AuthService.authenticate(...)` delegates to `PasswordAuthService.authenticate`:

   * Normalises email.
   * Fetches user by email.
   * Checks active status.
   * Runs `get_lockout_error`; if locked, returns 403 with structured detail.
   * Verifies password using `verify_password`.
   * Updates `last_login_at`, clears lockout state.
   * Uses `flush()` as needed; no `commit()` inside this flow.
3. `AuthService.start_session(user)`:

   * Calls `SessionService.issue_tokens(user)` to create:

     * `SessionTokens` bundle (access, refresh, CSRF, expiry times, max-ages).
4. `AuthService.is_secure_request(request)` decides whether cookies should be `secure=True`.
5. `AuthService.apply_session_cookies(response, tokens, secure=...)` writes the cookies.
6. Caller retrieves `UserProfile` and returns a `SessionEnvelope` containing profile and expiries.

#### Flow 2 — SSO login (OIDC) with caching

**Name:** `SSO/OIDC login`

**Steps:**

1. `GET /auth/sso/login`:

   * Calls `AuthService.prepare_sso_login(return_to=...)` → `SsoService.prepare_login`.
   * `SsoService`:

     * Loads cached OIDC metadata (or fetches it via discovery and caches it).
     * Generates `state`, `nonce`, `code_verifier`, `code_challenge`.
     * Normalises `return_to` against `server_public_url`.
     * Encodes state token (signed JWT) with TTL (`_SSO_STATE_TTL_SECONDS`).
   * Router sets `SSO_STATE_COOKIE` with state token, redirects to IdP.
2. `GET /auth/sso/callback?code=...&state=...`:

   * Reads `SSO_STATE_COOKIE` and passes `code`, `state`, `state_token` to `AuthService.complete_sso_login(...)`.
   * `SsoService.complete_login`:

     * Decodes `state_token`, checks `state`.
     * Exchanges code for tokens (`_exchange_authorization_code`).
     * Retrieves cached OIDC metadata (or refreshes).
     * Verifies `id_token` via JWKS (`_verify_jwt_via_jwks`), enforcing nonce, issuer, audience.
     * Resolves or auto-provisions a user via `_resolve_sso_user`:

       * Ensures not locked out (via `PasswordAuthService.get_lockout_error`).
       * Assigns `global-user` role on provision if configured.
     * Updates `last_login_at`, clears lockout counters.
   * Returns `SSOCompletionResult(user, return_to)`.
3. Router calls `AuthService.start_session(user)` and applies cookies as in password login.
4. Response is `SessionEnvelope` + optional `return_to` hint for the frontend.

#### Flow 3 — Dev identity (`auth_disabled=True`)

**Name:** `Dev identity setup & reuse`

**Steps:**

1. In `shared.dependency.get_current_identity`, when `Settings.auth_disabled=True`:

   * Call `AuthService.ensure_dev_identity()`.
2. `AuthService.ensure_dev_identity` delegates to `DevIdentityService.ensure_dev_identity`:

   * On **first call**:

     * Create or fetch dev user (using `auth_disabled_user_email` / `auth_disabled_user_name`).
     * Ensure active + display name.
     * Run `sync_permission_registry(force=True)`.
     * Assign `global-administrator` via a reusable helper (`_assign_global_role_if_missing_or_500`).
     * Ensure principal.
     * Cache `dev_user_id` and `_dev_setup_done=True` in process-local state.
   * On **later calls**:

     * Fetch user by cached ID; if missing, fallback to email.
     * Skip registry sync and global role assignment.
     * Ensure principal.
3. Returns `AuthenticatedIdentity(user, principal, credentials="development")` used for authorisation logic.

**Result:** in dev mode, expensive registry sync and global role writes happen once per process, not once per request.

#### Flow 4 — API key authentication

**Name:** `API key issuance and auth`

**Steps:**

1. `/auth/api-keys` (POST) → `AuthService.issue_api_key_for_user_id` or `issue_api_key_for_email`:

   * `ApiKeyService`:

     * Generates prefix/secret, hashes secret.
     * Persists via `ApiKeyRepository.create`.
     * Returns `APIKeyIssueResult` (includes raw `prefix.secret` to show once).
2. Requests authenticate via API key (e.g. header `Authorization: Bearer <key>` or `X-API-Key` depending on integration):

   * `AuthService.authenticate_api_key(raw_key)` delegates to `ApiKeyService.authenticate`.
   * Splits prefix/secret, looks up active key by prefix.
   * Validates not expired/revoked, hash matches.
   * Resolves the user **without** relying on async lazy-loads (use repository or eager loading).
   * Ensures principal.
   * Optionally touches last-seen metadata (bounded by `session_last_seen_interval`).
   * Returns `AuthenticatedIdentity(..., credentials="api_key")`.

### 4.4 Open questions / decisions

* **Where exactly to plug in dev identity?**
  **Decision:** `shared.dependency.get_current_identity` should call `AuthService.ensure_dev_identity()` when `auth_disabled=True`. All other code should treat the returned `AuthenticatedIdentity` the same way as real identities.

* **How should API key authentication be wired into the HTTP surface (headers)?**
  **Decision:** Leave existing behaviour as-is for now (whatever header/query pattern is already used in your app). When you refactor or add new API key-protected endpoints, route them through `AuthService.authenticate_api_key`.

* **Should we share an `httpx.AsyncClient` between SSO calls?**
  **Decision:** For this refactor, keep short-lived `AsyncClient` instances per network operation but rely on **metadata/JWKS caching** to avoid frequent network calls. If later profiling shows connection setup as a bottleneck, introduce a shared client using FastAPI startup/shutdown hooks and update this section to reflect the change.

> **Agent instruction:**
> If you end up changing any of these decisions (e.g. you introduce a shared `httpx.AsyncClient`), update this section and explain *why*.

---

## 5. Implementation & notes for agents

This section tells you *how* to implement the design above in this repo.

### 5.1 Coding standards / style

* Keep code **type-annotated** and mypy‑friendly.
* Follow existing project patterns:

  * Async SQLAlchemy with `AsyncSession`.
  * Dependency injection via `Depends(get_session)` and `Depends(get_settings)`.
  * Logging via `logging.getLogger(__name__)` and `log_context(...)`.
* Prefer small methods with descriptive names rather than long monoliths.
* Avoid prematurely optimising DB-level performance; we’re already addressing the main bottlenecks (dev identity, SSO metadata/JWKS).

### 5.2 Implementation steps (suggested order)

1. **Introduce subservices inside `service.py`**

   * Add `SessionService`, `PasswordAuthService`, `ApiKeyService`, `SsoService`, and `DevIdentityService` with the responsibilities described above.
   * Keep the logic consistent with the existing code paths (password verification, token creation, SSO flows, etc.).
   * For lockout bookkeeping in `PasswordAuthService`, **remove** any `commit()` / `refresh()` calls that exist today (e.g. in `_record_failed_login`) and rely on `flush()` plus the outer unit-of-work to commit.
   * Add `_assign_global_role_or_500` and `_assign_global_role_if_missing_or_500` helpers so multiple services can reuse them.

2. **Refactor `AuthService` into a façade**

   * Give `AuthService.__init__` a single responsibility: compose:

     * `UsersRepository`, `ApiKeyRepository`, `SystemSettingsRepository`,
     * the five subservices.
   * Expose public methods:

     * Dev identity: `ensure_dev_identity`.
     * Setup: `get_initial_setup_status`, `complete_initial_setup`.
     * Password auth: `authenticate`.
     * Sessions: `is_secure_request`, `start_session`, `refresh_session`, `decode_token`, `apply_session_cookies`, `clear_session_cookies`, `enforce_csrf`, `extract_session_payloads`.
     * Provider discovery & user resolution: `get_provider_discovery`, `resolve_user`.
     * API keys: `issue_api_key_*`, `list_api_keys`, `paginate_api_keys`, `revoke_api_key`, `authenticate_api_key`.
     * SSO: `prepare_sso_login`, `decode_sso_state`, `complete_sso_login`.

3. **Update `router.py` to use `AuthService` as the DI boundary**

   * Add a small helper `get_auth_service(session, settings) -> AuthService`.
   * Update all routes to take `auth: Annotated[AuthService, Depends(get_auth_service)]` and call the façade methods.
   * Ensure behaviour of:

     * `/auth/providers`
     * `/setup/*`
     * `/bootstrap`
     * `/auth/session` (POST/GET/DELETE, `/auth/session/refresh`)
     * `/auth/me`
     * `/auth/api-keys*`
     * `/auth/sso/login`, `/auth/sso/callback`
       remains semantically equivalent (response shapes, status codes, and error messages should not regress).

4. **Refactor dev identity behaviour**

   * Implement `DevIdentityService.ensure_dev_identity` with:

     * cached `dev_user_id`,
     * `_dev_setup_done` flag,
     * one‑time `sync_permission_registry(force=True)` and global admin assignment.
   * Update `shared.dependency.get_current_identity` (or equivalent) to call `auth.ensure_dev_identity()` when `Settings.auth_disabled=True`.

5. **Wire in SSO metadata/JWKS caching**

   * In `SsoService`, add class-level caches:

     * `_metadata_cache`, `_metadata_expires_at`,
     * `_jwks_cache: dict[jwks_uri, (expires_at, keys)]`.
   * Use TTL (e.g. 10 minutes) to determine reuse vs. refresh.
   * Ensure JWKS parsing, key selection, and algorithm checks follow the constraints:

     * algorithms in `{"RS256","RS384","RS512","ES256"}` only.
     * Reasonable error messages and HTTP status codes.
   * While refactoring `_exchange_authorization_code`, choose a **single** client authentication strategy with the IdP (either HTTP Basic or `client_secret` in the POST body) instead of sending the secret in both places.

6. **Update `ApiKeyService` to avoid async lazy-loads**

   * Make sure `ApiKeyService.authenticate` either:

     * uses an API key repository method that eager-loads `APIKey.user`, or
     * explicitly fetches the user via `UsersRepository` from `record.user_id`.
   * Do **not** rely on accessing `record.user` triggering implicit IO in async mode.

7. **Update shared dependencies**

   * Refactor `shared.dependency.get_current_identity`, `require_authenticated`, `require_csrf`, and any API-key auth helpers to:

     * resolve identities via `AuthService` (sessions, bearer tokens, API keys, dev identity).
     * keep CSRF enforcement wired to `AuthService.enforce_csrf`.

8. **Update tests**

   * Update `tests/features/auth/test_service.py` to use the new `AuthService` where needed (e.g. `is_secure_request`).
   * Add tests if necessary to cover:

     * `DevIdentityService` behaviour (one‑time setup vs. repeated calls).
     * `PasswordAuthService.get_lockout_error` and `authenticate` logic.
     * `SessionService` cookie handling + CSRF enforcement (where feasible without spinning up the whole app).
     * `ApiKeyService.authenticate` path using a non-lazy way to resolve users.

9. **Clean up / final pass**

   * Remove any dead code paths in `service.py` that are no longer used after refactor.
   * Simplify `_lockout_error` to remove unreachable branches while preserving its behaviour and response shape.
   * Ensure `__all__` exports in `service.py`, `repository.py`, `schemas.py`, and `models.py` reflect the new public surface.
   * Confirm that you didn’t accidentally introduce circular imports (especially around `shared.dependency`).

### 5.3 Testing requirements

* **Unit tests**:

  * Existing auth tests must continue to pass (or be updated to the new structure).
  * Add focused unit tests for:

    * `SessionService.is_secure_request`.
    * `DevIdentityService.ensure_dev_identity` (behaviour before and after `_dev_setup_done` is set).
    * `PasswordAuthService.get_lockout_error` — test unlocked, locked, and edge cases.
    * `ApiKeyService.authenticate` — ensure it does not rely on async lazy-loads for `record.user`.

* **Integration / functional checks** (manual or automated):

  * Happy path for password login:

    * `POST /auth/session` → cookies set, `/auth/me` works.
  * Happy path for SSO login:

    * With a mocked IdP or test IdP, verify `/auth/sso/login` → `/auth/sso/callback` flow.
  * Dev mode (`auth_disabled=True`):

    * `/bootstrap` and `/workspaces/.../documents` should not exhibit the per-request 1–3s overhead tied to dev identity.

* **Performance sanity**:

  * On a slow DB, confirm the dev-identity path does heavy work only once per process (e.g., by logging or tracing).
  * Confirm SSO metadata/JWKS is not fetched for every SSO login when within the TTL window.

### 5.4 Performance / security notes

* Do **not** relax any of the existing security properties:

  * JWTs must still be signed with configured secret and algorithm.
  * CSRF checking must remain strict (cookie vs. header vs. payload hash).
  * Lockout behaviour must be enforced consistently for both password and SSO logins.

* Caching SSO metadata/JWKS:

  * Use modest TTLs (e.g. 10 minutes) to balance performance and key rotation agility.

* Dev identity:

  * This path is **only** for `auth_disabled` and should never be used in true prod deployments.
  * In prod-like environments, ensure `auth_disabled=False` and that real auth (password/SSO) is used.

---

You can now use this work package as the top‑level plan.
If you need to change the design as you implement (e.g. you discover a better way to structure SSO caching), **update this document first**, then proceed with code changes.
