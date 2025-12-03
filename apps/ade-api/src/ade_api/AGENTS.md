# ade_api package layout

This backend now follows a conventional FastAPI layout with clear layering and no legacy `shared` package.

```
ade_api/
├─ main.py                  # FastAPI app factory + ASGI entrypoint
├─ settings.py              # Pydantic settings
├─ routers.py               # API router composition (v1)
├─ app/                     # Application wiring (lifecycles, dependency factories)
├─ common/                  # Cross-cutting helpers (logging, exceptions, middleware, schema, pagination, etc.)
├─ core/                    # Identity/RBAC contracts and security primitives
├─ infra/                   # Infrastructure (db engines/sessions/types, storage adapters)
├─ features/                # Domain modules (users, workspaces, configs, runs, documents, auth, roles, etc.)
├─ templates/               # Config package templates
├─ web/                     # Bundled SPA assets
└─ scripts/                 # Utility scripts
```

Layering guidelines:
- `app/` wires FastAPI (lifespan, dependency factories) and should not contain business logic.
- `common/` holds generic utilities; avoid importing `features/*` from here.
- `core/` defines identity/auth/RBAC contracts and security helpers consumed by `features/*`.
- `infra/` houses DB/storage infrastructure; no imports from `features/*`.
- `features/*` implement vertical functionality and import from `common/`, `core/`, `infra/`, `settings`, and `app/dependencies` only.

## Auth

- `POST /auth/session/refresh` prefers a JSON ``refresh_token`` payload for API/CLI callers and falls back to the refresh cookie; Authorization headers are ignored for refresh rotation.
