# Admin Guide

Administrators install, configure, and operate the Automatic Data Extractor. This guide captures the durable pieces of that workflow while deeper runbooks are drafted.

## Deployment at a glance
- ADE is a FastAPI application created in [`backend/app/main.py`](../../backend/app/main.py) with its settings defined in [`backend/app/shared/core/config.py`](../../backend/app/shared/core/config.py).
- Development mirrors Uvicorn's factory semantics: run `uvicorn backend.app.main:create_app --factory` (or `npm run start`) to serve the compiled SPA and API in a single process. Add `--reload` while iterating and run `npm run dev` in `frontend/` for Vite hot module reload.
- Production deployments build the frontend once (`npm run build`) and serve the static bundle behind the same reverse proxy that forwards API traffic to a managed ASGI process (Uvicorn, Uvicorn+Gunicorn, systemd, or a container orchestrator).
- Persistent state lives under the `data/` directory by default. SQLite databases and uploaded documents sit beneath `data/db/` and `data/documents/`; both paths can be overridden through environment variables.
- The API entry point calls the shared database bootstrap helper before opening sessions. It creates the SQLite directory, runs Alembic migrations, and surfaces progress in the logs before mirroring the manual fallback documented in the [admin getting started guide](getting_started.md#manual-migrations-and-recovery).

## Configuration snapshot
- Settings are loaded once at startup through `get_settings()` and cached on `app.state.settings`. Routes and background workers read from this state rather than reloading environment variables on every request.
- Environment variables use the `ADE_` prefix (for example `ADE_DATABASE_DSN`, `ADE_STORAGE_UPLOAD_MAX_BYTES`). A local `.env` file is respected during development.
- Host and port configuration splits into `ADE_SERVER_HOST` / `ADE_SERVER_PORT` for the uvicorn listener and `ADE_SERVER_PUBLIC_URL` for the externally reachable origin. When ADE sits behind HTTPS on a domain such as `https://ade.example.com`, set the public URL and provide a JSON array in `ADE_SERVER_CORS_ORIGINS` so browsers can connect (for example `["https://ade.example.com"]`).
- Documentation endpoints (`/docs`, `/redoc`, `/openapi.json`) default on for the `local` and `staging` environments and can be
  toggled explicitly through the `ADE_API_DOCS_ENABLED` flag to keep production surfaces minimal.
- Account lockout policy is governed by `ADE_FAILED_LOGIN_LOCK_THRESHOLD` (attempts) and
  `ADE_FAILED_LOGIN_LOCK_DURATION` (lock length, supports suffixed durations like `5m`). Defaults lock a user for
  five minutes after five consecutive failures.

## Operational building blocks
- Database connections are created via the async SQLAlchemy engine in [`backend/app/shared/db/engine.py`](../../backend/app/shared/db/engine.py) and scoped sessions from [`backend/app/shared/db/session.py`](../../backend/app/shared/db/session.py).
- Background work is handled by the in-process task queue defined in [`backend/app/shared/workers/task_queue.py`](../../backend/app/shared/workers/task_queue.py).
- Structured logging and correlation IDs are configured through [`backend/app/shared/core/logging.py`](../../backend/app/shared/core/logging.py) and middleware in [`backend/app/shared/core/middleware.py`](../../backend/app/shared/core/middleware.py).

Future sections will expand on security hardening, backup procedures, and frontend onboarding once those pieces land. The components listed above are already in place and unlikely to change dramatically.

- [ADE Admin Getting Started Guide](getting_started.md) – local/python vs. Docker workflows, `.env` usage, and interim provisioning steps.
