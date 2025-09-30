# Admin Guide

Administrators install, configure, and operate the Automatic Data Extractor. This guide captures the durable pieces of that workflow while deeper runbooks are drafted.

## Deployment at a glance
- ADE is a FastAPI application created in [`app/main.py`](../../app/main.py) with its settings defined in [`app/core/settings.py`](../../app/core/settings.py).
- Development favours two hot-reload loops: run `ade start` to launch FastAPI and the Vite dev server together, or start `uvicorn` and `npm run dev -- --host` in separate terminals.
- Production deployments build the frontend once (`npm run build`) and serve the static bundle behind the same reverse proxy that forwards API traffic to a managed ASGI process (Uvicorn, Uvicorn+Gunicorn, systemd, or a container orchestrator).
- Persistent state lives under the `var/` directory by default. SQLite databases and uploaded documents sit beneath `var/db/` and `var/documents/`; both paths can be overridden through environment variables.

## Configuration snapshot
- Settings are loaded once at startup through `get_settings()` and cached on `app.state.settings`. Routes and background workers read from this state rather than reloading environment variables on every request.
- Environment variables use the `ADE_` prefix (for example `ADE_DATABASE_DSN`, `ADE_STORAGE_UPLOAD_MAX_BYTES`). A local `.env` file is respected during development.
- Host and port configuration splits into `ADE_SERVER_HOST` / `ADE_SERVER_PORT` for the uvicorn listener and `ADE_SERVER_PUBLIC_URL` for the externally reachable origin. When ADE sits behind HTTPS on a domain such as `https://ade.example.com`, set the public URL and frontend `VITE_API_BASE_URL` to that origin and list it in `ADE_SERVER_CORS_ORIGINS` (comma or whitespace separated) so browsers can connect.
- Documentation endpoints (`/docs`, `/redoc`, `/openapi.json`) default on for the `local` and `staging` environments and can be
  toggled explicitly through the `ADE_API_DOCS_ENABLED` flag to keep production surfaces minimal.

## Operational building blocks
- Database connections are created via the async SQLAlchemy engine in [`app/core/db/engine.py`](../../app/core/db/engine.py) and scoped sessions from [`app/core/db/session.py`](../../app/core/db/session.py).
- Background work is handled by the in-process task queue defined in [`app/core/task_queue.py`](../../app/core/task_queue.py) and message hub in [`app/core/message_hub.py`](../../app/core/message_hub.py).
- Structured logging and correlation IDs are configured through [`app/core/logging.py`](../../app/core/logging.py) and middleware in [`app/core/middleware.py`](../../app/core/middleware.py).

Future sections will expand on security hardening, backup procedures, and frontend onboarding once those pieces land. The components listed above are already in place and unlikely to change dramatically.

- [ADE Admin Getting Started Guide](getting_started.md) – local/python vs. Docker workflows, `.env` usage, CLI management, and interim provisioning steps.
