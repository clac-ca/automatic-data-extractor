Below is a **clean, single‑release workpackage** to standardize your schema so **every table’s primary key column is named `id`**. Because you have **no live databases or users**, we will **edit the initial Alembic revision** (not add a new migration) and align the ORM and schemas to the new convention.

---

## Why we’re doing this

We’re removing “naming tax” across the stack. Today some tables use `user_id`, `workspace_id`, `document_id`, some use **natural keys** like `key`, and some use **composite primary keys**. That diversity forces special‑case FKs, model mixins, and schema aliasing. Moving to **one rule—every table owns a single `id` PK—** makes the data model *boringly consistent*: joins are predictable, ORM code is simpler, OpenAPI/types are cleaner, and future migrations are safer. With no production data, we can do this as a one‑shot edit to the initial schema and lock in the convention.

---

## Target end‑state (rules)

1. **PK column name**: always `id` (ULID, varchar(26) for entity tables).
2. **FK column names**: keep explicit `<resource>_id` (e.g., `workspace_id`, `user_id`, `document_id`).
3. **Composite PKs** → replaced by surrogate `id` + **unique** constraints that preserve business rules.
4. **Natural PKs** (`permissions.key`, `system_settings.key`) → keep the natural column as **unique**, but not the PK.

---

## Before → After map (authoritative checklist)

> These are the tables defined in your initial revision. For each, the “After” state shows how the PK and key FKs should look.

| Table                     | Current PK                            | After: PK & notes                                                                                                                                                     |
| ------------------------- | ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `users`                   | `user_id`                             | **PK** `id`; keep `email_canonical` unique; FKs elsewhere now point to `users.id`.                                                                                    |
| `user_credentials`        | `credential_id`                       | **PK** `id`; FK `user_id → users.id` (unchanged column name, new target).                                                                                             |
| `user_identities`         | `identity_id`                         | **PK** `id`; FK `user_id → users.id`; `(provider, subject)` unique stays.                                                                                             |
| `workspaces`              | `workspace_id`                        | **PK** `id`; keep `slug` unique; FKs elsewhere now point to `workspaces.id`.                                                                                          |
| `workspace_memberships`   | `workspace_membership_id`             | **PK** `id`; FKs `user_id → users.id`, `workspace_id → workspaces.id`; `(user_id, workspace_id)` unique stays.                                                        |
| `permissions`             | `key` (natural)                       | **PK** `id`; add **UNIQUE(key)**; downstream FKs should use `permission_id → permissions.id`.                                                                         |
| `roles`                   | `role_id`                             | **PK** `id`; FK `scope_id → workspaces.id`; uniqueness `(scope_type, scope_id, slug)` stays; partial unique for “system” slug stays.                                  |
| `role_permissions`        | `(role_id, permission_key)`           | **PK** `id` (new); **UNIQUE(role_id, permission_id)**; FKs: `role_id → roles.id`, `permission_id → permissions.id`.                                                   |
| `principals`              | `principal_id`                        | **PK** `id`; FK `user_id → users.id`; check constraint on `(principal_type, user_id)` stays.                                                                          |
| `role_assignments`        | `assignment_id`                       | **PK** `id`; FKs: `principal_id → principals.id`, `role_id → roles.id`, `scope_id → workspaces.id`; uniqueness `(principal_id, role_id, scope_type, scope_id)` stays. |
| `documents`               | `document_id`                         | **PK** `id`; FKs: `workspace_id → workspaces.id`, `uploaded_by_user_id → users.id`, `deleted_by_user_id → users.id`.                                                  |
| `document_tags`           | `(document_id, tag)`                  | **PK** `id` (new); **UNIQUE(document_id, tag)**; FK `document_id → documents.id`.                                                                                     |
| `api_keys`                | `api_key_id`                          | **PK** `id`; FK `user_id → users.id`; `token_prefix` and `token_hash` unique stay.                                                                                    |
| `system_settings`         | `key` (natural)                       | **PK** `id`; add **UNIQUE(key)**.                                                                                                                                     |
| `configs`                 | `config_id`                           | **PK** `id`; FK `workspace_id → workspaces.id`; `(workspace_id, slug)` unique stays.                                                                                  |
| `config_versions`         | `config_version_id`                   | **PK** `id`; FK `config_id → configs.id`; `(config_id, sequence)` unique stays.                                                                                       |
| `workspace_config_states` | `workspace_id`                        | **PK** `id` (new); **UNIQUE(workspace_id)**; FKs: `workspace_id → workspaces.id`, `config_id → configs.id`, `config_version_id → config_versions.id`.                 |
| `configurations`          | `(workspace_id, config_id)`           | **PK** `id` (new); **UNIQUE(workspace_id, config_id)**; FK `workspace_id → workspaces.id`.                                                                            |
| `configuration_builds`    | `(workspace_id, config_id, build_id)` | **PK** `id` (new); add `configuration_id` (FK → `configurations.id`); keep other columns; translate partial uniques for status to use `configuration_id`.             |
| `jobs`                    | `job_id`                              | **PK** `id`; FKs: `workspace_id → workspaces.id`, `config_id → configs.id`, `config_version_id → config_versions.id`, `submitted_by_user_id → users.id`.              |

