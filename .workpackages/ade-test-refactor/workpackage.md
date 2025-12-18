> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

* [x] Inventory current test harness issues (fixtures/config/isolation). *(Confirmed root vs per-app pytest drift; `ade` CLI command is `test` not `tests`; ade-api startup runs RBAC sync against DB.)*
* [x] Decide canonical pytest entrypoint(s) and config ownership (root vs per-app). *(Canonical: `ade tests` runs pytest per-app in `apps/ade-api`, `apps/ade-engine`, `apps/ade-cli`; pytest config lives in each app `pyproject.toml`. Removed repo-root `pytest.ini` + `conftest.py`.)*
* [x] Refactor ade-api fixtures to avoid global env leakage (use `MonkeyPatch`/explicit `Settings`). *(Deleted legacy `apps/ade-api/conftest.py`; integration tests construct `Settings` directly; env use is limited to a scoped `MonkeyPatch` with undo.)*
* [x] Make DB setup integration-only (no unit-test migrations) and remove session autouse side effects. *(Integration-only `tests/integration/conftest.py` runs migrations once/session; unit tests no longer pay DB startup cost.)*
* [x] Add per-test DB isolation for integration tests (transaction/savepoint or fresh DB per test). *(Per-test outer transaction + per-request savepoints; explicit SQLite `BEGIN` to make savepoints reliable; hard-fails if a test commits the outer transaction.)*
* [x] Remove order-dependent integration tests and manual cache resets inside tests. *(DB state rolls back per test; added autouse `reset_auth_state()`; patched config validation suite to no-op background build jobs.)*
* [x] Stop mutating the shared FastAPI app in tests (fresh app or app factory for special cases). *(Function-scoped `create_app(settings=...)` fixture; tests that need ad-hoc routes construct a local app instance.)*
* [x] Consolidate/relocate misplaced tests (e.g., tests living under `src/ade_api/**/tests`). *(Removed `src/**/tests`; migrated coverage into `apps/ade-api/tests/**`.)*
* [x] Standardize test helpers/imports (no reliance on `tests` as an importable package unless intentional). *(Kept `tests/utils.py` as the explicit helper module; removed repo-root path hacks so imports are consistent when running per-app.)*
* [x] Run `ade tests` and `ade ci`; document runtime deltas and any follow-ups. *(CI green: `ade ci` runs ruff + eslint + pytest (api/engine/cli) + vitest + vite build; approx runtimes: api 36s (169 tests), engine 0.6s (31), cli 0.3s (23), vitest 4.4s, vite build 15s; total ~68s.)*

> **Agent note:**
> Keep brief status notes inline as you complete tasks.

---

# ADE test refactor (standardize backend testing)

## 1. Objective

Make ADE’s Python test suites (primarily `apps/ade-api`) follow standard pytest/FastAPI/SQLAlchemy practices:

* No global state leaks (env vars, cached settings, cached DB engines) across tests.
* Fast and reliable unit tests (no DB migrations for unit suite).
* Deterministic integration tests (each test sets up its own state; no ordering dependencies).
* Clean, conventional fixture layout (`tests/conftest.py` and `tests/integration/conftest.py`).
* A documented, canonical way to run tests locally and in CI (`ade tests` / `ade ci`).

## 2. Context (what exists today)

### 2.1 Current entrypoints/configs

* `ade test` runs backend tests via `pytest -q` with `cwd=apps/ade-api` (`apps/ade-cli/src/ade_cli/commands/tests.py`).
* There is also a repo-root `pytest.ini` and repo-root `conftest.py` that manipulate import paths; they are not used when running from `apps/ade-api` (pytest rootdir becomes `apps/ade-api` because of `apps/ade-api/pyproject.toml`).
* Root vs per-app pytest configuration differs (e.g., root `asyncio_mode=strict` vs `apps/ade-api` `asyncio_mode=auto`), so behavior changes depending on where pytest is invoked.

### 2.2 Non-standard/fragile testing patterns observed

**Global environment mutation (leaky / unsafe):**
* `apps/ade-api/conftest.py` writes to `os.environ` directly (instead of `MonkeyPatch`) and teardown `pop()` does not restore pre-existing values.
* `ADE_JWT_SECRET` is set with `setdefault(...)` but later always removed (`pop()`), which can delete a developer’s real env var.
* OIDC env vars are set but not unset in teardown (`ADE_OIDC_CLIENT_ID`, `..._SECRET`, `..._ISSUER`, `..._REDIRECT_URL`, `..._SCOPES`).
* `override_app_settings` overrides the *FastAPI dependency* for `get_settings`, but does not update the global `get_settings()` cache; tests that call `get_settings()` directly can observe different settings than the running app.

