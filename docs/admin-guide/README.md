# Admin Guide

Administrators install, configure, and operate the Automatic Data Extractor. This guide captures the durable pieces of that workflow while deeper runbooks are drafted.

## Deployment at a glance
- ADE is a FastAPI application created in [`backend/api/main.py`](../../backend/api/main.py) with its settings defined in [`backend/api/settings.py`](../../backend/api/settings.py).
- Development favours two hot-reload loops: run `ade start` to launch FastAPI and the Vite dev server together, or start `uvicorn` and `npm run dev -- --host` in separate terminals.
- Production deployments build the frontend once (`npm run build`) and serve the static bundle behind the same reverse proxy that forwards API traffic to a managed ASGI process (Uvicorn, Uvicorn+Gunicorn, systemd, or a container orchestrator).
- Persistent state lives under the `backend/data/` directory by default. SQLite databases and uploaded documents sit beneath `backend/data/db/` and `backend/data/documents/`; both paths can be overridden through environment variables.

## Configuration snapshot
- Settings are loaded once at startup through `get_settings()` and cached on `app.state.settings`. Routes and background workers read from this state rather than reloading environment variables on every request.
- Environment variables use the `ADE_` prefix (for example `ADE_DATABASE_URL`, `ADE_MAX_UPLOAD_BYTES`). A local `.env` file is respected during development.
- Documentation endpoints (`/docs`, `/redoc`, `/openapi.json`) default on for the `local` and `staging` environments and can be
  toggled explicitly through the `ADE_ENABLE_DOCS` flag to keep production surfaces minimal.

## Operational building blocks
- Database connections are created via the async SQLAlchemy engine in [`backend/api/db/engine.py`](../../backend/api/db/engine.py) and scoped sessions from [`backend/api/db/session.py`](../../backend/api/db/session.py).
- Background work is handled by the in-process task queue defined in [`backend/api/core/task_queue.py`](../../backend/api/core/task_queue.py) and message hub in [`backend/api/core/message_hub.py`](../../backend/api/core/message_hub.py).
- Structured logging and correlation IDs are configured through [`backend/api/core/logging.py`](../../backend/api/core/logging.py) and middleware in [`backend/api/extensions/middleware.py`](../../backend/api/extensions/middleware.py).

Future sections will expand on security hardening, backup procedures, and frontend onboarding once those pieces land. The components listed above are already in place and unlikely to change dramatically.

- [ADE Admin Getting Started Guide](getting_started.md) – local/python vs. Docker workflows, `.env` usage, CLI management, and interim provisioning steps.
