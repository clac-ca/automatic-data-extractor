## backend/AGENTS.md

### Backend Structure

```
backend/
├─ app/
│  ├─ main.py                  # FastAPI app, CORS, health, static mount
│  ├─ api/
│  │  └─ v1/
│  │     ├─ __init__.py
│  │     ├─ health.py          # /api/health, /api/ready (or /api/v1/healthz)
│  │     ├─ auth.py
│  │     ├─ users.py
│  │     ├─ documents.py
│  │     ├─ jobs.py
│  │     └─ workspaces.py
│  ├─ services/                # business logic (pure python)
│  │  ├─ auth_service.py
│  │  ├─ users_service.py
│  │  ├─ documents_service.py
│  │  ├─ jobs_service.py
│  │  └─ workspaces_service.py
│  ├─ repositories/            # DB/data access (add when DB exists)
│  │  ├─ base.py
│  │  ├─ users_repo.py
│  │  ├─ documents_repo.py
│  │  └─ jobs_repo.py
│  ├─ schemas/                 # Pydantic request/response DTOs
│  │  ├─ auth.py
│  │  ├─ users.py
│  │  ├─ documents.py
│  │  ├─ jobs.py
│  │  └─ workspaces.py
│  ├─ core/                    # cross‑cutting concerns
│  │  ├─ config.py             # settings/env
│  │  ├─ security.py           # auth/JWT/permissions
│  │  ├─ errors.py             # error envelope handlers
│  │  └─ logging.py
│  ├─ db/                      # database wiring (optional until used)
│  │  ├─ session.py            # engine/session factory
│  │  └─ models/               # ORM models
│  └─ static/                  # built frontend copied here by build step
├─ tests/
│  ├─ api/                     # route/contract tests
│  └─ services/                # business logic tests
├─ requirements.txt
└─ .env.example
```

### Commands

```bash
# from repo root
npm run dev       # runs FastAPI on :8000 with reload (and frontend if present)
npm run test      # runs backend pytest (and frontend tests if present)
npm run start     # run FastAPI in local prod
```

### API conventions

* **Base path:** all application endpoints under `/api/v1/*`.
* **Health:** expose `/api/health` (liveness) and `/api/ready` (readiness). If you prefer versioned health: `/api/v1/healthz`.
* **Error shape:** return a consistent envelope:

  ```json
  { "ok": false, "error": { "code": "SOME_CODE", "message": "…" }, "trace_id": "…" }
  ```

### Module boundaries

* **Routers** (`app/api/v1/*.py`) = HTTP I/O only (validation, HTTP codes).
* **Services** = business logic; no HTTP dependencies.
* **Repositories** = DB access; no business logic.
* **Schemas** = Pydantic models for request/response.
* **core/** = config/security/errors/logging.

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