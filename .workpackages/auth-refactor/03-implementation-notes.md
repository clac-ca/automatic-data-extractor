## `.workpackages/auth-refactor/03-implementation-notes.md`

```markdown
## 3. Data model / schema

Your existing schema for auth‑related tables is already solid:

* `users`, `user_credentials`, `user_identities` – fine.
* `api_keys` – `token_prefix` + `token_hash` with unique constraints; `user_id` index – fine.
* RBAC tables (`roles`, `role_assignments`, `permissions`, `principals`) – no changes needed for this re‑architecture.

**No schema changes are required** for this work package.

If you later want micro‑optimisations (e.g. partial indexes on non‑revoked API keys or role assignments), you can add dedicated migrations.

---

## 4. Files & responsibilities

We keep the same file names but update contents where appropriate:

* `features/auth/__init__.py`
  * Export key types (`AuthService`, `AuthenticatedIdentity`, `SessionTokens`, `APIKey`, etc.).
* `features/auth/models.py`
  * Same `APIKey` model (no behavioural changes).
* `features/auth/repository.py`
  * Slightly cleaned up, with an internal `ApiKeyRepository` implementation (you can keep `APIKeysRepository` as a legacy alias if you want).
* `features/auth/security.py`
  * Unchanged: password hashing, JWT helpers, token payload dataclass.
* `features/auth/utils.py`
  * Unchanged: `normalise_email`, `normalise_api_key_label`.
* `features/auth/service.py`
  * All the reorganised business logic lives here:
    * `AuthService` façade.
    * `SessionService`, `PasswordAuthService`, `ApiKeyService`, `SsoService`, `DevIdentityService`.
* `features/auth/schemas.py`
  * Unchanged Pydantic DTOs.
* `features/auth/router.py`
  * Uses `AuthService` as a dependency; endpoints remain semantically unchanged.
* `shared/dependency.py`
  * Updated to resolve identities and enforce auth/CSRF solely through `AuthService`.
* `features/auth/tests/test_service.py`
  * Tests for `AuthService.is_secure_request` and any additional behaviours you choose to cover.

---

## 5. Code listings and file notes

The original “Full code listings” section from the previous work package has been split into real files under `./code/` so you can apply them directly:

* `code/apps/ade-api/src/ade_api/features/auth/__init__.py`
* `code/apps/ade-api/src/ade_api/features/auth/models.py`
* `code/apps/ade-api/src/ade_api/features/auth/repository.py`
* `code/apps/ade-api/src/ade_api/features/auth/security.py`
* `code/apps/ade-api/src/ade_api/features/auth/utils.py`
* `code/apps/ade-api/src/ade_api/features/auth/service.py`

(Original note: “Below is a full replacement for each auth file you showed. You can paste these into a work package and have an agent apply them.”)

### Additional notes from the package

* `apps/ade-api/src/ade_api/features/auth/schemas.py`
  * Keep your current `schemas.py` verbatim.
* `apps/ade-api/src/ade_api/features/auth/router.py`
  * Behaviour (API surface, status codes, payloads) should remain the same.
  * The main change is that the router now depends on `AuthService` as a façade and lets it delegate to subservices internally. Dev identity no longer hammers the DB on every request when `auth_disabled` is on.
* `apps/ade-api/src/ade_api/shared/dependency.py`
  * This module is where `auth_disabled` vs. “real” auth is decided:
    * In dev mode, call `AuthService.ensure_dev_identity()`.
    * Otherwise, resolve session cookies, bearer tokens, or API keys using `AuthService`.
  * This is also where CSRF is enforced for mutating requests via `AuthService.enforce_csrf(...)`.
* `apps/ade-api/src/ade_api/features/auth/tests/test_service.py`
  * Your existing tests still make sense, because `AuthService.is_secure_request` delegates to `SessionService.is_secure_request` and the semantics have not changed.
  * You may add more tests as you implement subservices (e.g. for lockout, dev identity, and API key behaviour).

---

## 6. Micro-level logic changes to apply during refactor

These are small, targeted fixes that clean up issues identified in the existing implementation:

* **Lockout helper cleanup**
  * Simplify `_lockout_error` to remove unreachable branches while preserving current behaviour and error payload shape.
  * Ensure the lockout logic is reused consistently from both password login and SSO user resolution.

* **Failed-login bookkeeping**
  * Remove `commit()` and `refresh()` calls from the failed-login path (e.g. `_record_failed_login`).
  * Use `flush()` only where required; leave transaction management to the outer request-scoped unit-of-work.

* **API key user resolution in async**
  * Avoid relying on accessing `record.user` in async mode if that relationship is not guaranteed to be eagerly loaded.
  * Either:
    * make `ApiKeyRepository.get_by_prefix` eager-load `APIKey.user`, or
    * always fetch the user through `UsersRepository` using `record.user_id`.

* **SSO token exchange client-auth**
  * In `_exchange_authorization_code`, pick a single client authentication method with the IdP (HTTP Basic **or** `client_secret` in the body) and stick to it.
  * Do not send the client secret in both places simultaneously.

* **Private host detection**
  * The existing `_is_private_host` logic is generally fine. If you touch it, keep the behaviour the same (blocking obvious private/loopback/local hosts) but feel free to remove small redundancies (e.g. duplicate checks for `127.0.0.1`).

These changes are small but ensure the refactored code is both cleaner and more predictable than the original.