**DB setup is too global and too eager:**
* A session-scoped, `autouse=True` fixture applies Alembic migrations for *every* test run (including unit tests) even when no DB is needed.
* DB migration logic in tests duplicates production logic (`command.upgrade(...)` in conftest vs `ensure_database_ready(...)` elsewhere).
* `seed_identity` calls `ensure_database_ready(...)` even though migrations were already applied in the session fixture (extra work and two migration pathways).

**Order-dependent integration tests / shared DB state:**
* Some tests assume “users exist” based on earlier tests having run (shared DB data persists across tests).
* Some tests manually call `reset_database_state()` / `reset_session_state()` inside a test to force cache resets.

**Shared app mutation:**
* At least one integration test dynamically registers a route on the shared `app` fixture (`apps/ade-api/tests/integration/db/test_session.py`). This persists for the remainder of the session.

**Test placement / discovery issues:**
* Tests exist under `apps/ade-api/src/ade_api/**/tests` which are not included in `apps/ade-api`’s `testpaths=["tests"]` by default, so they may not run consistently.
* Some tests (notably `apps/ade-engine/tests/**`) modify `sys.path` inside test files; prefer editable installs or pytest config over per-test path hacks.

**Minor hygiene:**
* Unused imports exist in test fixtures (e.g., `select` in `apps/ade-api/conftest.py`).
* Fixture typing mismatches exist (e.g., a sync `yield` fixture annotated as `AsyncIterator[None]`).

## 3. Target architecture / structure (ideal)

### 3.1 Canonical pytest invocation

Pick one and document it (decision required):

**Option A (monorepo root run):**
* Run `pytest` from repo root; single root config controls all suites.
* `ade tests` becomes an orchestrator for root-level `pytest` + frontend tests.

**Option B (per-app run, orchestrated):**
* Keep each Python app’s config local (e.g., `apps/ade-api/pyproject.toml`).
* `ade tests` runs `pytest` in `apps/ade-api`, `apps/ade-engine`, and `apps/ade-cli` explicitly (plus frontend tests).

Recommended: **Option B** (keeps configs local, avoids cross-suite config drift).

### 3.2 Fixture layout (ade-api)

```text
apps/ade-api/
  tests/
    conftest.py                    # shared, lightweight fixtures/helpers (no DB migrations)
    integration/
      conftest.py                  # DB + app + http client fixtures for integration
      ...                          # integration tests
    unit/
      ...                          # unit tests (no shared DB)
```

### 3.3 DB isolation approach (integration tests)

Pick one and implement consistently (decision required):

**Option 1 (recommended): transaction + nested savepoint per test**
* Run Alembic migrations once per session on a session-scoped DB.
* For each test:
  * open a connection + begin an outer transaction
  * each request/session runs inside a nested transaction (SAVEPOINT)
  * rollback outer transaction at end of test to reset DB state
* Pros: fast, deterministic, scales well.
* Cons: more complex; needs careful SQLAlchemy/SQLite handling.

**Option 2: fresh SQLite DB file per test**
* For each test, create a new sqlite file + run migrations.
* Pros: simplest mental model.
* Cons: slowest.

**Option 3: truncate tables between tests**
* Keep a single DB and wipe tables per test.
* Pros: simpler than nested tx.
* Cons: needs table ordering/foreign key handling; slower than savepoints.

## 4. Design (for this workpackage)

### 4.1 Design goals

* Eliminate hidden coupling between tests (order, shared DB contents, shared app mutations).
* Keep unit tests fast (no global DB setup unless requested).
* Make integration tests explicit about what they need: `settings`, `db_session`, `client`, `seed_identity`, etc.
* Avoid test-only hacks in production code where possible; if needed, prefer small seams (dependency overrides).

### 4.2 Proposed fixture stack (ade-api integration)

**Core fixtures**
* `settings` (session): explicit `Settings` instance (no `os.environ` mutation).
* `migrated_db` (session): applies Alembic migrations once.
* `db_connection` (function): connection + outer transaction.
* `db_session` (function): `AsyncSession` bound to `db_connection` with nested tx support.
* `app` (function or session): `create_app(settings=settings)` + dependency overrides:
  * override `get_settings` to return the fixture settings
  * override the DB session dependency to use sessions bound to `db_connection`
