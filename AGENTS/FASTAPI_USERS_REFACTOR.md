# FastAPI Users Refactor Assessment

## Summary
- ADE currently maintains a bespoke authentication stack covering password login, cookie-based sessions with CSRF, refresh rotation, API keys, service accounts, and OIDC SSO flows. The bulk of this logic lives in `app/auth/service.py:130`, `app/auth/router.py:29`, and supporting modules.
- `fastapi-users` can replace the core password login/session issuance pieces, but it does not natively handle ADE-specific requirements such as double-submit CSRF cookies, hashed API keys, service-account restrictions, or the existing OIDC flow.
- A migration would therefore be a partial adoption: we could swap in `fastapi-users` for credential validation and session transport, yet large portions of the surrounding surface would remain custom. The overall code savings are material but nowhere near a full removal of `app/auth/service.py`.

## Benefits of the bespoke stack
- Cookie-first session handling is tuned for our SPA: we mint access+refresh JWT cookies, surface CSRF tokens, and mirror the contract captured in the auth design review (`app/auth/service.py:236`, `app/auth/service.py:314`, `app/auth/service.py:379`, `docs/auth-design-review.md:1`).
- API keys are fully owned: we generate prefix+secret pairs, hash the secret, and persist rich audit metadata on every use, which keeps machine access deterministic (`app/auth/service.py:503`, `app/auth/service.py:543`, `app/auth/repository.py:12`).
- Service accounts and admin bootstrap are first-class concerns, letting us enforce "no password" rules, count admins, and gate initial setup without third-party assumptions (`app/users/models.py:44`, `app/users/models.py:90`, `app/users/repository.py:56`, `app/auth/service.py:156`).
- OIDC SSO is deeply customised (PKCE, JWKS cache, provider metadata), so various enterprise IdPs can be supported without waiting on upstream changes (`app/auth/service.py:563`, `app/auth/service.py:742`, `app/auth/service.py:780`).

## Known weaknesses / risks
- The auth service remains a monolith (788 LoC) that re-implements sensitive primitives such as JWT issuing and CSRF enforcement, increasing review and maintenance overhead (`app/auth/service.py:130`).
- We maintain our own cryptography pipeline (scrypt hashing, manual JWT decode), which must be audited for timing, parameter, and upgrade issues (`app/auth/security.py:53`, `app/auth/security.py:116`).
- The bespoke SSO and HTTPX interactions pull in network and token-handling complexity that few teammates are familiar with, raising on-call risk (`app/auth/service.py:563`, `app/auth/service.py:780`).
- Supporting the stack requires a broad test surface (300+ line module) plus CLI pathways, so every behaviour change forces multi-touch updates (`tests/modules/auth/test_auth.py:1`, `app/cli/commands/api_keys.py:47`).

## Capabilities currently unique to the custom stack
- Double-submit CSRF baked into every mutating request, bound to ADE's cookie names, allows the frontend to stay stateless and secure without extra middleware (`app/auth/service.py:314`, `app/auth/service.py:379`, `frontend/src/api/auth.ts:10`).
- Session-aware permission checks can read the enriched `ServiceContext` and custom decorator to combine user, workspace, and permission data—fastapi-users would only recover the user (`app/core/service.py:42`, `app/auth/security.py:182`).
- Detailed API-key telemetry (last seen IP/user agent) feeds auditing and throttling decisions that generic libraries rarely expose (`app/auth/service.py:543`, `app/auth/repository.py:32`).
- Initial setup flow coordinates database state and admin creation atomically, ensuring ADE can ship without pre-provisioned users (`app/auth/service.py:156`, `app/system/repository.py:13`).

## Current custom implementation
| Concern | Implementation | Notes |
| --- | --- | --- |
| Data model | `User` ULID model with role, service-account flag, OIDC identity fields, and validation hooks (`app/users/models.py:37`). | Uses ULID primary keys and stores canonical email + display metadata. |
| Persistence helpers | `UsersRepository` and `APIKeysRepository` for lookups/creation (`app/users/repository.py:15`, `app/auth/repository.py:12`). | Multiple bespoke queries plus count-admin helper for initial setup. |
| Business logic | `AuthService` (788 LoC) orchestrates passwords, cookies, API keys, SSO, and initial admin setup (`app/auth/service.py:130`). | Includes custom scrypt hashing, JWT minting, CSRF enforcement, API key hashing, PKCE/OIDC clients, and state storage. |
| HTTP layer | Class-based router exposing login/refresh/logout/me/api-key/SSO endpoints (`app/auth/router.py:29`). | CSRF-aware cookies, admin-only issuance, and redirects. |
| Middleware/deps | Dependencies resolve principals from cookies/bearer/API key (`app/auth/dependencies.py:27`) and apply permission decorator (`app/auth/security.py:182`). | Double-submit CSRF enforced for non-idempotent requests. |
| Supporting flows | Initial admin bootstrap via `SystemSettings` (`app/auth/service.py:154`) and CLI API key helpers (`app/cli/commands/api_keys.py:47`). | Tests exercise these paths (`tests/modules/auth/test_auth.py:1`). |
| Frontend contract | SPA expects cookies `ade_session`/`ade_refresh`/`ade_csrf` and propagates CSRF header (`frontend/src/api/auth.ts:10`, `frontend/src/api/auth.ts:93`). | Any backend change must keep contract or update the client.

The combined custom surface across `app/auth` and `app/users` is roughly 1,849 LoC.

