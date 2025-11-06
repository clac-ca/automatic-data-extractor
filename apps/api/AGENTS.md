# apps/api/AGENTS.md

## API Service Layout

```
apps/api/
├─ app/
│  ├─ main.py                    # FastAPI factory; mounts /api and static SPA
│  ├─ api/                       # Route composition (FastAPI routers)
│  ├─ core/                      # settings, logging, middleware, security
│  ├─ services/                  # orchestration + business workflows (TBD)
│  ├─ repositories/              # database persistence layer (SQLAlchemy)
│  ├─ schemas/                   # Pydantic request/response/DB models
│  ├─ workers/                   # async worker/queue orchestration (future)
│  ├─ shared/                    # cross-cutting helpers (core, db, adapters)
│  ├─ scripts/                   # CLI helpers (e.g., route summaries)
│  └─ web/                       # static assets served with the API
│     └─ static/                 # SPA build output (npm run build)
├─ migrations/                   # Alembic migration scripts
└─ tests/                        # pytest suites (api + services + utilities)
```

Install dependencies from the repo root (`pip install -e apps/api[dev]`) or via `npm run setup`.

## Commands

```bash
# from repo root
npm run dev         # FastAPI (with reload) + web dev server
npm run dev:backend # FastAPI only
npm run test        # pytest + vitest
npm run build       # compile SPA into apps/api/app/web/static
npm run openapi-typescript  # refresh OpenAPI JSON + TS types
```

## API Conventions

* **Base path:** `/api/v1/*`.
* **Health:** `/api/health` (liveness) and `/api/ready` (readiness). Keep `/api/v1/healthz` for versioned checks if needed.
* **Error envelope:** return a consistent payload:

  ```json
  { "ok": false, "error": { "code": "SOME_CODE", "message": "…" }, "trace_id": "…" }
  ```

## Module Boundaries

* `app/api/*` — router composition (no business logic).
* `app/services/*` — orchestration/business workflows (pure Python, no HTTP).
* `app/repositories/*` — persistence adapters (SQLAlchemy sessions only).
* `app/shared/*` — shared configuration, logging, security, storage, etc.
* `app/schemas/*` — Pydantic models shared across layers.

## Environment & Config

```
.env             # local overrides (ignored)
.env.example     # documented defaults
Alembic          # configured via alembic.ini (script_location=apps/api/migrations)
```

## Testing

* HTTP contract tests live in `apps/api/tests/api/`.
* Service/unit tests live in `apps/api/tests/services/` (and friends).
* Use `pytest` fixtures from `conftest.py` for database setup and settings reloads.

## Do / Don’t

* **Do** keep routers thin; they should delegate to services immediately.
* **Do** isolate DB access in repositories or adapters.
* **Do** run `npm run test` before commits and `npm run ci` before merging.
* **Don’t** import FastAPI objects inside domain code.
* **Don’t** commit `.env` or generated artifacts under `apps/api/app/web/static`.
