# Work Package: Backend Folder Restructure

> **Agent instructions**
>
> 1. Read this entire file once before starting.
> 2. Work top‑to‑bottom through the milestones. Update checkboxes in place (`[x]` when done).
> 3. Keep *Session Handoff* current.

## Session Handoff

**Completed in Last Session**

* Relocated Alembic artifacts under `ade/db/migrations`, refreshed docs, and pointed `alembic.ini` at the new location.
* Updated the Alembic env to import feature models so autogenerate sees the full metadata.
* Folded the database bootstrap helpers into `ade/db/engine.py` and removed the legacy `bootstrap.py` module.
* Split shared security dependencies between platform (`ade/platform/security/`) and feature modules (`ade/features/auth/roles`).
* Added feature-scoped repositories/dependency providers for documents, configurations, users, jobs, and health to keep routers thin.

**Next Step for Incoming Agent**

* Turn to milestone 6 (tests & fixtures) now that the API shell is slim and feature scaffolding is in place.

---

## Design & folder philosophy

* **Thin `api/`**: HTTP shell only—route composition, global deps, error mapping.
* **Vertical `features/`**: each feature owns its `models`, `schemas`, `repository`, `service`, `deps`, `router` (and tests). Business logic lives here.
* **`platform/` for app plumbing**: config, logging, security primitives, pagination, middleware—things used by most features. (Common and broadly recognized.)
* **`db/` is the only persistence layer**: engine, session, Alembic migrations in one place. Defaults to **SQLite** now; can swap later.
* **`adapters/` for external integrations**: today just **filesystem storage** and a **SQLite‑polled queue** (no Redis/S3/Postgres). Later you can drop in alternative adapters without touching features.
* **`workers/` are process entrypoints**: no business logic—just loop + lifecycle wiring to call feature tasks.
* **Tests close to code**: per‑feature tests under the feature; cross‑cutting fixtures in root `tests/`.
* **Documentation baked in**: every top folder has a short README with “put X here when …”.
* **No legacy shims**: delete obsolete modules once callers migrate; `ade/app.py` and `ade/platform/config.py` are the canonical entry points (no `ade/main.py` or `ade/settings.py` compatibility layers).

**Dependency rule of thumb**

```
api  → features → (platform + adapters) → db
workers  ┐
cli      ┘  → features (+ platform/adapters) → db

No feature → feature imports.
platform/adapters never import features.
```

---

## Desired folder structure (with inline comments)

