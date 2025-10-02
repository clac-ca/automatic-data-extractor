# Agent Spec: ADE Minimal Schema Refactor — Upload & Processing Core

**Goal:** Implement a clean, tenancy‑aware persistence + service layer with FastAPI endpoints for auth, workspaces, documents (single‑request upload via `UploadFile`), configurations, jobs, events, and minimal system settings. SQLite first, with a clearly documented path to PostgreSQL.

---

## Execution Plan

1. **Foundation:** Introduce domain primitives (shared enums, ULID helpers, aware timestamp mixins, JSON/DateTime type decorators), wire the session `before_flush` hook, and replace the Alembic base migration plus supporting schema docs.
2. **Identity & Auth:** Rebuild users, identity providers, user identities, and API keys with canonicalised email handling, update services/routers (`/auth/providers`, `/auth/me`), and extend `system_settings` helpers for `auth.force_sso`.
3. **Workspaces:** Implement workspace and membership constraints (slug lower-case check, partial unique defaults, “last owner” guard), refresh services/routes, and back the behaviours with tests.
4. **Documents:** Add the document model with `(workspace_id, sha256)` dedupe, streaming filesystem storage rooted in settings, upload/list/download/soft-delete endpoints, and audit event emission.
5. **Configurations:** Model `DocumentType`, `Configuration`, and `ConfigurationSet`, enforce version sequencing and atomic activation, and align routes/tests around state transitions and workspace isolation.
6. **Jobs:** Redesign the job table with composite foreign keys and lifecycle fields, enforce workspace idempotency, and update submission/status APIs with membership validation and timestamp handling.
7. **Events & Settings:** Finalise the event store and system settings routes, ensuring UTC timestamps and JSON round-trips are thoroughly covered by tests.
8. **QA & Tooling:** Add deterministic fixtures/seeds, refresh documentation/glossary, and run `pytest`, `mypy`, and `ruff` to confirm the refactor meets the acceptance criteria.

---

## 0) Repository Contract

**Assumptions**

* Runtime: Python 3.11+
* Frameworks: FastAPI, SQLAlchemy 2.x (Declarative + Session), Alembic, Pydantic v2
* Test/Lint: pytest, mypy, ruff
* Storage: local filesystem path for blobs (configurable); DB = SQLite (file)
* IDs: ULID strings (`CHAR(26)`) for all entity PKs except natural keys called out below

---

## 1) In/Out of Scope

**In scope**

* ORM models, mixins, enums, Alembic **base migration** (fresh baseline).
* FastAPI routes/services: `auth`, `workspaces`, `documents`, `configurations`, `jobs`, `events`, `system_settings` (minimal).
* Pydantic schemas, seeds, fixtures, tests.
* Session‑level timestamp stamping (replaces DB triggers in SQLite).
* Audit event logging.

**Out of scope**

* Downstream analytics/extracted tables, admin UI, historical migrations/backcompat, broad document type registry (keep minimal set only used by configs/jobs).

---

## 2) Architecture Rules (enforced)

1. **Single source of truth:** DB constraints enforce invariants (defaults, actives). No derived duplicates.
2. **Workspace isolation:** Every tenant‑owned row has `workspace_id`. Composite FKs/uniques prevent cross‑tenant references.
3. **Aware timestamps:** Use timezone‑aware UTC `datetime`. `before_flush` stamps `updated_at` on dirty rows. Plan to migrate to DB triggers on Postgres.
4. **Lean JSON:** Use JSON columns only for flexible payloads/settings (`payload`, `metrics`, `logs`, `metadata`, `system_settings.value`).
5. **Naming:** plural snake_case tables; `_id` for identifiers; `_at` for timestamps.
6. **ULIDs:** `CHAR(26)` + CHECK length at DB, plus application‑level validation.
7. **SQLite‑first constraints:** Partial unique indexes via `WHERE`; regex checks deferred until Postgres.

---

## 3) Canonical Data Model (agent‑parsable)

> Use SQLAlchemy `Enum(native_enum=False)`; store timezone-aware datetimes as ISO strings in SQLite. All JSON stored as TEXT with `json.dumps`/`json.loads` in services/schemas.

