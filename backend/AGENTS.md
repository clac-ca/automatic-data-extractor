## backend/AGENTS.md

### Backend Structure

```
backend/
├─ app/
│  ├─ main.py                  # FastAPI app, CORS, health, static mount
│  ├─ api/
│  │  └─ v1/
│  │     └─ __init__.py        # composes feature routers
│  ├─ features/                # vertical slices (router + domain logic)
│  │  ├─ auth/
│  │  │  ├─ __init__.py
│  │  │  ├─ router.py          # /api/v1/auth
│  │  │  ├─ schemas.py
│  │  │  └─ service.py
│  │  ├─ users/
│  │  │  ├─ __init__.py
│  │  │  ├─ router.py
│  │  │  ├─ schemas.py
│  │  │  ├─ service.py
│  │  │  └─ repository.py
│  │  ├─ documents/
│  │  │  ├─ __init__.py
│  │  │  ├─ router.py
│  │  │  ├─ schemas.py
│  │  │  ├─ service.py
│  │  │  └─ repository.py
│  │  ├─ jobs/
│  │  │  ├─ __init__.py
│  │  │  ├─ router.py
│  │  │  ├─ schemas.py
│  │  │  ├─ service.py
│  │  │  └─ repository.py
│  │  ├─ workspaces/
│  │  │  ├─ __init__.py
│  │  │  ├─ router.py
│  │  │  ├─ schemas.py
│  │  │  └─ service.py
│  │  └─ health/
│  │     ├─ __init__.py
│  │     └─ router.py          # /api/health, /api/ready, /api/v1/healthz
│  ├─ shared/                  # cross-cutting utilities
│  │  ├─ core/
│  │  │  ├─ config.py          # settings/env
│  │  │  ├─ errors.py          # error envelope handlers
│  │  │  ├─ logging.py
│  │  │  └─ security.py
│  │  ├─ db/                   # database wiring (optional until used)
│  │  │  ├─ __init__.py
│  │  │  ├─ session.py         # engine/session factory
│  │  │  └─ models/            # ORM models
│  │  └─ repositories/
│  │     ├─ __init__.py
│  │     └─ base.py            # generic repository abstraction
│  └─ static/                  # built frontend copied here by build step
├─ tests/
│  ├─ api/                     # route/contract tests
│  └─ services/                # business logic tests
├─ pyproject.toml
└─ .env.example
```

Dependencies are defined in `pyproject.toml`; install them via `pip install -e .` from `backend/` or run `npm run setup` at the repo root.

### Commands

```bash
# from repo root
npm run dev       # runs FastAPI on :8000 with reload (and frontend if present)
npm run test      # runs backend pytest (and frontend tests if present)
npm run start     # run FastAPI in local prod
npm run openapi-typescript   # dump schema + regenerate frontend TS types
```

### API conventions

* **Base path:** all application endpoints under `/api/v1/*`.
* **Health:** expose `/api/health` (liveness) and `/api/ready` (readiness). If you prefer versioned health: `/api/v1/healthz`.
* **Error shape:** return a consistent envelope:

  ```json
  { "ok": false, "error": { "code": "SOME_CODE", "message": "…" }, "trace_id": "…" }
  ```

### Module boundaries

* **Feature packages** (`app/features/<feature>`) own router/service/schemas/repository for that slice.
* **Routers** = HTTP I/O only (validation, HTTP codes).
* **Services** = business logic; no HTTP dependencies.
* **Repositories** = DB access; no business logic; import shared repository base.
* **Shared** (`app/shared/*`) = cross-cutting config, logging, security, db helpers.

### Env & config

```
backend/.env          # local only; do not commit
backend/.env.example  # document keys
```

### Tests

* Put HTTP route tests in `tests/api/…`, logic tests in `tests/services/…`.
* Keep tests small and fast; prefer unit tests for services.

### Do / Don’t

* **Do** keep routers thin and typed via Pydantic.
* **Do** keep side‑effects in services/repos, not in routers.
* **Don’t** access DB directly from routers.
* **Don’t** commit secrets or modify `.env` in PRs.
