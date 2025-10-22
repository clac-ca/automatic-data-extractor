# RBAC Refactor Work Package

## Scope
- Implement unified RBAC model using principal → role @ scope assignments across backend, API, and frontend.
- Replace legacy role tables (`user_global_roles`, `workspace_membership_roles`, `users.role`) with new schema: `principals`, `permissions`, `roles`, `role_permissions`, `role_assignments` (with `scope_type` + `scope_id`).
- Update services, dependencies, and authorization checks to rely solely on `authorize(principal_id, permission_key, scope_type, scope_id)`.
- Align REST API routes, OpenAPI spec, and client usage with standardized endpoints for permissions, roles, and role assignments.
- Refresh seeds, migrations, and documentation to reflect the new terminology and workflows.
- Overhaul settings/admin UI to manage roles and role assignments within global and workspace scopes.
- Explicitly replace existing codepaths; **no backward compatibility shims** or dual-write logic required.

## Governance
- **Owner:** Platform engineering (auth & identity pod).
- **Reviewers:** Backend lead, frontend lead, security reviewer.
- **Stakeholders:** Product (admin experience), Compliance (audit/a11y).

## Non-goals
- Object-level ACLs or deny rules.
- Audit log redesign.
- Group/service-account principals (reserve schema affordances only).
- Changes to invitation or onboarding flows beyond role assignment touchpoints.

## Open Questions
- Confirm whether service accounts will land in this milestone or a future follow-up.
- Validate if any third-party integrations rely on legacy `users.role` or direct DB access (coordinate removals).

## Milestones
1. **Foundational Data Model** — Design migrations, SQLAlchemy models, and seed data for principals, roles, permissions, and assignments. Remove legacy tables/columns.
2. **Authorization Service Layer** — Introduce `authorize` helper, CRUD services for roles/assignments/permissions, and replace legacy checks in backend features.
3. **API Alignment** — Rebuild endpoints under `/api/v1` to match new routes, update schemas, dependencies, and integrate authorization helper.
4. **Frontend Admin Experience** — Update UI to manage roles and assignments across scopes, replacing old toggles.
5. **Testing & Documentation** — Add/adjust unit, integration, and E2E tests; update architecture docs, how-tos, and changelog.

## Authoritative API Routes
- **Permissions**
  - `GET /api/v1/permissions`
- **Global roles**
  - `GET /api/v1/roles?scope=global`
  - `POST /api/v1/roles?scope=global`
- **Workspace roles**
  - `GET /api/v1/workspaces/{workspace_id}/roles`
  - `POST /api/v1/workspaces/{workspace_id}/roles`
- **Role detail (applies to both scopes; `role_id` is unique)**
  - `GET /api/v1/roles/{role_id}`
  - `PATCH /api/v1/roles/{role_id}`
  - `DELETE /api/v1/roles/{role_id}`
- **Global role assignments**
  - `GET /api/v1/role-assignments?principal_id=&role_id=`
  - `POST /api/v1/role-assignments`
  - `DELETE /api/v1/role-assignments/{assignment_id}`
- **Workspace role assignments**
  - `GET /api/v1/workspaces/{workspace_id}/role-assignments?principal_id=&role_id=`
  - `POST /api/v1/workspaces/{workspace_id}/role-assignments`
  - `DELETE /api/v1/workspaces/{workspace_id}/role-assignments/{assignment_id}`
  - *(future enhancement; not yet implemented)* `PUT /api/v1/workspaces/{workspace_id}/role-assignments/{principal_id}/{role_id}`
- **Effective permissions**
  - `GET /api/v1/me/permissions?workspace_id={workspace_id}`
  - `POST /api/v1/me/permissions/check`

Use snake_case path and query parameters consistently (`workspace_id`, `principal_id`, `role_id`).

Use hyphenated resource names (`role-assignments`), plural nouns for collections, and shared request/response schemas for parity between scopes.

