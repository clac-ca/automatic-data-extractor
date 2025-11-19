# ADE CLI mapping

The Python-first `ade` CLI (provided by `apps/ade-cli`) replaces the legacy root npm wrappers. Use the table below to translate older commands to the new entrypoints.

| Old workflow | New `ade` command | Notes |
| --- | --- | --- |
| `npm run dev` | `ade dev` | Starts backend + frontend together (`--backend/--frontend` to scope). |
| `npm run dev:backend` | `ade dev --backend --no-frontend` | Backend autoreload on port `DEV_BACKEND_PORT` (defaults to 8000 or 8001 when frontend also runs). |
| `npm run dev:frontend` | `ade dev --frontend --no-backend` | Frontend dev server (`npm run dev`) on `DEV_FRONTEND_PORT` (default 8000). |
| `npm run start` | `ade start` | Backend server without autoreload (uvicorn). |
| `npm run build` | `ade build` | Builds SPA and copies dist → `apps/ade-api/src/ade_api/web/static`. |
| _(n/a)_ | `ade migrate` | Run Alembic migrations for the backend (defaults to head). |
| `npm run test` | `ade test` | Pytest in `apps/ade-api/` + frontend tests if defined. |
| `npm run lint` | `ade lint` | Runs backend ruff + frontend lint (scope with `--scope`). |
| `ade openapi-types` | `ade openapi-types` | Generates OpenAPI JSON + TypeScript definitions. |
| `npm run routes` / `routes:backend` | `ade routes` | Lists FastAPI routes. |
| `npm run clean[:force]` | `ade clean` | Removes `.venv`, frontend node_modules/dist, backend static assets. |
| `npm run reset[:force]` | `ade reset` | Purges ADE storage, cleans artifacts, re-runs setup. |
| `ade ci` | `ade ci` | End‑to‑end pipeline: setup → openapi-types → lint → test → build. |
| `npm run workpackage` | `ade workpackage` | Delegates to the legacy Node helper until migrated. |

`ade --help` shows all available commands and options.
