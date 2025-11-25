### Why we’re doing this (articulate & fundamental)

We’re turning our API and domain layer into a **contract‑first system**: every resource has a single, predictable set of names, enums, and envelopes; every list looks the same; every error looks the same; every identifier is strongly typed; and every “update” means “partial.” That contract should be simple enough that it’s hard to misuse and rich enough that `openapi-typescript` produces **zero‑surprise** client types—no `any`, no ad‑hoc unions, no special cases per feature. The payoff is compound interest: fewer UI branches, fewer API gotchas, safer refactors, and a smoother path for new capabilities (versioned configs, richer roles, larger file trees) without re‑designing the plumbing each time. In short: **make the shape of the data the product**, and let the codegen and tests enforce it.

---

## Executive “wins” (what to change for the biggest dividends)

1. **One schema base. Everywhere.**
   Most schemas already use a shared `BaseSchema`, but the configuration and build schemas use raw `BaseModel` with local `ConfigDict`s—this is the root of subtle inconsistencies. Migrate *all* schemas to one base with `extra="forbid"`, `from_attributes=True`, `populate_by_name=True`, and default `exclude_none=True` serialization. Targets: `configurations` & `builds`.

2. **One ID type alias for ULIDs. Everywhere.**
   Documents use a strong `ULIDStr` alias; others pass raw `str`. Standardize on `ULIDStr` for **every** ULID field across users, workspaces, roles, builds, API keys, etc. This removes an entire class of client/server bugs. 

3. **Enums aligned across ORM & schemas.**
   Replace string statuses + checks with shared Python Enums at the ORM level and expose the same names as string enums in Pydantic/OpenAPI: configurations (`draft/published/archived`), builds (`building/active/inactive/failed`), documents (status/source), and RBAC (scope/principal). Today this is mixed (raw strings, SQLA `Enum`, or Literals). Unify it.

4. **Update means partial.**
   Some `Update` schemas still require fields (e.g., `RoleUpdate.name`), which forces clients to re‑send full objects. Make every field optional and validated **if present** across all `*Update` DTOs. 

5. **Stable wire names, minimal aliasing.**
   Several DTOs map names via `validation_alias`/`serialization_alias` (e.g., `document_id`↔`id`, `original_filename`↔`name`). Keep **canonical snake_case wire names** (`*_id`, `original_filename`, etc.) and use aliasing only as a temporary, documented bridge for deprecations—don’t permanently ship two names per field. 

6. **Page every list.**
   Documents & users already return `Page[T]`. Extend that envelope to roles, workspaces, API keys, etc., so every client list call is uniform.

7. **Tighten file‑tree DTOs (branchless UI).**
   `FileEntry` currently allows many `None`s (e.g., `mtime`, `etag`, `content_type`, `has_children`). Make these always present (dirs can have `size=null` but still include `mtime`, `content_type="inode/directory"`, `has_children: bool`). Also standardize rename response to use **wire keys `from` / `to`** (not `src` / `dest`). 

8. **Stop leaking server internals in builds.**
   `BuildRecord` exposes `venv_path` as an absolute filesystem path. Replace with a non‑sensitive `environment_ref` or `venv_label` that’s meaningful to clients but does not tie UI to host layout. 

9. **One error model: RFC‑9457 Problem Details.**
   Introduce a single `ProblemDetail` schema with stable `code`, `trace_id`, and optional `meta` used by **all** endpoints. No more bespoke error shapes.

10. **Make workspace JSON settings truly mutable.**
    The ORM model stores plain JSON (no change tracking) while documents use `MutableDict`. Convert workspace settings to mutable JSON to avoid lost updates.

---

## Scope

* **Models**: users, workspaces/memberships, RBAC, documents, configurations, builds, API keys, system settings, (runs: remove or formalize).
* **Schemas**: auth, users, workspaces, roles, documents, configurations & file tree, builds, health, runs placeholder.

---

## Canonical conventions (apply repo‑wide)

### Naming & structure