```text
ade/
  __init__.py
  app.py                    # create_app(): FastAPI app factory, mounts v1 router
  lifecycles.py             # startup/shutdown hooks

  api/                      # HTTP "shell": composition, versioning, error mapping
    __init__.py
    deps.py                 # cross-cutting deps only (db session, settings)
    errors.py               # domain exception → HTTP response mapping
    v1/
      __init__.py
      router.py             # includes feature routers; no business logic

  platform/                 # app-wide plumbing used by many features
    __init__.py
    config.py               # Pydantic Settings (single source of truth)
    logging.py              # structured logging setup
    middleware.py           # CORS, request-id, timing, base CSRF protection
    time.py                 # time helpers
    ids.py                  # ULID/UUID helpers
    pagination.py           # Page/PageParams primitives
    responses.py            # common response envelopes
    security/
      __init__.py
      crypto.py             # hashing, token signing/verifying
      csrf.py               # CSRF primitives (no FastAPI deps)

  db/                       # all persistence glue in one place
    __init__.py
    engine.py               # make_engine() → SQLite by default
    session.py              # SessionLocal, get_session() FastAPI Depends
    base.py                 # DeclarativeBase metadata import here
    mixins.py               # Timestamped, ULID mixins
    migrations/             # Alembic environment + versions
      env.py
      script.py.mako
      versions/
        0001_initial.py

  adapters/                 # external system connectors (today: local-only)
    __init__.py
    storage/
      __init__.py
      base.py               # interface: save_file(), open_stream(), delete()
      filesystem.py         # local data dir implementation (default)
    queue/
      __init__.py
      base.py               # interface: enqueue(), claim_next(), ack(), retry()
      sqlite_poll.py        # simple SQLite-backed poller (works with single/local worker)

  features/                 # vertical slices; business logic lives here
    auth/
      __init__.py
      models.py
      schemas.py
      repository.py
      service.py
      deps.py               # FastAPI Depends for this feature (require_authenticated, etc.)
      router.py
      tests/
        test_router.py
        test_service.py

    roles/
      __init__.py
      authorization.py      # feature-level policy building on platform.security
      models.py
      registry.py
      schemas.py
      repository.py
      service.py
      deps.py
      router.py
      tests/

    users/
      __init__.py
      models.py
      schemas.py
      repository.py
      service.py
      deps.py
      router.py
      tests/

    workspaces/
      __init__.py
      models.py
      schemas.py
      repository.py
      service.py
      deps.py
      router.py
      tests/

    documents/
      __init__.py
      models.py
      schemas.py
      storage.py            # uses adapters.storage.* behind a small wrapper
      filtering.py
      repository.py
      service.py            # upload, list, delete; no engine logic
      deps.py
      router.py
      tests/

    configurations/
      __init__.py
      models.py
      schemas.py
      validation.py
      repository.py
      service.py
      deps.py
      router.py
      tests/

    jobs/
      __init__.py
      models.py
      schemas.py
      repository.py
      processor.py          # execution engine orchestrator (pure logic)
      service.py            # submit, fan-out, status, uses adapters.queue
      tasks.py              # thin queueable units calling service/processor
      deps.py
      router.py
      tests/

    health/
      __init__.py
      router.py
      service.py
      tests/

  workers/                  # process entrypoints only
    __init__.py
    run_jobs.py             # loop: claim from adapters.queue.sqlite_poll, execute tasks

  cli/                      # Typer CLI entrypoints
    __init__.py
    main.py
    commands/
      dev.py
      users.py
      reset.py
      settings.py

  web/                      # optional static serving (can be disabled in prod)
    README.md
    static/
      index.html
      assets/

# repo root
tests/                      # shared fixtures + cross-cutting tests
  conftest.py               # app fixture, db fixture (SQLite), temp data dir fixture
  test_api_health.py
  test_security.py

AGENTS.md
agents/                     # work packages, glossaries, agent prompts
docs/
pyproject.toml
alembic.ini                 # points to ade/db/migrations
.env.example
README.md
py.typed
```

**Why this tree is “obvious” (and future‑proof)**

* Common names (`api`, `features`, `platform`, `db`) that agents recognize.
* Clear “area of responsibility”: when adding Excel/PDF logic later, it naturally expands under `features/jobs/processor.py` (with submodules) without moving existing code.
* Adapters let you keep **local FS + SQLite** now and swap in S3/Redis/Rabbit later by adding files under `adapters/`—not by editing features.

---

## Future needs (design notes, not added yet)

> We **do not** create these folders now; this is the planned landing zone.

* **Excel ingestion & table detection**
  Add to `features/jobs/processor.py` as submodules:

  * `excel_io.py` (openpyxl/pyxlsb/pyarrow integration)
  * `table_detect/row_scoring.py` (header/data/blank scoring)
  * `table_detect/segmenter.py` (contiguous block detection)
  * `table_detect/validators.py` (min rows/cols, header heuristics)

* **PDF conversion**
  `pdf_io.py` (pdfminer/pymupdf), `pdf_to_tables.py` (lattice/stream hybrid), shared scoring utilities reused with Excel detection.

* **Column analysis & transforms**
  `column_infer/runner.py` (exec configuration scripts per column, total scores),
  `column_infer/normalizer.py` (assign normalized headers),
  `transforms/runner.py` (transform steps declared in config scripts).

* **Export & download**
  `exporters/xlsx.py`, `exporters/csv_zip.py`.
  Documents feature continues to use **filesystem storage** via `adapters.storage.filesystem` for download links.

* **Queue alternatives**
  Add `adapters/queue/redis_rq.py` or `postgres.py` later, then flip a single setting.

---

## Milestones & tasks

### 1) Scaffolding & contracts