```yaml
enums:
  user_system_role: [admin, user]
  workspace_role:   [owner, member]       # 'viewer' later
  job_status:       [pending, running, succeeded, failed, canceled]
  configuration_state: [draft, active, archived]

tables:

  users:
    pk: user_id (CHAR(26))
    uniques: [email_canonical]
    checks:
      - length(user_id)=26
      - email_canonical = lower(email_canonical)
      - system_role in enums.user_system_role
    fks:
      created_by_user_id -> users.user_id ON DELETE SET NULL
    cols:
      email (TEXT, !null)
      email_canonical (TEXT, !null, unique, lower-cased)
      password_hash (TEXT, null)
      display_name (TEXT, null)
      description (TEXT, null)
      is_service_account (INT, !null, default=0)
      is_active (INT, !null, default=1)
      system_role (TEXT, !null)
      last_login_at (TEXT, tz, null)
      created_at/updated_at (TEXT, tz, defaults: now)

  identity_providers:
    pk: provider_id (TEXT slug)
    cols:
      label (!null), icon_url, start_url, enabled (default=1), sort_order (default=0)
      created_at/updated_at

  user_identities:
    pk: identity_id (CHAR(26))
    uniques:
      - [provider_id, subject]
    checks: [length(identity_id)=26]
    fks:
      user_id -> users.user_id ON DELETE CASCADE
      provider_id -> identity_providers.provider_id ON DELETE RESTRICT
    cols:
      subject (!null), email_at_provider (null)
      created_at/updated_at

  api_keys:
    pk: api_key_id (CHAR(26))
    uniques: [token_prefix, token_hash]
    checks: [length(api_key_id)=26, length(token_prefix)=12]
    fks: user_id -> users.user_id ON DELETE CASCADE
    cols:
      token_prefix (!null), token_hash (!null)
      expires_at, last_seen_at, last_seen_ip, last_seen_user_agent
      created_at/updated_at

  system_settings:
    pk: key (TEXT)
    cols: value (TEXT JSON), created_at/updated_at

  workspaces:
    pk: workspace_id (CHAR(26))
    uniques: [slug]
    checks: [length(workspace_id)=26, slug=lower(slug)]
    fks: created_by_user_id -> users.user_id ON DELETE SET NULL
    cols:
      name (!null), slug (!null lc), settings (TEXT JSON default '{}')
      archived_at, created_at/updated_at

  workspace_memberships:
    pk: workspace_membership_id (CHAR(26))
    uniques: [[user_id, workspace_id]]
    partial_uniques:
      - name: uq_workspace_memberships_default_per_user
        columns: [user_id]
        where: "is_default = 1"
    checks: [length(workspace_membership_id)=26, role in enums.workspace_role]
    fks:
      workspace_id -> workspaces.workspace_id ON DELETE CASCADE
      user_id -> users.user_id ON DELETE CASCADE
    cols:
      role (default 'member'), is_default (0/1), created_at/updated_at

  # Minimal registry
  document_types:
    pk: document_type_key (TEXT)
    cols: display_name, created_at/updated_at

  configurations:
    pk: configuration_id (CHAR(26))
    uniques:
      - [workspace_id, document_type_key, version]
      - [configuration_id, workspace_id]   # for composite FKs
    checks: [length(configuration_id)=26, state in enums.configuration_state]
    fks:
      workspace_id -> workspaces.workspace_id ON DELETE CASCADE
      document_type_key -> document_types.document_type_key ON DELETE RESTRICT
      published_by_user_id -> users.user_id ON DELETE SET NULL
    cols:
      title, version (int), state (default 'draft')
      activated_at, published_at, revision_notes
      payload (TEXT JSON default '{}'), created_at/updated_at

  configuration_sets:
    pk: (workspace_id, document_type_key)
    uniques: [[workspace_id, document_type_key]]
    composite_fks:
      - [active_configuration_id, workspace_id] -> configurations(configuration_id, workspace_id) ON DELETE SET NULL
    fks:
      workspace_id -> workspaces.workspace_id ON DELETE CASCADE
      document_type_key -> document_types.document_type_key ON DELETE RESTRICT
    cols: active_configuration_id (nullable)

  documents:
    pk: document_id (CHAR(26))
    uniques: [[document_id, workspace_id]]
    partial_uniques:
      - name: uq_documents__ws_sha256_active
        columns: [workspace_id, sha256]
        where: "deleted_at IS NULL"
    checks: [length(document_id)=26, byte_size >= 0]
    fks:
      workspace_id -> workspaces.workspace_id ON DELETE CASCADE
      created_by_user_id -> users.user_id ON DELETE SET NULL
      deleted_by_user_id -> users.user_id ON DELETE SET NULL
    cols:
      original_filename, content_type, byte_size, sha256, stored_uri
      metadata (TEXT JSON default '{}'), expires_at
      deleted_at, delete_reason
      created_at/updated_at
    indexes:
      - [workspace_id, created_at]

  jobs:
    pk: job_id (CHAR(26))
    uniques: [[job_id, workspace_id]]
    partial_uniques:
      - name: uq_jobs__ws_idem
        columns: [workspace_id, idempotency_key]
        where: "idempotency_key IS NOT NULL"
    checks: [length(job_id)=26, status in enums.job_status]
    fks:
      workspace_id -> workspaces.workspace_id ON DELETE CASCADE
      created_by_user_id -> users.user_id ON DELETE RESTRICT
    composite_fks:
      - [configuration_id, workspace_id] -> configurations(configuration_id, workspace_id) ON DELETE RESTRICT
      - [input_document_id, workspace_id] -> documents(document_id, workspace_id) ON DELETE RESTRICT
      - [parent_job_id, workspace_id] -> jobs(job_id, workspace_id) ON DELETE SET NULL
    cols:
      configuration_id, input_document_id, status
      queued_at (default now), started_at, finished_at
      attempt (int default 1), parent_job_id, priority (int default 0)
      metrics (TEXT JSON '{}'), logs (TEXT JSON '[]')
      error_code, error_message, idempotency_key
      created_at/updated_at
    indexes:
      - [workspace_id, status, queued_at]
      - [workspace_id, finished_at]

  events:
    pk: event_id (CHAR(26))
    checks: [length(event_id)=26]
    fks: workspace_id -> workspaces.workspace_id ON DELETE SET NULL
    cols:
      event_type, entity_type, entity_id
      occurred_at (default now)
      actor_type, actor_id, actor_label
      source, request_id
      payload (TEXT JSON '{}')
    indexes:
      - [workspace_id, occurred_at]
      - [entity_type, entity_id]
```