* **DTO families**: `*Create`, `*Update` (partial), `*Out` (single read), `*List` or `Page[*]` (paginated), `*Summary` (truly condensed). Retire mixed terms like `Record`/`Profile`/`Read` unless there’s a strong reason. Current candidates to rename: `UserProfile/UserSummary` → `UserOut`; `RoleRead` → `RoleOut`; `DocumentRecord` → `DocumentOut`; `BuildRecord` → `BuildOut`; `ConfigurationRecord` → `ConfigurationOut`.
* **IDs**: all ULIDs use `ULIDStr` and *wire names are explicit* (`user_id`, `workspace_id`, `document_id`, `build_id`, …). Avoid `id` on the wire; if you must bridge legacy, keep the alias **temporary** with a documented removal date. 
* **Enums**: single Python Enum per concept consumed by both ORM (SQLAlchemy `Enum(..., native_enum=False)`) and schema (string enum). Unify `Configuration.status`, `Build.status`, `Document.status/source`, RBAC `scope_type/principal_type`.
* **Base schema**: one `BaseSchema` with `extra="forbid"`, `from_attributes=True`, `populate_by_name=True`, default `model_dump(exclude_none=True)`. Migrate configs/builds off raw `BaseModel`.
* **Pagination**: everything lists as `Page[T]` (you already do this in documents & users); extend it to roles/workspaces/auth listings.
* **Errors**: `ProblemDetail` (RFC‑9457) with `type`, `title`, `status`, `detail`, and extensions: `code` (stable machine code), `trace_id`, `meta`.

### File tree specifics

* `FileEntry`: `mtime`, `etag`, `content_type`, `has_children` are **required**; `size: null` for dirs; `content_type="inode/directory"` for dirs; `depth: int`.
* `FileListing.depth`: `"0" | "1" | "infinity"` (string union), aligning request/response.
* `FileRenameResponse`: use **wire keys** `from` / `to` (deprecate `src` / `dest`). 

### Security & privacy

* Avoid leaking host paths or secrets (e.g., replace `venv_path` with `environment_ref`). 

---

## Class inventory (what exists now → target names)

> The agent should produce a one‑to‑one rename map and update `__all__` exports accordingly.

* **Documents**: `UploaderSummary`, `DocumentRecord`, `DocumentListResponse` → `UploaderOut`, `DocumentOut`, `Page[DocumentOut]`. (Keep `ULIDStr`.) 
* **Users**: `UserProfile`, `UserSummary`, `UserListResponse` → `UserOut`, `Page[UserOut]`. 
* **Workspaces**: `WorkspaceProfile`, `WorkspaceMember`, `WorkspaceMemberCreate`, `WorkspaceMemberRolesUpdate`, `WorkspaceDefaultSelection` → `WorkspaceOut`, `WorkspaceMemberOut`, `WorkspaceMemberCreate`, `WorkspaceMemberRolesUpdate`, `WorkspaceDefaultSelectionOut`. 
* **RBAC**: `PermissionRead`, `RoleCreate`, `RoleUpdate`, `RoleRead`, `RoleAssignmentCreate`, `RoleAssignmentRead`, `EffectivePermissionsResponse`, `PermissionCheckRequest/Response` → `PermissionOut`, `RoleCreate`, `RoleUpdate` (partial), `RoleOut`, `RoleAssignmentOut`, etc. Make `scope_type` and `principal_type` true enums. 
* **Auth**: keep shapes, but align names to `*Out` where they are responses (`SessionEnvelope`, `AuthProvider`, `ProviderDiscoveryResponse`, `APIKeyIssueResponse`, `APIKeySummary`). Consider `APIKeyOut` for summaries. 
* **Health**: `HealthComponentStatus`, `HealthCheckResponse` (leave as is or lift to enums). 
* **Configurations + Files**: `ConfigurationCreate`, `ConfigurationRecord`, `ConfigurationValidateResponse`, `ConfigurationActivateRequest`, `File*` DTOs → `ConfigurationOut`, `ConfigurationValidateOut`, and tightened `FileEntry/FileListing` as above. Keep discriminated `ConfigSource`. 
* **Builds**: `BuildRecord`, `BuildEnsureRequest/Response` → `BuildOut`, `BuildEnsureOut`; replace `venv_path`. 
* **Runs**: `RunPlaceholder` → remove or formalize `RunOut` minimally. 

---

## Mechanical steps for the agent

1. **Schema base unification**

   * Replace `BaseModel` with `BaseSchema` in configs/builds; verify `extra="forbid"`, `from_attributes=True`, `populate_by_name=True`, and default `exclude_none=True`.

2. **ULID pass**

   * Introduce (or centralize) `ULIDStr` and migrate all `*_id` fields in schemas to it (users, workspaces, roles, builds, API keys, etc.). Keep documents as the reference. 

3. **Enums pass**

   * Map each status/type Literal/string to shared Enums:

     * ORM: configs (`status`), builds (`status`), documents (`status`, `source`), RBAC (`scope_type`, `principal_type`).
     * Schemas: import and use the same enum types so OpenAPI emits string enums.

