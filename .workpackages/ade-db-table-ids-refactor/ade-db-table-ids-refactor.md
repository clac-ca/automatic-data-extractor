# ADE DB Table ID Prefix Standardization
> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

* [x] Capture current ID formats (length, generator, prefix) across DB tables and code.
* [ ] Finalize canonical prefix map + generator rules for each resource type (OpenAI-style).
* [ ] Map schema churn (column lengths, defaults, constraints) needed to adopt timestamped hex IDs.
* [ ] Plan rollout across API/engine/CLI + storage paths and testing strategy.
* [ ] Document migration/backfill + compatibility story (handling existing IDs).

---

# ADE DB Table ID Prefix Standardization

## 1. Objective

**Goal:**
Adopt OpenAI-style, time-ordered prefixed IDs (e.g., `ws_<timehex>`, `run_<timehex>`) across tables, storage, and APIs, and define the changes needed to reach that state.

You will:

* Establish the definitive prefix + format for each table/record type using timestamped hex payloads.
* Identify schema and code touch points (generators, migrations, storage layouts, API/TS types) impacted by the change.
* Produce a rollout plan that preserves traceability and minimizes breaking changes.

The result should:

* Provide a documented, consistent ID scheme that distinguishes resource types at a glance and sorts by creation time.
* Outline concrete implementation and migration steps for the backend, engine, CLI, and frontend.

---

## 2. Context (What you are starting from)

Current state of IDs:

* **Default IDs are bare ULIDs (26 chars, no prefix).** `ULIDPrimaryKeyMixin` in `apps/ade-api/src/ade_api/shared/db/mixins.py` defaults `id` to `String(26)` via `generate_ulid()` in `apps/ade-api/src/ade_api/shared/core/ids.py`.
* **Initial migration uses plain strings.** `apps/ade-api/migrations/versions/0001_initial_schema.py` sets `id` columns to `String(26)` for most tables and `String(40)` for `runs`/`builds`/FKs pointing to them; no prefixes baked into the schema.
* **Run/Build IDs already have ad-hoc prefixes but different formats.**
  * `RunsService._generate_run_id()` (`apps/ade-api/src/ade_api/features/runs/service.py`) returns `run_{uuid4().hex}` (36 chars, lowercase hex).
  * `BuildsService._generate_build_id()` (`apps/ade-api/src/ade_api/features/builds/service.py`) returns `build_{uuid4().hex}` (38 chars, lowercase hex).
  * Column lengths (40) tolerate these, but the format diverges from ULID-based IDs elsewhere.
* **Tables using ULIDs today (no prefix)** include `users`, `user_credentials`, `user_identities`, `workspaces`, `workspace_memberships`, `permissions`, `roles`, `role_permissions`, `principals`, `role_assignments`, `documents`, `document_tags`, `api_keys`, `system_settings`, `configurations`, plus related FK columns. Frontend/API shapes surface these as opaque strings.
* **Storage layout depends on IDs.** Workspace directory tree under `./data/workspaces/<workspace_id>/...` and run/build subfolders use the raw IDs (see `AGENTS.md` storage section), so prefix changes flow into filesystem paths and any blob/object storage URIs that mirror these IDs.
* **Related guidance:** `docs/developers/workpackages/wp10-standard_db_ids.md` standardized column names to `id` but did not introduce prefixed values; no existing doc covers value-level prefixes.

Known pain points / risks:

* IDs are visually indistinguishable across tables (e.g., workspace vs. document vs. configuration), making debugging and log correlation slower.
* Mixed generators (ULID vs. UUID4 hex) complicate future validation/formatting rules.
* Column lengths are tight for prefixed ULIDs (26 + prefix), so schema updates are required before rollout.
* Changing IDs cascades to API payloads, TS types, CLI/engine telemetry, storage paths, and test fixtures.

---

## 3. Target architecture / structure (ideal)

* **Canonical format:** `<prefix>_<payload>` where `payload` is a 24-byte, timestamp-first hex string (48 lowercase hex chars). First 4 bytes encode epoch seconds (time-sortable), remaining bytes are random. Column length baseline: prefix (3–8 chars) + underscore + 48 → 52–57 chars; set PK/FK columns to `String(60)` for headroom.
* **Proposed prefix map (first pass, swap in timestamped hex payloads):**
  * `usr_<tshex>` — users
  * `ws_<tshex>` — workspaces
  * `wsm_<tshex>` — workspace memberships
  * `perm_<tshex>` — permissions
  * `role_<tshex>` — roles
  * `rperm_<tshex>` — role_permissions
  * `princ_<tshex>` — principals
  * `rassign_<tshex>` — role_assignments
  * `doc_<tshex>` — documents
  * `doctag_<tshex>` — document_tags
  * `apk_<tshex>` — api_keys
  * `sys_<tshex>` — system_settings
  * `cfg_<tshex>` — configurations
  * `run_<tshex>` — runs (replace UUID4 generator; keep prefix)
  * `build_<tshex>` — builds (replace UUID4 generator; keep prefix)