## Seed Permissions & Roles
- **Permission keys** (PascalCase; authoritative list, seeded in migrations/tests)
  - Global scope: `Workspaces.Read.All`, `Workspaces.ReadWrite.All`, `Workspaces.Create`, `Roles.Read.All`, `Roles.ReadWrite.All`, `Users.Read.All`, `Users.Invite`, `System.Settings.Read`, `System.Settings.ReadWrite`.
  - Workspace scope: `Workspace.Read`, `Workspace.Settings.ReadWrite`, `Workspace.Delete`, `Workspace.Members.Read`, `Workspace.Members.ReadWrite`, `Workspace.Documents.Read`, `Workspace.Documents.ReadWrite`, `Workspace.Configurations.Read`, `Workspace.Configurations.ReadWrite`, `Workspace.Roles.Read`, `Workspace.Roles.ReadWrite`, `Workspace.Jobs.Read`, `Workspace.Jobs.ReadWrite`.
- **Default global roles** (Microsoft Graph aligned)
  - `global-administrator`: tenant-wide administrator with every global permission.
  - `global-user`: baseline authenticated access without elevated privileges.
- **Default workspace roles** (SharePoint-inspired)
  - `workspace-owner`: full workspace management rights including membership and destructive operations.
  - `workspace-member`: collaborative contributor with document/job access.

Document rationale in seeds module and mirror definitions in frontend constants for UI labels.

## Database Constraints & Indexes
- `principals`: `principal_type` ENUM (`user` initial) with unique `user_id` FK and check enforcing user linkage when type=`user`.
- `permissions`: store `resource`, `action`, and `scope_type` columns with PascalCase keys; index on `scope_type` for quick lookups.
- `roles`: enforce `UNIQUE(scope_type, scope_id, slug)` plus lookup index on `(scope_type, scope_id)`; add a partial unique index on `(slug, scope_type)` where `scope_id IS NULL` to protect system workspace role templates.
- `role_assignments`: `UNIQUE(principal_id, role_id, scope_type, scope_id)` plus check constraint ensuring `scope_id` is present for workspace scope and absent for global.
- All bridging tables cascade deletions (`principals` ↔ `role_assignments`, `roles` ↔ `role_permissions`).
- Drop legacy enums (`permissionscope`, `rolescope`) once migrations land to avoid drift.

- [ ] Inventory existing RBAC usage across backend services and routers.
- [x] Draft Alembic migration for new tables and column drops (now consolidated into the baseline `0001_initial_schema`).
- [x] Update SQLAlchemy models to match final schema (principals, permissions, roles, role_permissions, role_assignments).
- [x] Implement data seeds for default permissions and roles.
- [x] Implement unified `authorize` utility and supporting service methods.
  - [x] Introduced stopgap `authorize(principal_id, ...)` facade that proxies to legacy helpers for global/workspace scopes.
  - [x] Flip workspace permission resolution to `role_assignments` once membership migration is complete.
  - [x] Promote `authorize` to operate on principals directly using assignment-backed permission lookups.
- [x] Replace legacy authorization helpers throughout backend.
- [x] Update `/api/v1/permissions` to use the new listing logic and scope guards.
- [x] Implement role CRUD endpoints for global and workspace scopes.
- [x] Implement role assignment endpoints for global and workspace scopes.
- [x] Ensure role assignment writes are idempotent (conflict-safe insert/upsert strategy).
- [x] Implement `/api/v1/me/permissions` effective permission endpoint.
- [x] Implement `/api/v1/me/permissions/check` batch permission endpoint.
- [x] Introduce FastAPI security dependencies (`require_authenticated`, `require_csrf`, `require_global`, `require_workspace`).
- [x] Adopt route-level security dependencies across feature routers.
  - [x] Roles router — workspace endpoints.
  - [x] Roles router — permissions/me endpoints.
  - [x] Roles router — global role & assignment endpoints.
  - [x] Remaining feature routers (documents, jobs, configurations, workspaces, users).