* [x] Add `ade/platform/config.py` with a single `Settings` model (env‑driven; defaults for SQLite, local `DATA_DIR`).【F:ade/platform/config.py†L1-L494】
* [x] Add `ade/db/engine.py` + `session.py` (SQLite by default); unify session dependency.【F:ade/db/engine.py†L1-L157】【F:ade/db/session.py†L1-L88】
* [x] Add `ade/adapters/storage/base.py` & `filesystem.py`; default to `{DATA_DIR}/uploads`.【F:ade/adapters/storage/base.py†L1-L60】【F:ade/adapters/storage/filesystem.py†L1-L118】
* [x] Add `ade/adapters/queue/base.py` & `sqlite_poll.py` (polls `jobs` table status).【F:ade/adapters/queue/base.py†L1-L43】【F:ade/adapters/queue/sqlite_poll.py†L1-L158】
* [x] Create `ade/v1/router.py` that composes feature routers.【F:ade/v1/router.py†L1-L24】
* [x] Create `ade/app.py` (`create_app()`), `lifecycles.py` (startup/shutdown).【F:ade/app.py†L1-L205】【F:ade/lifecycles.py†L1-L60】

**Acceptance**

* `uvicorn ade.app:create_app` boots; `/health` returns 200.
* `DATA_DIR` auto‑created; file save/read works.

### 2) Move DB + migrations into `db/`

* [x] Move `ade/alembic/*` → `ade/db/migrations/*`; update `alembic.ini` (`script_location`).【F:ade/db/migrations/env.py†L1-L120】【F:alembic.ini†L1-L4】
* [x] Fold `bootstrap.py` into `engine.py`/`session.py` (one session home).【F:ade/db/engine.py†L129-L190】
* [x] Ensure the Alembic environment imports all feature models for autogenerate (without reintroducing circular imports).【F:ade/db/migrations/env.py†L18-L33】

**Acceptance**

* `alembic upgrade head` succeeds against SQLite.
* Root tests use the same session factory.

### 3) Extract platform from “core”

* [x] Move `ids.py`, `pagination.py`, `responses.py`, `time.py`, `logging.py`, `middleware.py` into `platform/`.【F:ade/platform/ids.py†L1-L12】【F:ade/platform/pagination.py†L1-L106】【F:ade/platform/responses.py†L1-L123】【F:ade/platform/time.py†L1-L14】【F:ade/platform/logging.py†L1-L98】【F:ade/platform/middleware.py†L1-L94】
* [x] Split `api/security.py`: primitives → `platform/security/*`; feature deps → `features/auth`/`roles` dependencies.【F:ade/platform/security/permissions.py†L1-L41】【F:ade/features/auth/dependencies.py†L87-L130】【F:ade/features/roles/dependencies.py†L1-L109】

**Acceptance**

* No imports from `ade/settings.py` exist (all via `platform.config.Settings`).
* `grep -R "api/security" ade/` returns only router imports (if any backwards re‑exports).

### 4) Normalize features

* [ ] Ensure each feature has: `models.py`, `schemas.py`, `repository.py`, `service.py`, `deps.py`, `router.py`, `tests/`.
* [x] Add feature-scoped service dependencies/repositories for documents, configurations, jobs, users, and health.【F:ade/features/documents/dependencies.py†L1-L21】【F:ade/features/jobs/repository.py†L1-L46】【F:ade/features/jobs/dependencies.py†L1-L21】【F:ade/features/users/dependencies.py†L1-L17】【F:ade/features/health/dependencies.py†L1-L17】
* [x] Move any stray guards to respective `deps.py`.【F:ade/features/auth/dependencies.py†L87-L130】【F:ade/features/roles/dependencies.py†L1-L109】
* [x] In **jobs**: introduce `tasks.py` (queueable), keep compute in `processor.py`, orchestration in `service.py`.【F:ade/features/jobs/tasks.py†L1-L58】【F:ade/features/jobs/service.py†L1-L140】
* [x] Scaffold `system_settings` service/dependency for future admin surfaces.【F:ade/features/system_settings/service.py†L1-L45】【F:ade/features/system_settings/dependencies.py†L1-L21】

**Acceptance**

* No feature imports another feature.
* Jobs can be enqueued and processed locally (single worker) with SQLite poller.

### 5) Thin the API shell