**SQLite specifics**

* TIMESTAMPTZ simulated via `DateTime(timezone=True)` → ISO string storage; always UTC.
* Partial unique indexes supported (`WHERE`).
* No regex checks; keep lowercase constraints via `CHECK col = lower(col)`.
* `before_flush` hook updates `updated_at`; plan to swap to triggers on Postgres.

---

## 4) API Contract (unchanged surface, explicit shapes)

**Auth**

* `GET /auth/providers` → list enabled providers
  Response: `[{ provider_id, label, icon_url, start_url, enabled, sort_order }]`
* `GET /auth/me` → current user profile & memberships
  Response: `{ user_id, email, display_name, system_role, memberships: [{workspace_id, role, is_default}] }`

**Workspaces**

* `GET /workspaces` (for current user)
* `POST /workspaces` (admin only) body: `{name, slug}`
* `POST /workspaces/{id}/default` (flip default for caller)
* `GET /workspaces/{id}`

**Documents**

* `POST /documents/upload` (multipart): `file: UploadFile`, `workspace_id`
  Response: `{document_id, sha256, byte_size, stored_uri, created_at}`
* `GET /documents` query: `workspace_id`, paging
* `GET /documents/{id}/download` → `FileResponse`
* `PATCH /documents/{id}` body: `{metadata?}`
* `DELETE /documents/{id}` → soft delete; emits event

**Configurations**

* `POST /configurations` body: `{workspace_id, document_type_key, title, payload}` → creates version `n+1 (draft)`
* `POST /configurations/{id}/publish` → sets `published_at`, `state=draft|active` (see below)
* `POST /configuration_sets/activate` body: `{workspace_id, document_type_key, configuration_id}` → flips active pointer atomically
* `GET /configurations` / `GET /configuration_sets`

**Jobs**