- [x] Update frontend admin/settings UI for roles and assignments.
- [x] Update automated tests for new RBAC behavior.
- [x] Update OpenAPI schemas and generated clients if present. *(Security schemes exposed; no generated clients to refresh yet.)*
- [x] Update architecture and how-to documentation.
- [x] Validate migrations apply cleanly to empty database.
- [x] Purge legacy models, enums, and seed paths once replacements are wired.
- [x] Coordinate frontend constant updates with backend slug/label naming.
- [x] Update API router and clients to mount `/api/v1` prefix consistently.
- [x] Drop column `users.role` and associated Pydantic/ORM references.
- [x] Remove `user_global_roles`; follow-up to retire `workspace_membership_roles` once workspace assignments move to the new table.
- [x] Remove `permissions.scope` column + any usage.
- [x] Rename `roles.scope` → `scope_type`, `roles.workspace_id` → `scope_id`; update ORM, schemas, and migrations accordingly.
- [x] Delete legacy helpers (`is_admin`, `has_workspace_role`, etc.) once `authorize` is live.
- [x] Migrate workspace membership flows to `role_assignments` and remove `workspace_membership_roles` usage.
- [x] Update seeds/fixtures to rely solely on new RBAC tables.
- [x] Update tests referencing legacy roles to use new assignments.

## Decisions Log
- *(2025-10-09)* Pending — initial discovery phase.
- *(2025-10-10)* Adopted standardized route naming, seed taxonomy, and constraint requirements per review feedback.
- *(2025-10-10)* Revised default role slugs to mirror Microsoft Graph/SharePoint conventions (`global-administrator`, `global-user`, `workspace-owner`, `workspace-member`).
- *(2025-10-15)* Confirmed need for Postgres partial unique index on system workspace roles, clarified interim `authorize(user_id, ...)` contract, and codified cookie path derivation relative to the API base.
- *(2025-10-16)* Established "modify the baseline migration" policy: collapse all Alembic history into `0001_initial_schema.py` and adjust AGENTS guidance accordingly while the product remains pre-GA.

## Risks & Mitigations
- **Large blast radius:** Schema, service, API, and UI changes touch many files. *Mitigation:* Work in scoped commits per milestone, maintain extensive tests.
- **Missing hidden authorization paths:** Legacy helpers may exist in multiple features. *Mitigation:* Perform exhaustive search for `is_admin`, `authorize_*`, and role slug references.
- **Frontend parity gap:** UI changes are sizable. *Mitigation:* Align backend routes first, then adjust frontend with mock data/tests.
- **Seed data drift:** Ensuring defaults match new roles/permissions. *Mitigation:* Centralize seed definitions in one module with tests.
- **UI/terminology drift:** Ensure frontend translations and copy reflect new scope labels. *Mitigation:* Introduce shared constants for labels and reuse them across API & SPA.

