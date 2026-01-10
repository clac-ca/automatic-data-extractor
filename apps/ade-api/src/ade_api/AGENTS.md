# ade_api package layout

This backend now follows a conventional FastAPI layout with clear layering and no legacy `shared` package.

```
ade_api/
├─ main.py                  # FastAPI app factory + ASGI entrypoint
├─ settings.py              # Pydantic settings
├─ api/                     # HTTP layer (dependency wiring + versioned routers)
├─ app/                     # Application wiring (lifecycles)
├─ common/                  # Cross-cutting helpers (logging, exceptions, middleware, schema, pagination, etc.)
├─ core/                    # Identity/RBAC contracts and security primitives
├─ db/                      # Database engines/sessions/types (SQLAlchemy)
├─ models/                  # SQLAlchemy ORM models
├─ infra/                   # Infrastructure adapters (storage, venv, versioning)
├─ features/                # Domain modules (users, workspaces, configs, runs, documents, auth, roles, etc.)
├─ templates/               # Config package templates
├─ web/                     # Web-related helpers; API can serve built SPA when configured
└─ scripts/                 # Utility scripts
```

Layering guidelines:
- `api/` contains HTTP wiring and should not contain business logic.
- `app/` wires FastAPI lifecycle and should not contain business logic.
- `common/` holds generic utilities; avoid importing `features/*` from here.
- `core/` defines identity/auth/RBAC contracts and security helpers consumed by `features/*`.
- `db/` and `models/` hold persistence primitives and should not import `features/*`.
- `infra/` houses storage/venv/version adapters; avoid importing `features/*`.
- `features/*` implement vertical functionality and may import from `api/deps`, `common/`, `core/`, `db/`, `models/`, and `settings`.

## Auth

- Auth uses fastapi-users cookie sessions (`POST /auth/cookie/login` + `/auth/cookie/logout`) and optional JWT login (`POST /auth/jwt/login`).
- There is no refresh-token or `/auth/session/refresh` flow in the current auth stack.