* [x] Limit `ade/api/` to shared settings/errors; feature deps now live under their respective packages.【F:ade/api/__init__.py†L1-L6】【F:ade/api/settings.py†L1-L25】【F:ade/api/errors.py†L1-L60】
* [x] All route inclusion happens in `ade/v1/router.py`.【F:ade/v1/router.py†L1-L24】

**Acceptance**

* `api/` contains no business logic.

### 6) Tests & fixtures

* [ ] Move duplicate test roots under `features/*/tests/` or root `tests/`.
* [ ] `tests/conftest.py`: app fixture, db fixture (SQLite), temp `DATA_DIR` fixture.
* [ ] Minimal tests for upload (filesystem), job enqueue/run (sqlite poller), health.

**Acceptance**

* `pytest -q` passes locally and in CI.

### 7) Lint, types, import rules

* [ ] Add **ruff** + **mypy** configs; enable SQLAlchemy + Pydantic plugins.
* [ ] Add **import‑linter** (or ruff rules) to enforce dependency graph.

**Acceptance**

* CI blocks on lint/type/import violations.
* Layers contract prevents feature‑to‑feature imports.

### 8) README rollout

* [ ] Short README in each top folder (`api/`, `platform/`, `db/`, `adapters/`, `features/`, `workers/`) with purpose + “put files here when …”.
* [ ] Update `AGENTS.md` with this map and common tasks (e.g., “Add a new queue backend”).

---

## Mechanical changes (search/replace guide)

* Replace imports from `ade.settings` → `from ade.platform.config import Settings`.
* Replace `from ade.api.security import ...` →

  * Authentication guards: `from ade.features.auth.dependencies import require_authenticated, require_csrf`
  * Permission guards: `from ade.features.roles.dependencies import require_global`, etc.
* Update Alembic config: `script_location = ade/db/migrations`.

---

## Guardrails (configs)

**`pyproject.toml` (snippets)**

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E","F","I","N","UP","B","PL","RUF","ARG","PTH"]
ignore = ["D"]  # enable later if you want docstrings
[tool.ruff.lint.isort]
known-first-party = ["ade"]

[tool.mypy]
python_version = "3.11"
plugins = ["pydantic.mypy", "sqlalchemy.ext.mypy.plugin"]
disallow_untyped_defs = true
warn_unused_ignores = true
```

**`.importlinter`**

```ini
[importlinter]
root_package = ade

[contract:layers]
name = Layered architecture
layers =
    ade.db
    ade.adapters
    ade.platform
    ade.features
    ade.api
```

---

## Risks & mitigations

* **SQLite concurrency**: safe for single‑node, modest throughput. Mitigate with short transactions; worker uses `SELECT … FOR UPDATE`-like pattern via status transitions (claim → running → done).
* **Background work timing**: `sqlite_poll` is a poller; keep interval reasonable (e.g., 250–500ms). We can later switch to Redis/Postgres by adding an adapter only.
* **File system storage**: ensure `DATA_DIR` is configurable and temp‑dir safe in tests.

---

## Exit criteria

* The tree matches “Desired folder structure.”
* The app boots from `ade.app:create_app`.
* Upload → run (queued) → worker processes → status surfaces, entirely with SQLite + filesystem.
* Lint, type, and import contracts pass.
* READMEs present and accurate.
* New contributors (or agents) can place code without asking “where does this go?”

---

## Open questions

* Do we want `features/system_settings` or fold these into `platform.config` + admin routes?
* Should `platform.security.csrf` be enabled on all mutating routes now or deferred to when you expose a browser UI directly to API?
* For downloads, will we stream from FS or pre‑generate signed URLs later (adapter concern)?

---

## Quick “Where do I put X?” cheatsheet

* **New API endpoints for jobs** → `features/jobs/router.py` (+ logic in `service.py`/`processor.py`).
* **Authorization checks** → relevant `features/*/deps.py`; policy building blocks in `platform/security` or `features/roles/authorization.py`.
* **Excel/PDF processing** → `features/jobs/processor.py` (later add `excel_io.py`, `pdf_io.py`, and `table_detect/*`).
* **New storage backend** → `adapters/storage/<name>.py`; select in `Settings`.
* **New queue backend** → `adapters/queue/<name>.py`; worker imports via adapter factory.

---