* **Generator strategy:** shared helper `generate_id(prefix: str, *, codec="tshex")` in `shared/core/ids.py` that emits `<prefix>_<timestamp_hex><random_hex>`; used by ORM mixins and service-layer code; remove ad-hoc UUID/ULID generation in services.
* **Schema footprint:** widen relevant `String(26)`/`String(40)` columns and dependent FKs to `String(60)` (or calculated max) to accommodate the new payload; keep autoincrement ints (log IDs) untouched.
* **Cross-layer alignment:** API schemas/TS types expect prefixed strings; storage paths use the same IDs; CLI/engine telemetry validates against prefix-aware regex.

```text
apps/
  ade-api/
    src/ade_api/shared/core/ids.py      # Prefix-aware time-ordered generator + validators
    src/ade_api/shared/db/mixins.py     # PK mixin switches to prefix-based time-ordered IDs
    src/ade_api/features/*/service.py   # Run/Build generators removed in favor of shared helper
    migrations/versions/0001_initial_schema.py  # Column length + defaults updated
  ade-engine/                           # Runtime ID validation/formatting
  ade-cli/                              # CLI-side validation + display helpers
apps/ade-web/src/schema/                # Re-exported API types with prefixed ID docs
tests/                                  # Fixtures updated to new formats
```

---

## 4. Design (for this workpackage)

### 4.1 Design goals

* Make resource type obvious from the ID string while keeping lexical sorting (timestamp-first hex payload).
* Use one generator path to prevent format drift across services.
* Keep migration blast radius predictable (schema length changes, deterministic backfill/forward rules).

### 4.2 Key components / modules

* `shared/core/ids.py` — central prefix-aware, timestamped-hex ID generator and regex/pydantic validators.
* `shared/db/mixins.py` — PK mixin updated to accept a prefix per model/table.
* Run/Build services — consume shared generator instead of local UUID helpers.

### 4.3 Key flows / pipelines

* **ID creation:** model default → prefix-aware timestamped-hex generator → persisted → surfaced via API/TS.
* **Storage addressing:** filesystem/object paths derived from IDs must accept new prefixed form without collisions.
* **Validation:** inbound API params validated against `<prefix>_<timestamped_hex>` patterns; engine/CLI telemetry uses same pattern to correlate runs/builds.

### 4.4 Open questions / decisions

* Should we allow mixed legacy formats during transition (ULID/UUID4 + new timestamped hex), or backfill everything? If mixed, how do we validate and index efficiently?
* Column length standard: `String(60)` everywhere vs. tighter calculated max per prefix?
* Do we expose/allow uppercase hex, or normalize to lowercase only (OpenAI-style)?
* Any external integrations expecting bare ULIDs (e.g., webhook consumers, log scrapers) that require dual-format support?
* **Workspace/config routes & API:** Yes—workspace and configuration IDs should adopt the new prefix+timestamp-hex format for consistency, even though they appear in URL routes and API payloads. Plan to (a) widen route and API validators to accept both legacy IDs and new prefixed IDs during transition, and/or (b) prioritize slugs for user-facing URLs while keeping IDs as opaque params elsewhere.

### 4.5 ID reuse boundaries (what shares an ID vs. not)

* **Shared across layers for the same resource (must stay identical across DB/API/storage/logging):**
  * `workspace_id` — DB row, API responses/requests, storage root `./data/workspaces/<workspace_id>/`, telemetry/log context.
  * `configuration_id` — DB row, API payloads, config package storage path (under workspace), telemetry/log context.
  * `document_id` — DB row, document storage path, run references, API payloads, telemetry.
  * `build_id` — DB row, build logs table, venv path (`.../<workspace>/<config>/<build_id>/`), run/build events.
  * `run_id` — DB row, run logs table, run output/log storage dir, telemetry correlation (`ADE_RUN_ID`, traces).
  * `api_key_id` — DB row and any API/CLI surfaces that return key metadata (token value is separate).
* **DB-only (not expected to appear as storage folder names or external identifiers):**
  * RBAC tables (`role_id`, `permission_id`, `role_permission_id`, `principal_id`, `role_assignment_id`, `workspace_membership_id`).
  * `system_settings.id`.
  * Surrogate bridge IDs (e.g., `document_tag_id`) beyond the document/tag pair.
* **Never shared across resource types:** IDs are type-scoped via prefixes; the same payload must not be reused between different resource kinds. Prefix ensures global disambiguation even if payload collides.

---

## 5. Implementation & notes for agents

* Align schema first: widen `String(26)`/`String(40)` PK/FK columns where prefixes will apply; adjust Alembic initial revision accordingly (per AGENTS rules, edit `0001_initial_schema.py` directly if no prod DBs exist).
* Introduce `generate_prefixed_ts_hex(prefix: str)` (timestamped hex) in `shared/core/ids.py` and update mixins/services to use it; remove UUID4- and ULID-specific generators where replaced.
* Update validators/schemas (FastAPI/Pydantic + TS openapi types) to new regex patterns; regenerate via `ade openapi-types` once API schemas change.
* Storage/layout: ensure directory builders (e.g., `storage_layout.py`, run/build paths) work with prefixed IDs; consider shims if existing paths must remain readable.
* Testing: add format assertions for each prefix; update fixtures and factories in `apps/ade-api/tests/**` that call `generate_ulid()` to use the new helper with the correct prefix.
* Commandments: per `AGENTS.md`, run `ade test` before commit and `ade ci` before push; avoid resetting unrelated changes.
