# 🚧 FastAPI Backend Rebuild Plan

## Status
- **Current Phase:** Phase 3 – Identity, tenancy, and permission framework *(not started; design only).* 
- **Completed Work:**
  - Phase 0 – Scaffolded the new FastAPI backend shell (`backend/app/main.py`, `backend/app/api.py`, health module blueprint, async pytest fixtures).
  - Phase 1 – Established shared configuration, structured logging, middleware, responses, and base services.
  - Phase 2 – Rebuilt the database backbone with async engine/session factories, Alembic environment, baseline migration, and tests covering migration execution plus request-scoped session injection.
- **Completed Pre-work:** Archived the legacy implementation to `backend.backup/` so we can reference behaviour while rebuilding from scratch.

## Phase 0 – Scaffold the new FastAPI backend shell ✅ *Complete*
Established the fresh `backend/` package with an application factory, central router registration, health module blueprint, async pytest fixtures, and documentation describing the rebuild layout. Future phases should extend this structure rather than modifying `backend.backup/`.

## Phase 1 – Core configuration, responses, and service foundations ✅ *Complete*
Structured the backend around shared infrastructure:

- Added `backend/app/core/settings.py` with Pydantic Settings support for environment-specific TOML files and environment variables, plus helpers to reset the cache during tests.
- Introduced `backend/app/core/schema.py`, `responses.py`, `logging.py`, and `service.py` to centralise schema behaviour, JSON responses, structured logging with correlation IDs, and reusable service context/dependencies.
- Registered a `backend/app/extensions/middleware.py` request middleware that injects correlation IDs and emits JSON request logs.
- Updated the health module to inherit from the base service, emit details via the shared response class, and ensured FastAPI uses the new configuration + middleware paths on startup.

**Exit status**
- Application startup and request logs now flow through the JSON formatter with correlation IDs, configuration reads from TOML/env without touching module code, and `/health` returns responses via the shared `JSONResponse`/`BaseSchema` stack.

## Phase 2 – Database and migration backbone ✅ *Complete*
Implemented an async-first persistence layer with consistent naming conventions and automated schema management:

- Introduced `backend/app/db/` with naming-aware declarative base, ULID/timestamp mixins, cached async engine, and a `get_session` FastAPI dependency that binds sessions to `request.state` and `ServiceContext`.
- Wired a dedicated Alembic environment under `backend/app/migrations/` plus a baseline migration recreating the legacy schema with the new constraint/index naming scheme.
- Expanded test fixtures to spin up an ephemeral SQLite database, run migrations, and expose an HTTPX client; added smoke tests validating `alembic upgrade head` and the request-scoped session dependency.

**Exit status**
- `alembic upgrade head` executes cleanly via the rebuilt environment, and session-aware routes commit/rollback through the shared dependency without manual session management.

## Phase 3 – Identity, tenancy, and permission framework
**Goal:** Restore authentication/authorization with the class-based decorator approach described in the feedback while keeping dependencies explicit.

- Port `auth`, `users`, and `tenants` functionality into dedicated `backend/app/modules/<module>/` packages using class-based services and repositories where complexity warrants it.
- Implement an `access_control` decorator (or FastAPI dependency equivalent) capable of enforcing module/resource/superuser flags using the contextual data stored on service instances.
- Adopt class-based views via `fastapi-utils` (or a similar utility) so shared dependencies like `commons = Depends(common_deps)` live on the view class, reducing repetition.
- Ensure authentication dependencies populate context (`current_user`, `tenant_id`, injected sessions via `get_session`) for downstream services without manual parameter threading.
- Provide tests that cover permission checks, decorator behaviour, and common failure paths (unauthenticated, unauthorized, missing tenant).

**Exit criteria**
- Protected routes in the identity modules enforce permissions through the shared decorator/dependency infrastructure.
- Unit and integration tests assert the correct 401/403 handling and context propagation.

## Phase 4 – Domain modules, events, and background processing
**Goal:** Rebuild the ADE-specific modules (documents, configurations, jobs, events) using the new architecture, message hub, and queue strategy.

- Implement `documents`, `jobs`, `configurations`, `maintenance`, and any other domain modules as packages with `router.py`, `schemas.py`, `service.py`, `dependencies.py`, `repository.py`, and `handlers.py` as needed.
- Introduce `backend/app/core/message_hub.py` that broadcasts domain events to subscribed handlers (mirroring the feedback’s `MessageHub`).
- Connect long-running tasks to a queue solution (e.g. RQ, as recommended) with a worker bootstrap script and dependency injection for the queue within services.
- Ensure file uploads/processing use async-friendly patterns (`run_in_threadpool` for blocking I/O) and emit events consumed by other modules via the hub.
- Port utility clients (`mailer`, `filesystem`, etc.) into `backend/app/services/` or module-specific adapters using dependency injection rather than globals.
- Expand tests to cover event emission/handling and background job orchestration.

**Exit criteria**
- Document ingestion flows (upload → extraction → job tracking) function through the rebuilt modules, including event fan-out and queue-based background processing.
- Tests verify at least one cross-module event lifecycle and queued job execution path.

## Phase 5 – API surface, serialization fidelity, and documentation
**Goal:** Finalise path operations with consistent REST semantics, rich metadata, and documentation that reflects the new response strategy.

- Refine routers to use HTTP verbs + resource nouns consistently, eliminating redundant endpoints inherited from the legacy API.
- Replace manual `.model_dump()` / `.model_validate()` usage with response models or the shared response classes, ensuring OpenAPI metadata stays accurate.
- Add detailed route metadata (status codes, tags, descriptions) and hide Swagger/Redoc outside development environments per best practices.
- Provide a `DefaultResponse` schema for generic acknowledgements and update clients/tests to assert against it.
- Refresh `DOCUMENTATION.md` and `README.md` with example requests/responses, module overviews, and guidance on extending the architecture.

**Exit criteria**
- OpenAPI output accurately documents each route’s contract, and documentation clearly explains how to interact with the rebuilt services.
- API smoke tests confirm the new response shapes and metadata are honoured.

## Phase 6 – Testing, quality gates, and developer experience
**Goal:** Ensure the rebuilt backend ships with async-first tests, static analysis, and contributor tooling aligned with the new architecture.

- Convert the test suite to rely on `httpx.AsyncClient` fixtures, pytest markers for async/background jobs, and module-specific test packages.
- Wire linting (Ruff), typing (MyPy), and formatting checks into `pyproject.toml`, adding a `pre-commit` configuration if contributors rely on it.
- Add coverage for dependencies, permission decorators, message hub, queue workers, and failure cases (timeouts, invalid payloads).
- Provide developer docs covering environment setup, running workers, applying migrations, executing tests, and troubleshooting common issues.
- Ensure CI (if configured) runs `pytest`, `ruff`, `mypy`, and any queue worker smoke tests.

**Exit criteria**
- `pytest`, `ruff`, and `mypy` all pass locally, and CI mirrors those checks.
- Contributor-facing docs give a clear checklist for running and extending the new backend architecture.