---

## Plan of record (single release, edit the initial revision)

Because no instances exist, **edit `0001_initial_schema` directly**:

### 1) Cross‑cutting decisions

* Keep your declared `Enum`s as is; this migration only renames/introduces PKs and rewires FKs.
* Use the same ULID type you already use elsewhere (varchar(26)) for all new `id` columns.
* Keep existing **indexes** and **check constraints**, adjusting only their column references.

### 2) Update each `_create_*` function in the initial Alembic

> The pattern is: (a) rename owner PK columns to `id` where possible, (b) where natural/composite PKs exist, introduce `id` as the PK and add/adjust uniques, (c) change FKs to reference `<table>.id`, and (d) update any index/constraint names if you maintain naming conventions.

* **Users, Workspaces, API Keys, Roles, Principals, Credentials, Identities, Memberships, Documents, Jobs**
  Change the PK column in `op.create_table()` to `sa.Column("id", sa.String(26), primary_key=True)` and adjust downstream FKs in callers to reference `.id`. (Examples: `user_id` references → `["users.id"]`; `workspace_id` references → `["workspaces.id"]`; `roles.role_id` → `roles.id`, etc.)

* **Permissions**
  Change PK to `id`; keep `key` as a regular column with **UNIQUE**. Update the bridge to use `permission_id`.

* **Role permissions (bridge)**
  Replace `PrimaryKeyConstraint("role_id", "permission_key")` with `sa.Column("id", sa.String(26), primary_key=True)`, add a new `permission_id` column (FK → `permissions.id`), and add `sa.UniqueConstraint("role_id", "permission_id")`. Change the index from `permission_key_idx` → `permission_id_idx`.

* **Document tags (bridge)**
  Add `id` PK, keep `document_id` + `tag` as a **UNIQUE** pair, and point `document_id` FK to `documents.id`.

* **Configs / Config versions**
  Use `id` as primary key in both tables; update `config_versions.config_id` to FK `configs.id`. (Keep existing unique constraints indexed.)

* **Workspace config states**
  Add `id` as the PK; keep `workspace_id` as a FK to `workspaces.id`; add **UNIQUE(workspace_id)**; keep the existing unique on `config_version_id`.

* **Configurations**
  Introduce `id` as PK; keep `workspace_id` and `config_id` columns; add **UNIQUE(workspace_id, config_id)**; continue indexing on `(workspace_id, status)` and the single‑active partial unique.

* **Configuration builds**
  Introduce `id` as PK. Add `configuration_id` (FK → `configurations.id`) to replace the composite FK. Re‑express the two partial uniques (“active” and “building”) to use `(configuration_id)` instead of `(workspace_id, config_id)`.

