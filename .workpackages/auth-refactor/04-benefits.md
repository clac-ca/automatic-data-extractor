## `.workpackages/auth-refactor/04-benefits.md`

```markdown
## 6. What this buys you (re the earlier performance discussion)

### 6.1. With auth enabled

* User resolution is clearly separated (`PasswordAuthService.resolve_user` feeding into `AuthService.resolve_user`), with lockout checks applied in one place.
* Lockout bookkeeping no longer calls `commit()` on each failed login; it uses a consistent pattern for failed-login updates (flush only, outer unit-of-work commits).
* SSO metadata/JWKS are cached per process, reducing repeated network calls on login.
* Session handling + CSRF are isolated and easy to profile/modify inside `SessionService`.
* API key authentication is encapsulated, avoids async lazy-loaded relationships, and is easier to audit and extend (e.g. key rotation, scoping).

Overall, the hot path for a typical authenticated request becomes:

1. Decode JWT or API key and resolve user/principal (read-only).
2. Evaluate permissions (via existing roles/permissions mechanisms).
3. Execute the business query.

### 6.2. With auth disabled (`settings.auth_disabled == True`)

* `DevIdentityService.ensure_dev_identity` **only** runs the heavy path (sync registry + assign global admin) once per process.
* Subsequent requests do a simple user fetch + principal ensure – no more per‑request global role assignment against the slow SQL server.
* The rest of the stack sees a normal `AuthenticatedIdentity`, so you don’t need any special-case logic elsewhere.

### 6.3. Maintainability & future changes

Because responsibilities are split:

* You can change the password hashing parameters, JWT claims, or CSRF behaviour without touching SSO or API key code.
* You can introduce additional auth modes (e.g. “in-memory dev identity with no DB at all”, or “service-to-service JWTs”) by adding new subservices and exposing them via `AuthService`.
* You can further optimise performance (e.g. introducing a shared `httpx.AsyncClient` for IdP calls, or adding cross-request caching for user/principal) without disturbing the HTTP API surface.

If you want to go further (e.g. introduce an `AuthMode` in `Settings`, return an entirely in‑memory identity for dev bypass, or add cross‑request caching for user/principal), this layout makes that much easier.

If you want, the next step after this refactor can be to sketch the updated `shared.dependency.get_current_identity` implementation and add focused tests for it, so auth behaviour is fully covered end-to-end.