* `async_client` (function): httpx `AsyncClient` with lifespan.

**Data factories**
* Replace `seed_identity`’s untyped dict with a small dataclass (or typed mapping) and/or provide factory helpers:
  * `create_user(...)`, `create_workspace(...)`, `add_membership(...)`, `assign_role(...)`.
* Ensure tests that need “users exist” explicitly request/create them.

### 4.3 Cleanup/consistency tasks

* Remove repo-root path hacks if `pip install -e ...` is required anyway, or align them with the chosen entrypoint.
* Move `src/**/tests` into `apps/ade-api/tests/...` so they always run.
* Standardize helper imports:
  * Either keep `tests` as a package intentionally, or switch to relative imports / a `tests/_support` package.

### 4.4 Acceptance criteria

* `apps/ade-api` unit tests run without applying Alembic migrations.
* Integration tests do not depend on ordering and can be run individually.
* No test suite run mutates developer environment variables (all env changes are restored).
* No test mutates a shared app instance in a way that persists across tests.
* `ade tests` and `ade ci` pass.

## 5. Implementation notes for agents

* Prefer landing this in small PR-sized steps:
  1) Make env handling safe + remove autouse DB setup
  2) Introduce DB isolation fixture and migrate a few integration modules
  3) Finish migrating integration suite and delete old fixtures
  4) Relocate misplaced tests and standardize helpers/imports
* When changing fixture behavior, update a small set of integration tests first to prove the pattern (auth + runs).
* If SQLite SAVEPOINT semantics get tricky, fall back to “fresh DB per module” as an intermediate step, then iterate.

## 6. Concrete file-level tasks (starting point)

### 6.1 `apps/ade-api` fixtures

* `apps/ade-api/conftest.py`
  * Remove session `autouse=True` DB/migration setup (unit tests shouldn’t pay this cost).
  * Replace direct `os.environ` usage with a session-scoped `pytest.MonkeyPatch()` (or eliminate env entirely by constructing `Settings` explicitly).
  * Fix teardown to restore previous env var values (especially `ADE_JWT_SECRET`) and include missing OIDC teardown vars.
  * Fix incorrect typing (`AsyncIterator` vs `Iterator`) and remove unused imports.
  * Move remaining fixtures into `apps/ade-api/tests/conftest.py` and/or `apps/ade-api/tests/integration/conftest.py`; delete this file if it becomes empty.

* `apps/ade-api/tests/integration/conftest.py`
  * Replace the current `session()` fixture with a consistent DB isolation strategy (preferred: per-test outer tx + nested savepoints).
  * Provide canonical fixtures: `settings`, `engine`/`migrated_db`, `db_connection`, `db_session`, `app`, `async_client`.
  * Override FastAPI dependencies so API requests use the isolated test DB sessions.

* `apps/ade-api/tests/utils.py`
  * Decide whether test helpers live in `tests/_support/...` (package) or as relative imports; update imports accordingly.

### 6.2 `apps/ade-api` flaky/order-dependent tests

* `apps/ade-api/tests/integration/auth/test_auth_router.py`
  * Make “users exist” tests explicitly depend on seeded users (e.g., require `seed_identity`).
  * Remove in-test cache resets (`reset_database_state` / `reset_session_state`) by using fixtures for fresh DB/settings when needed.

* `apps/ade-api/tests/integration/db/test_session.py`
  * Stop mutating the shared `app` (dynamic route registration). Use a fresh app instance for this test (or an `app_factory` fixture).

### 6.3 Test discovery / placement cleanup

* Move `apps/ade-api/src/ade_api/features/documents/tests/*` into `apps/ade-api/tests/unit/features/documents/*` (or another consistent location).
  * Ensure they run under `testpaths=["tests"]` and have access to required fixtures.

### 6.4 Monorepo test entrypoints/config drift

* Decide between “single root pytest run” vs “per-app orchestrated runs”.
  * If choosing per-app runs: update `apps/ade-cli/src/ade_cli/commands/tests.py` so `ade tests` runs:
    * `pytest` in `apps/ade-api`
    * `pytest` in `apps/ade-engine`
    * `pytest` in `apps/ade-cli`
  * Remove or clearly document repo-root `pytest.ini` and repo-root `conftest.py` path hacks to avoid confusion.

* `apps/ade-engine/tests/**`
  * Remove per-test `sys.path.insert(...)` calls; rely on editable installs or config-managed pythonpath.