### 3) ORM alignment (SQLAlchemy)

* Update your ULID mixin to **always create `id`** as the PK and remove the `__ulid_field__` override pattern in models.
* Update each model class to expose `.id` as the PK.
* Change bridge models: `RolePermission` → `id` PK + `permission_id` FK; `DocumentTag` → `id` PK + **UNIQUE(document_id, tag)**.
* Update `Configuration` and `ConfigurationBuild` models to match the new PK/`configuration_id` design.
* Remove any model properties or aliases that exposed old owner PK names (e.g., `document_id` property hacks).

### 4) (Optional but strongly recommended) API schema alignment

* Top‑level `*Out` DTOs (Users, Workspaces, Roles, Principals, Documents, API Keys, Configs, Config Versions, Configurations, Builds, Jobs) expose **`id`**.
* Relationship fields remain explicit `<resource>_id` (e.g., `workspace_id`, `user_id`, `document_id`, `configuration_id`).
* Remove permanent aliasing like `document_id ⇄ id` in schemas—no need for dual names now.

---

## Acceptance criteria

* **DB**: Every table has a single `id` PK; all FKs reference `<table>.id`; composite PKs are gone; natural keys are unique, not primary.
* **ORM**: Every model exposes `.id`; bridge models use `id` PK and the new FKs; relationship loading still works.
* **Build rules**: “Single active” / “single building” constraints for builds are enforced using `configuration_id`.
* **API (if applied)**: Top‑level resources return `id`; generated OpenAPI/TypeScript types reflect the new names without alias hacks.
* **Migrations**: The initial revision (`0001_initial_schema`) reflects this final state and can be applied to an empty DB without errors.

---

## Test plan

1. **Schema compile & migrate (empty DB)**

   * `alembic upgrade head` from a clean database succeeds.
   * Introspect: each table has PK on `id`; all FKs reference `… .id`.

2. **ORM CRUD smoke**

   * Create/read/update/delete for Users, Workspaces, Documents (+Tags), Permissions/Roles/Assignments, Configs/Versions/Configurations/Builds, API Keys, System Settings.
   * Relationship checks: e.g., Workspace → Memberships; Role ↔ Permissions; Document ↔ Tags; Configuration ↔ Builds.

3. **Constraint checks**

   * Uniqueness: `(workspace_id, slug)` in `configs`; `(config_id, sequence)` in `config_versions`; `(workspace_id, config_id)` in `configurations`; `(document_id, tag)` in `document_tags`; `(role_id, permission_id)` in `role_permissions`; unique `key` in `permissions` and `system_settings`.
   * Build partial uniques: exactly one `active` and one `building` per `configuration_id`.

4. **API smoke (if applied)**

   * Representative endpoints return `id` for owners and `<resource>_id` for references; no 500s due to renamed columns.

---

## Execution order (agent checklist)

1. Edit `0001_initial_schema`:

   * Rename owner PK columns to `id`.
   * For natural/composite PKs, add `id` and set uniques/FKs as above.
   * Adjust all FK targets and indexes.
2. Update SQLAlchemy models to match the new PK/ FK layout; remove `__ulid_field__`.
3. (Optional) Update Pydantic schemas to expose `id` for owners.
4. Run the test plan; fix any naming oversights.
5. Commit with a clear migration note: “**All tables now use `id` as primary key**. Bridges & composites replaced by surrogate `id` + uniques; natural keys remain unique.”

---

## Risks & notes

* **Join/Bridge cardinality**: moving from composite PK to `id` is safe but requires careful unique constraints; ensure they’re present.
* **Config lineage**: `configuration_builds` should point to `configurations.id` via `configuration_id`; this avoids re‑introducing a composite FK later.
* **Naming clarity**: we are explicitly *not* renaming FK column names (`user_id`, `workspace_id`, …)—only their targets. This keeps changes focused and predictable.