* `POST /jobs` body: `{workspace_id, configuration_id, input_document_id, idempotency_key?}`
* `GET /jobs` / `GET /jobs/{id}`
* `PATCH /jobs/{id}` (internal) body: lifecycle updates (`status`, `started_at/finished_at`, `metrics`, `logs`, `error_*`)

**Events**

* `GET /events` query: `workspace_id?`, `entity_type?`, `entity_id?`, time window

**System Settings**

* `GET /system-settings/{key}` / `PUT /system-settings/{key}` (admin)

**Permission fences**

* All workspace-bound operations require membership; role `owner` for admin-ish workspace actions.
* Cross-workspace access is invalid by design (enforced via DB FKs + service guards).

---

## 5) Implementation Tasks (Phased, deterministic)

> Execute phases in order. Each checkbox implies code + tests + docs where noted. Use ULIDs everywhere.

### Phase A — Foundation

* [ ] Add `core/ulid.py` (generate/validate ULIDs) and validators (len=26).
* [ ] Add `domain/mixins.py` → `TimestampMixinTZ` (`created_at`, `updated_at`).
* [ ] Add `core/db.py`: engine/session factory; enable SQLite FK pragma; SQLAlchemy event `before_flush` to set `updated_at` on dirty instances.
* [ ] Centralize enums in `domain/enums.py`.
* [ ] Create Alembic base migration `0001_initial_schema.py` implementing schema above (tables, indexes, partial uniques, composite FKs, CHECKs).
* [ ] Docs: `docs/schema.md` (SQLite vs Postgres notes).

### Phase B — Identity & Auth

* [ ] Models: `IdentityProvider`, `User`, `UserIdentity`, `ApiKey`. Remove any legacy `users.sso_*`.
* [ ] Service: `services/auth_service.py` with email canonicalization (lowercase) on create/update.
* [ ] Expose `/auth/providers`, `/auth/me`.
* [ ] Add `system_settings['auth.force_sso']` helper.
* [ ] Tests: user creation, email lowercasing, identity uniqueness `[provider_id, subject]`, `auth.force_sso` read.

### Phase C — Workspaces & Memberships

* [ ] Models: `Workspace`, `WorkspaceMembership`. Enforce unique `[user_id, workspace_id]` and partial unique default per user.
* [ ] Service: default flip with single SQL update; guard “cannot remove last owner”.
* [ ] Slug canonicalization (lowercase) + DB CHECK.
* [ ] Routes: list/get/create, default flip.
* [ ] Tests: default uniqueness, owner rule, slug lowercasing.

### Phase D — Documents (FastAPI Upload)

* [ ] Model: `Document` (composite unique `[document_id, workspace_id]`, partial unique `(workspace_id, sha256) WHERE deleted_at IS NULL`).
* [ ] Storage: `storage/filesystem_store.py` that streams `UploadFile` to disk while computing `sha256` and `byte_size`; returns `stored_uri` (e.g., `file://.../ws/<workspace_id>/<ulid>`).
* [ ] Router/service: upload, list, download (`FileResponse`), metadata update, soft delete (set `deleted_at`, `deleted_by_user_id`, `delete_reason`).
* [ ] Emit `events` on upload/delete with workspace context.
* [ ] Tests: upload→download→delete, dedupe enforcement, workspace isolation.

### Phase E — Configurations

* [ ] Models: `DocumentType`, `Configuration`, `ConfigurationSet`.
* [ ] Service: create versioned rows; `version = max(version)+1 per (workspace_id, document_type_key)`; `activate` flips pointer in one transaction.
* [ ] Routes: CRUD list/get + activation endpoint.
* [ ] Tests: version sequencing; pointer integrity; isolation; `state` transitions (`draft`→`active`→`archived`).

### Phase F — Jobs

* [ ] Model: `Job` with lifecycle timestamps, metrics/logs JSON, idempotency per workspace.
* [ ] Service: submit validates same‑workspace (`configuration_id`, `input_document_id`) and membership; enforce idempotency key unique (workspace).
* [ ] Router: submit/list/get; internal patch for status transitions.
* [ ] Tests: lifecycle happy path, failure scenarios (FK, cross‑workspace rejection, idempotency).

### Phase G — Events & System Settings

