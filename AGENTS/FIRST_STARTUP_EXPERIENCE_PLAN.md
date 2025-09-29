# First Startup Experience Plan

This document describes the simplest, most standard way to let the first operator create an admin account through the UI while keeping the codebase easy to reason about. The flow mirrors what many SaaS products do: a public status check, a one-time initial setup path that reuses our existing user creation service, and the regular login screen once an admin exists.

## Objectives
- Detect whether the database has an administrator account.
- Prompt unauthenticated visitors to create that first admin through the web UI only while none exist.
- Hand control back to the normal sign-in form immediately after initial setup succeeds.

## Data we need
- **`system_settings` table**: a single-row key/value table that already fits most FastAPI projects (`key` TEXT primary key, `value` JSONB/TEXT, `created_at`, `updated_at`).
- Store an `initial_setup.completed_at` timestamp (null until the initial admin is created). Keeping this flag alongside other system-wide settings means we do not introduce bespoke columns on the `users` table and lets us gate the initial setup route even if someone later deletes all admins.

## Backend plan
1. **Status endpoint**
   - Add `GET /auth/initial-setup` under the existing auth router (GET reads status, POST below performs setup).
   - Response shape: `{ "initialSetupRequired": boolean }`.
   - Implementation: open a transaction, lock the `initial_setup.completed_at` row (`SELECT ... FOR UPDATE`), and compute `initialSetupRequired` as `initial_setup.completed_at IS NULL AND admin_count == 0`.
   - Keep the handler unauthenticated; it only reveals whether the instance has ever been set up.

2. **Initial setup submission**
   - Reuse the existing `POST /users` route and schema instead of inventing a bespoke payload. The handler already validates email, password strength, and role assignment through `UsersService`.
   - Introduce a light-weight dependency (e.g. `InitialSetupWindow`) that:
     1. Opens a transaction.
     2. Locks the `initial_setup.completed_at` row.
     3. Counts current admins.
     4. Raises `HTTP 409` when an admin exists or the completion flag is set.
   - Allow the route to execute without authentication only while the dependency confirms the setup window is open. Otherwise, fall back to the existing behaviour that requires an authenticated admin.
   - After creating the admin, call the shared session-issuance helper so the response mirrors the normal login flow (session cookie + user payload) and set `initial_setup.completed_at = utcnow()` before committing.
   - If the guard fails (an admin already exists or another request won the race), return HTTP 409 with a friendly error payload.

3. **Fallback CLI flow**
   - Keep the existing CLI command for environments that prefer scripted provisioning; it can also reset `initial_setup.completed_at` to `NULL` if operators intentionally need to reopen the window. When the reset happens, the guard dependency automatically allows anonymous use of `POST /users` again.

## Frontend plan
1. **Status check**
   - The auth layout (same place we choose between login and forgot-password forms) calls `GET /auth/initial-setup` as soon as it mounts.
   - Cache the response for the session. If the POST request later returns 409, immediately invalidate the cache and render the login screen instead.

2. **Initial setup form**
   - Render an `InitialAdminSetup` component when `initialSetupRequired` is true.
   - Fields: email, password + confirmation, optional display name. Use the same validation helpers as the signup/invite forms for consistency.
   - Submit to `POST /users`. On success, route to the dashboard with the returned session info. On error, show the validation feedback inline and, for a 409, swap back to the login form.

3. **Standard login otherwise**
   - When `initialSetupRequired` is false, render the existing login form unchanged. No further logic is needed.

## Security checklist
- **Atomic guard**: lock the settings row and count admins inside the same transaction so two anonymous requests cannot both create admins. The same guard dependency also prevents bypassing the normal admin-only `POST /users` semantics once the instance is configured.
- **Input validation**: reuse established schemas for email and password strength, force the role to `ADMIN`, and rely on centralised password hashing.
- **Rate limiting**: apply the standard unauthenticated rate limiter/middleware used on other auth routes.
- **Session handling**: issue the same secure, HTTPOnly session cookie and ensure CSRF protections stay in place because the initial setup endpoint lives in the auth module.
- **Audit log**: emit an audit event noting who created the initial admin and when.

## Operational notes
- Add backend tests for the status endpoint, the successful initial setup, and the "already configured" guard.
- Add a frontend test that mocks the status API to cover both the setup form and the fallback login screen.
- Document in the deployment guide that the app now self-prompts for the first admin while the CLI command remains available for scripted installs.

This keeps the initial setup experience tiny, familiar to most developers, and aligned with how common FastAPI apps manage first-user setup.