4. **Create/Update split**

   * Ensure `*Create` has required fields; `*Update` is partial. E.g., make `RoleUpdate.name` optional and validate only if present. 

5. **Alias cleanup & wire names**

   * Collapse dual names on the wire (prefer explicit `*_id`, `original_filename`, etc.). Keep aliases for at most one release behind a feature flag or doc note (e.g., `DocumentRecord`’s mapping today). 

6. **Lists**

   * Migrate every list response to `Page[T]` (`items`, `count`, `next_token`) like documents/users. Add missing `*List` responses.

7. **File tree tightening**

   * Make `FileEntry` core fields non‑nullable; enforce `inode/directory` for dirs; ensure `FileRenameResponse` wire keys are `from`/`to` (deprecate `src`/`dest`). 

8. **Build surface hardening**

   * Replace `venv_path` with `environment_ref`/`venv_label` (string), preserving other metadata. 

9. **Problem Details**

   * Add a shared `ProblemDetail` schema (RFC‑9457) with `code`, `trace_id`, `meta`, and update router responses to reference it across modules.

10. **Workspace settings mutability**

* Switch ORM `Workspace.settings` to `MutableDict` to match expected in‑place schema updates; this aligns with `Document.attributes` & `SystemSetting.value`.

11. **Runs**

* Remove placeholder schemas/models or formalize a minimal `RunOut` and `Run` enum.

12. **Exports & docs**

* Normalize `__all__` across modules (export only public DTOs); add docstrings and `Field(..., description="…")` for any fields missing descriptions in responses that are user‑facing (e.g., a few workspace/auth fields already have good descriptions to emulate).

---

## Back‑compat & deprecation policy (subtle but important)

* **Field renames**: keep dual aliasing for **one release** only; mark in OpenAPI with `deprecated: true` on the old wire name (where your tooling supports it).
* **Enum tightening**: when upgrading from free strings to enums, keep a temporary server‑side parser that produces a `ProblemDetail` with `code="invalid_enum_value"` on bad input.
* **Build internals**: ship `environment_ref` alongside `venv_path` for one release, then remove `venv_path`. 

---

## Deliverables

1. **Schema audit report** (per DTO): base class, enum fields, ID types, aliasing, pagination, nullability notes, and a “new name” column.
2. **Enum catalog**: definitive list and mapping from old strings/Literals to new enum values (ORM + schema).
3. **Wire name map**: every field whose wire name changes (with deprecation notes).
4. **List envelope map**: endpoints converted to `Page[T]`.
5. **Error model**: shared `ProblemDetail` definition and router response table that uses it.
6. **OpenAPI diff**: before/after spec and a quick `openapi-typescript` compile check to ensure clean TS unions for discriminated types (e.g., `ConfigSource`) and string enums. 

---

## Acceptance criteria

* **Base**: all schemas inherit from one base; no stray `BaseModel` configs left in configs/builds.
* **IDs**: all ULID fields use `ULIDStr`; wire names are explicit `*_id`; any old aliases are deprecated and scheduled to be removed. 
* **Enums**: every status/kind/scope field in ORM & schemas uses the shared enums; OpenAPI emits string enums (not untyped strings).
* **Updates**: all `*Update` schemas are partial (optional fields with validation). 
* **Lists**: all list endpoints return `Page[T]` or `{Resource}List` matching that envelope. 
* **Files**: `FileEntry` core fields are non‑nullable and consistent; `FileRenameResponse` uses `from`/`to`. 
* **Builds**: no absolute host paths are exposed. 
* **Workspace settings**: mutable JSON with change tracking. 
* **Errors**: a single `ProblemDetail` is used across all endpoints.

---

## Quality gates & tests

* **Contract**: regenerate OpenAPI & run `openapi-typescript`—TypeScript compiles with no `any` from us, discriminated unions for `ConfigSource`, and string enums for statuses. 
* **Serialization**: golden JSON fixtures for each `*Out` and `*List` DTO (no missing required fields; dirs show `content_type="inode/directory"`; enums serialize as strings).
* **Back‑compat**: tests proving old aliases are accepted (during the deprecation window) and new names are canonical.
* **Security**: ensure `venv_path` (or any sensitive path) is never present on the wire. 

---

### Final note

This is intentionally a **small‑surface, big‑impact** refactor: unify base config, IDs, enums, lists, and errors; tighten file‑tree DTOs; remove path leakage. Everything else—like richer config/editor features—builds on this bedrock.