* [ ] Model: `Event`; repository helpers to filter by `workspace_id`, `entity_type`, `entity_id`.
* [ ] Routes: `GET /events` and `GET/PUT /system-settings/{key}` (admin).
* [ ] Tests: event persistence with UTC timestamps; filtering; JSON value round‑trip.

### Phase H — Tests, Seeds, Docs

* [ ] Fixtures/factories: ULIDs, aware datetimes, canonicalized emails/slugs.
* [ ] `seeds/seed_minimal.py`: identity provider, admin user, example workspace, default membership.
* [ ] Docs: schema reference, glossary, upload flow, SQLite vs Postgres differences.
* [ ] Repo meta: `ruff`, `mypy` configs tuned; CI job runs `pytest`, `mypy`, `ruff`.

---

## 6) Deterministic Acceptance Tests (Definition of Done)

> Prefix tests with IDs so they’re easy to assert programmatically.

**Schema & Migrations**

* [ ] **AC-S1**: Running `alembic upgrade head` on a clean SQLite DB creates all tables, indexes, CHECKs, partial uniques, composite FKs exactly as specified (names included).
* [ ] **AC-S2**: A second `alembic revision --autogenerate` yields **no diffs**.

**Normalization & Canonicalization**

* [ ] **AC-N1**: Inserting `users.email_canonical` with mixed case fails; only lower-case values are accepted; service layer always stores lower-case.
* [ ] **AC-N2**: `workspaces.slug` is stored lower-case; DB rejects mixed‑case via CHECK.

**ULIDs & Timestamps**

* [ ] **AC-U1**: Any PK with wrong length fails DB CHECK.
* [ ] **AC-T1**: `updated_at` changes on any ORM update within a transaction via `before_flush`.

**Membership Constraints**

* [ ] **AC-M1**: `workspace_memberships` allows only **one default per user** (partial unique).
* [ ] **AC-M2**: Attempt to demote the **last owner** of a workspace is rejected.

**Documents**

* [ ] **AC-D1**: Upload returns `{document_id, sha256, byte_size, stored_uri}`; file round‑trips via download.
* [ ] **AC-D2**: Re‑upload of same content in same workspace (not deleted) violates partial unique `(workspace_id, sha256)` and is handled as a **409**.
* [ ] **AC-D3**: Soft‑deleted duplicate may be re‑uploaded (partial unique ignores `deleted_at IS NOT NULL`).

**Configurations**

* [ ] **AC-C1**: New configuration version increments per `(workspace_id, document_type_key)`.
* [ ] **AC-C2**: `configuration_sets` always points to **<=1** active configuration for a pair; flip occurs in one transaction and yields consistent reads.

**Jobs**

* [ ] **AC-J1**: Submitting a job with mismatched workspace for `configuration_id` or `input_document_id` fails with **400**/**422** (service enforcement + FK).
* [ ] **AC-J2**: Idempotency key re-use within the same workspace yields **200** with the original job (or **409**), never duplicates.
* [ ] **AC-J3**: `status` transitions record timestamps (`started_at`, `finished_at`) and metrics/logs JSON round‑trip.

**Events & Settings**

* [ ] **AC-E1**: Upload/Delete emit `events` rows carrying `workspace_id`, entity info, and UTC `occurred_at`.
* [ ] **AC-E2**: `system_settings` JSON values persist and parse; `auth.force_sso` boolean round‑trips.

**Quality Gates**

* [ ] **AC-Q1**: `pytest` green; `mypy` strict‑enough mode passes; `ruff` clean.
* [ ] **AC-Q2**: Smoke tests: auth/workspace/document/configuration/job endpoints all respond as expected.


---



## 15) Glossary

* **Configuration**: versioned settings per `(workspace, document_type)`.
* **ConfigurationSet**: pointer to a single **active** configuration per `(workspace, document_type)`.
* **Event**: audit trail for significant actions (upload, delete, activation, job lifecycle).
* **Default membership**: at most one default workspace per user (partial unique).

---

### Done when

All **Acceptance Tests** in §6 pass, endpoints operate per §4, docs in `docs/` reflect SQLite vs Postgres behaviors, and the Alembic autogenerate produces **no diffs** after the base migration.

---
