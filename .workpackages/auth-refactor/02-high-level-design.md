## `.workpackages/auth-refactor/02-high-level-design.md`

```markdown
## 2. High‑level design

### 2.1. New service layout

Instead of `AuthService` being a “god class” doing everything, we split responsibilities:

* `SessionService`
  * JWT signing/verification (access & refresh).
  * Cookie issuing/clearing.
  * CSRF enforcement.
  * `is_secure_request`.
  * No direct transaction control; it never calls `commit()` / `rollback()` itself.
* `PasswordAuthService`
  * Email/password login.
  * Lockout & failed login tracking.
  * Resolving users from JWT payloads (read-only lookup + lockout checks).
  * Uses `flush()` where needed but leaves commit/rollback to the outer unit-of-work.
* `ApiKeyService`
  * Issuing & revoking API keys.
  * Authenticating API keys and creating `AuthenticatedIdentity`.
  * Touching `last_seen_*` on API keys (rate-limited by settings).
  * Resolving users without relying on async lazy-loaded relationships (no implicit IO on `record.user`).
* `SsoService`
  * OIDC discovery & JWKS fetch (with caching and TTL).
  * SSO login challenge & callback.
  * SSO user provisioning / conflict handling.
  * Uses a consistent HTTP client strategy (per-request clients for now; could be upgraded to a shared client later).
* `DevIdentityService`
  * Dev identity for `auth_disabled` mode.
  * Ensures dev user/admin role **once**, then cheap per‑request path.
* `AuthService` (façade)
  * Wires the above with a shared `AsyncSession` and `Settings`.
  * Exposes the methods the rest of the app uses (`authenticate`, `start_session`, `extract_session_payloads`, `prepare_sso_login`, `ensure_dev_identity`, etc.), delegating internally.
  * Keeps service code free from explicit `commit()` / `rollback()` calls; the session dependency owns transaction boundaries.

`AuthService` is the **only** entry point that routers and shared dependencies should talk to. Everything else is an implementation detail.

---

### 2.2. Dev identity (`auth_disabled`) performance fix

**Today** (before refactor): every request with `AUTH_DISABLED=true` calls a heavy path against the DB:

* `ensure_dev_identity` → `sync_permission_registry` + `assign_global_role_if_missing` + `ensure_user_principal`.

On the slow SQL Server this costs 1–2s per request, even though the business queries are fast.

**New behaviour**:

* `DevIdentityService` caches the dev user ID and a `_dev_setup_done` flag in module‑level state (per process).
* On the **first** call:
  * Get or create dev user.
  * Ensure `is_active` and `display_name`.
  * Sync permission registry.
  * Assign global admin role if missing.
  * Ensure principal.
* On **subsequent** calls:
  * Fetch dev user by ID (cheap read).
  * Ensure principal (cheap; just returns existing in normal cases).
  * No registry sync or global role assignment.

So even if you accidentally use `auth_disabled` on the slow prod DB, you only pay the heavy cost **once per process**, not on every request.

**Best practice** (recommended):

* Use `auth_disabled` (dev identity) **only in local dev**.
* In prod/staging, set `auth_disabled=False` and use real auth (password/SSO/API keys).

---

### 2.3. Identity resolution & shared dependencies

The existing `shared.dependency` module exposes helpers like:

* `get_current_identity`
* `require_authenticated`
* `require_csrf`
* `require_global(...)`

After the refactor:

* `get_current_identity` will:
  * In `auth_disabled` mode: call `AuthService.ensure_dev_identity()` and return that.
  * Otherwise: look for session cookies, bearer tokens, or API keys and resolve the identity via `AuthService` (sessions and `resolve_user`, or `authenticate_api_key`).
* `require_authenticated` becomes a thin wrapper on top of `get_current_identity`.
* `require_csrf` calls into `AuthService.enforce_csrf(...)` for mutating requests.

This keeps **all** auth/identity decisions in one place (`AuthService`) and makes dependencies easier to reason about.

---

### 2.4. SSO / OIDC caching strategy

`SsoService` introduces lightweight, in-process caching:

* OIDC discovery document (`authorization_endpoint`, `token_endpoint`, `jwks_uri`) is cached with a TTL (e.g. 10 minutes).
* JWKS responses are cached **per jwks_uri** with their own TTL.
* On expiry, `SsoService` transparently re-fetches the metadata/JWKS.

Important details:

* Only algorithms in `{"RS256","RS384","RS512","ES256"}` are allowed.
* Nonces are validated, and audience/issuer checks follow the settings.
* Errors from the IdP are mapped to reasonable HTTP status codes and messages (400/502).
* `_exchange_authorization_code` uses a single, clearly chosen client-auth method (either HTTP Basic or `client_secret` in the body), not both at once.

This reduces network chatter on each SSO login without changing the on‑wire SSO behaviour.

---

### 2.5. Error semantics & compatibility

Even though Python‑level backwards compatibility is not a goal, we still want **behavioural** compatibility where it matters:

* HTTP status codes for existing error conditions (invalid credentials, locked account, invalid SSO response, invalid CSRF, etc.) should remain the same.
* Error messages and detail payloads may be slightly cleaned up, but should not confuse existing clients (frontends, logs, alerts).
* The shape of successful responses (`SessionEnvelope`, `BootstrapEnvelope`, `APIKeyIssueResponse`, etc.) stays the same.

If you must change an error detail structure, document it explicitly in this workpackage and adjust the frontend/backend callers accordingly.