- **2025-10-09:** Initialized work package; gathered current RBAC models (`roles`, `permissions`, `user_global_roles`, `workspace_membership_roles`) for analysis.
- **2025-10-10:** Incorporated reviewer guidance: codified API routes, default permission taxonomy, constraints, and explicit legacy cleanup tasks.
- **2025-10-10:** Updated seed role catalog to align with Microsoft-inspired administrator/member naming across global and workspace scopes.
- **2025-10-11:** Added bridging `authorize(principal_id, ...)` helper and tests to exercise the target API without breaking legacy flows; ready to swap backend callers incrementally.
- **2025-10-12:** Migrated schema to unified principals/role_assignments model, updated ORM/services/tests/UI to use PascalCase permissions and Microsoft-style role slugs, and dropped `user_global_roles` in favour of the new assignment table.
- **2025-10-13:** Hardened migrations for SQLite, wired models/services/front-end to `scope_type`/`scope_id`, seeded PascalCase permissions, and greened backend/frontend test suites; workspace membership role migration and broad `authorize()` adoption still pending.
- **2025-10-14:** Shifted the public API to `/api/v1`, added effective permission endpoints (GET + batch POST), seeded workspace role assignments for fixtures, and updated plan routes to snake_case with principal/role filters.
- **2025-10-15:** Addressed review feedback by reinstating the partial uniqueness constraint for system workspace roles, clarifying the temporary `authorize` signature, hardening migration drops for drifted environments, and fixing refresh cookie path derivation with regression tests.
- **2025-10-16:** Collapsed migrations into the unified `0001_initial_schema` baseline (no downgrade), documented the workflow in the agent playbook, and removed superseded version files.
- **2025-10-17:** Made role assignments idempotent, enforced workspace existence on scoped grants, expanded baseline indexes for common queries, and added regression coverage for duplicate assignment calls.
- **2025-10-18:** Extended system role uniqueness enforcement to SQLite, hardened role assignment upserts for concurrent calls, and documented the workspace-authorization bridge that still relies on membership roles.
- **2025-10-19:** Added referential integrity for workspace-scoped assignments, normalised permission resource parsing, and tightened idempotent inserts to avoid nested transaction rollbacks during conflicts.
- **2025-10-20:** Replaced `workspace_membership_roles` with role assignments across services, repositories, and fixtures; workspace permissions now resolve exclusively via `role_assignments`.
- **2025-10-21:** Delivered global role CRUD endpoints using the unified service helpers, expanded router coverage for role detail/update/delete, and verified the flow via integration tests.
- **2025-10-22:** Implemented global and workspace role-assignment APIs with idempotent service plumbing, comprehensive router coverage, and integration tests validating create/list/delete flows.
- **2025-10-23:** Scoped next milestone to adopt route-level FastAPI security dependencies so OpenAPI accurately reflects RBAC requirements; queued work to author reusable guards before wiring them into feature routers.
- **2025-10-23:** Implemented shared FastAPI security dependencies (require_authenticated guard, CSRF enforcement, global/workspace permission checks) with unit coverage to unblock route-level adoption and OpenAPI security scheme wiring.
- **2025-10-24:** Converted global role and assignment endpoints to the new route-level security dependencies and planned follow-on work for workspace and catalog routes.
- **2025-10-25:** Shifted workspace role-assignment APIs onto the shared Security guards (with CSRF on mutations), clearing the workspace portion of the route-level enforcement milestone.
- **2025-10-26:** Moved the permission catalog and `/me` endpoints onto the shared Security dependencies so RBAC requirements surface directly in OpenAPI while preserving workspace existence checks.
- **2025-10-27:** Converted documents, configurations, jobs, users, and workspaces routers to the shared `require_authenticated`/`require_*` dependencies with CSRF enforcement on mutations, clearing the route-level security milestone for feature endpoints.
- **2025-10-28:** Added OpenAPI security schemes for session cookies, bearer tokens, and API keys so the docs reflect RBAC guards and wired corresponding tests.
- **2025-10-29:** Converted `authorize` and security dependencies to operate on principals, added principal-aware identities, and centralized permission evaluation on role assignments.
- **2025-10-30:** Retired the last admin-specific helper and moved auth API key management endpoints onto the shared Security guards with structured RBAC denials.
- **2025-10-31:** Removed the outdated RBAC migration plan doc, verified the baseline schema omits `users.role`, and centralized role detail/update/delete authorization through the route-level guards.
- **2025-10-31:** Delivered admin console screens for global and workspace role management with full CRUD and assignment workflows wired to the new `/api/v1/roles` and `/role-assignments` endpoints, ensuring UI parity with backend RBAC.
- **2025-11-01:** Documented the unified RBAC architecture and published how-to guides for granting global administrators and workspace editors so operators can follow supported flows without referencing code.
- **2025-11-02:** Addressed review nits by normalizing 422 responses, removing redundant CSRF enforcement, cleaning dead dependencies, and tightening documentation wording.
- **2025-11-03:** Verified route guards use the PascalCase permission catalog, plugged remaining CSRF dependencies on role mutations, and added a regression test that fails when new mutating routes omit the CSRF requirement.
