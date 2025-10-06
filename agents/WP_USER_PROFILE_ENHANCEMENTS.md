# Work Package: User Profile Enhancements

## Objective
Expose richer profile data (display name and default workspace selection) to support the post-login shell and ensure the frontend can recover preferred context after authentication.

## Deliverables
- Updated `UserProfile` schema with `display_name` and `default_workspace_id` fields.
- Query logic in `UsersService.get_profile` that resolves the caller's default workspace via `WorkspacesService`/repository helpers.
- FastAPI `/auth/me` response reflecting the expanded schema, with integration tests.
- Migration or fallback strategy when a user has no default workspace (return `null`).

## Key Decisions
- Prefer deriving the default workspace from `workspace_memberships.is_default`; do not denormalize into the users table yet.
- If no default workspace exists, explicitly return `null` so the client can choose the first workspace.
- Avoid additional round-trips by fetching default membership within the same DB session.

## Tasks
1. Extend `app/features/users/schemas.py` and related Pydantic models to include the new fields.
2. Update `UsersService` to fetch the default workspace ID (use existing repository helpers or add one if missing).
3. Adjust auth dependencies/tests to ensure the new fields propagate through `/auth/me` and session envelopes.
4. Update fixtures/factories to set `display_name` and `is_default` where necessary.
5. Run pytest + mypy to confirm compatibility.

## Testing
- pytest focusing on auth and workspaces suites.
- mypy (schemas/services).

## Out of Scope
- UI changes.
- Admin endpoints for editing profile fields.
- Storing UI preferences beyond default workspace.

## Dependencies
- Depends on `WP_WORKSPACE_DATA_MODEL` for consistent workspace scoping before rollout.

## Frontend impact
- Post-login shell expects `/api/auth/me` to return `display_name` and `preferred_workspace_id`. Current profile lacks both, so the workspace selector and greeting proposed in `agents/FRONTEND_DESIGN.md` cannot hydrate.
