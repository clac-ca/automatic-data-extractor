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
├─ web/                     # Web-related helpers (API no longer serves the SPA)
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

- Auth is ADE-owned and policy-driven (no FastAPI Users runtime dependency in request auth paths).
- Canonical browser endpoints are `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `POST /api/v1/auth/password/forgot`, `POST /api/v1/auth/password/reset`, and `POST /api/v1/auth/mfa/challenge/verify`.
- Canonical admin SSO policy endpoint is `GET/PUT /api/v1/admin/sso/settings`.
- API keys are accepted only via `X-API-Key` header. `Authorization: Bearer` is not used for API key auth.
- There is no refresh-token or `/auth/session/refresh` flow in the current auth stack.