## What fastapi-users provides out of the box
- SQLAlchemy user model mixins (`SQLAlchemyBaseUserTable`) and async repositories with password hashing and activation states.
- Authentication backends for JWT tokens and cookie transport with refresh support.
- Dependency helpers to retrieve the current user (with `is_superuser` convenience) and built-in routers for registration, password reset, verification, and OAuth (limited providers).
- Password hashing via passlib (bcrypt) with configurable password helper.

## Gap analysis
| ADE requirement | fastapi-users support | Gap / adaptation needed |
| --- | --- | --- |
| ULID primary keys & extra fields (service accounts, display name, OIDC subject) | Custom `SQLAlchemyBaseUserTable[str]` subclass can store extra columns. | Need to override default schemas/pydantic models; migrate existing tables or provide Alembic scripts. |
| Scrypt password hashes | Library defaults to bcrypt. | Either migrate hashes to bcrypt or implement a custom `PasswordHelper` that reproduces scrypt to avoid forced resets. |
| Double-submit CSRF with dedicated cookie/header | Cookie backend does not implement CSRF. | Would need custom transport/middleware to preserve CSRF guarantees or accept weaker protection. |
| Dual cookie issuance (access + refresh) aligned with current cookie names | Cookie backend supports only one cookie per backend. | Require custom transport to mirror `ade_session`/`ade_refresh` separation or rework frontend contract. |
| API keys hashing + auditing (`app/auth/service.py:503`) | Not provided. | Must keep existing API key repository/service/routers regardless of migration. |
| Service-account password restrictions (`app/users/models.py:60`) | No concept of service accounts. | Need custom validators and conditional login hooks. |
| Initial admin setup transaction (`app/auth/service.py:154`) | Not provided. | Keep custom setup flow or wrap library registration with ADE logic. |
| CLI integration (`app/cli/commands/api_keys.py:47`) | N/A. | Still required; dependent on AuthService or replacement service layer. |
| OIDC SSO with PKCE, JWKS validation (`app/auth/service.py:563`) | Library offers OAuth endpoints but not PKCE/JWKS verification. | Would need to port or re-implement SSO on top of fastapi-users OAuth adapter. |
| Permission decorator / workspace context (`app/auth/security.py:182`) | Only exposes user dependency. | Access control helper remains custom; unaffected. |
| Comprehensive tests relying on current endpoints (`tests/modules/auth/test_auth.py:1`) | Library ships generic tests only. | Need to rewrite suite against new routes/contracts.

## Migration work breakdown (high level)
1. **Foundations**
   - Introduce `fastapi-users` dependency and configure SQLAlchemy user manager using existing `AsyncSession` pattern.
   - Build custom user schemas mirroring ADE fields (service-account flag, display/description, OIDC metadata).
   - Decide on password strategy (hash migration vs custom helper).
2. **Session/auth backend**
   - Implement cookie/JWT backend that issues the three-cookie bundle or renegotiate the frontend contract and update `frontend/src/api/auth.ts` accordingly.
   - Recreate CSRF enforcement (possibly via Starlette middleware) if we retain cookie-based SPA security.
3. **Route integration**
   - Replace `/api/auth/login`/`refresh`/`logout`/`me` endpoints with fastapi-users equivalents or wrappers, preserving the openapi and response payloads expected by the frontend/tests.
   - Keep API key issuance/list/revoke routes but refactor them to consume the new user manager.
   - Bridge initial setup flow so the first admin creation still records system settings.
4. **SSO**
   - Evaluate whether fastapi-users OAuth helpers can host the existing OIDC flow; otherwise, keep the present implementation while delegating password-only paths to the library.
5. **Downstream adjustments**
   - Update dependencies (`bind_current_principal`) to rely on fastapi-users authentication backends while preserving bearer/API-key logic.
   - Modify CLI and tests to target the revised services and endpoints.
6. **Data migration**
   - Craft Alembic migrations if the user table schema changes (column names, constraints) and a strategy for re-hashing existing passwords if algorithms diverge.

## Estimated code impact
- Likely removable/replaced logic: password verification + JWT issuance (~300 LoC inside `app/auth/service.py:244-354` and `app/auth/router.py:79-144`).
- Code that must remain or be heavily rewritten: API key management, SSO helpers, CSRF validation, initial setup, repositories, tests (~950+ LoC).
- Expected net reduction: approximately 400–600 LoC after accounting for new glue code, at the cost of adding a third-party dependency and bespoke integration layer.

## Risks & open questions
- **Security regression**: downgrading or misconfiguring CSRF/session handling would undo the deliberate protections documented in `docs/auth-design-review.md:1`.
- **Password compatibility**: forcing all users to reset passwords or executing a bulk re-hash is operationally expensive; implementing scrypt inside fastapi-users increases maintenance burden.
- **Complexity displacement**: significant glue code will be required to bend fastapi-users to ADE's cookie + API key + SSO shape, reducing the purported simplicity gains.
- **Testing effort**: the 300+ lines of auth tests (`tests/modules/auth/test_auth.py:1`) must be reauthored and validated against the new stack.
- **Frontend contract**: any deviation from the current cookie names or CSRF flow requires coordinated frontend updates and possibly workspace permission checks elsewhere.

## Recommendation / next steps
- Proceed only if we value standardized user management and future features (email verification, password reset) enough to justify the migration cost.
- If we continue, start with a proof-of-concept branch that wires fastapi-users for password login while leaving SSO/API keys untouched, measuring the real code delta and behaviour.
- Alternatively, invest incremental effort in the existing stack (e.g., extracting smaller modules, improving tests) to gain clarity without a heavy migration.








