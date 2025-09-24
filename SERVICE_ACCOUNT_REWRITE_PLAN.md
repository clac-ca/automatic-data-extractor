# Service Account Rewrite Plan

## Background
- Service accounts currently live in their own table (`service_accounts`) with bespoke models/repositories.
- API keys and auth flows branch on two identity types even though both ultimately represent ADE principals.
- No external consumers rely on the current schema, so we can collapse to the simplest, most consistent design now.

## Guiding Idea
Treat every principal as a `User`. A service account is just a user that:
- Has `is_service_account = TRUE`.
- Does not authenticate with a password (password hash stays `NULL`).
- Uses API keys (or other automation credentials) exclusively.
- Can hold the same `role` values and permissions pipeline as humans.
This keeps identity logic unified and avoids duplicating models or repositories.

## Goals
- Store service accounts directly in `users` with a single Boolean flag and optional metadata.
- Remove the standalone service account module, migrations, and foreign keys.
- Simplify API key issuance/authentication so it only ever touches `User` rows.
- Update tests/fixtures/docs to reflect the unified identity model.

## Implementation Outline
1. **Schema refresh**
   - Delete the legacy `service_accounts` migration; amend the baseline so the `users` table includes:
     - `is_service_account` (BOOLEAN DEFAULT FALSE, indexed).
     - `display_name` (STRING, nullable) and `description` (STRING, nullable) for optional labelling.
     - `created_by_user_id` (nullable FK to `users.user_id`) for provenance.
   - Update the `api_keys` table to reference only `users.user_id` (drop `service_account_id`, related FKs/check constraints).
   - Regenerate Alembic revisions (or rewrite the existing ones) so a fresh `alembic upgrade head` produces the new structure.

2. **Domain model updates**
   - Extend `backend/api/modules/users/models.py` with the new columns and validation:
     - enforce trimmed strings;
     - ensure any password-based authentication path checks `not is_service_account`.
   - Provide convenience helpers on `User` (e.g., `is_service_account` is the flag, `label` returns `display_name or email`).
   - Enhance `UsersRepository` with service-account helpers: `create_service_account(...)`, `list_service_accounts()`, `get_by_service_account_email(...)`.
   - Remove `backend/api/modules/service_accounts/` and adjust exports/imports accordingly.

3. **Auth & API key flow**
   - Update the `APIKey` ORM/repository to drop the service-account relationship and always join through `User`.
   - Adjust `AuthService`:
     - Replace `ServiceAccountsRepository` usage with the new `UsersRepository` helpers.
     - Ensure password authentication rejects `is_service_account` users (raise 403).
     - `issue_api_key_for_service_account` now looks up users flagged as service accounts via email/ID.
     - `authenticate_api_key` returns `AuthenticatedPrincipal` with `principal_type` determined by the user flag.
   - Update FastAPI dependencies (`bind_current_principal`, `ServiceContext.current_service_account`) so they surface the user object and rely on the flag.

4. **Fixtures & tests**
   - Modify `backend/tests/conftest.py` fixtures to create service accounts via the user model (e.g., email `automation-{slug}@service.local`, `is_service_account=True`).
   - Update auth tests to assert service-account principals carry the user ID/email and that password logins are rejected for them.
   - Add unit coverage for the new repository helpers and validation logic.

5. **Documentation & plans**
   - Refresh `CLI_IMPLEMENTATION_PLAN.md` and `BACKEND_REWRITE_PLAN.md` to describe service accounts as “users flagged for automation”.
   - Document the expected email/label conventions and how API keys are issued in the unified model.

6. **Verification**
   - Run migrations on a clean database, then exercise `pytest`, `ruff`, and `mypy`.
   - Smoke-test API key issuance/auth for both human and service-account users, ensuring password login is blocked for the latter.

## Risks & Mitigations
- **Email collisions**: generate deterministic-but-unique emails for service accounts (`{slug}@service.local`) and rely on the existing UNIQUE constraint.
- **Forgotten flag checks**: audit authentication paths (password, SSO) to ensure they guard against `is_service_account` where appropriate.
- **Migration history rewrite**: clearly communicate the schema reset (and wipe sandbox DBs) since earlier revisions are removed.

## Follow-ups
- Consider exposing service-account CRUD through the CLI once the unified model lands.
- Extend user-facing schemas (e.g., `UserProfile`) with `display_name` so UI/API consumers see friendlier labels.
- Review event logging to include the new metadata for automated actors.
