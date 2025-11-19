# Legacy root workflows (inventory)

This captures the npm-based orchestration that previously lived at the repo root so future work can validate `ade` parity. Commands referenced `scripts/npm-*.mjs` and were exposed through `package.json` + `bin/ade`.

## Commands and behavior

- `setup` — create `.venv` (if missing), pip upgrade, editable installs for `packages/ade-schemas`, `apps/ade-engine`, `apps/ade-api[dev]`; run `npm ci` in `apps/ade-web/`. Env: uses OS python launcher; cwd: repo root.
- `dev` — run backend (uvicorn) and frontend (npm dev) via `npx concurrently`. Env: `DEV_BACKEND_PORT`/`DEV_FRONTEND_PORT` (defaults 8000/8001 when both). Cwd for backend: repo root; frontend: `apps/ade-web/`.
- `dev:backend` / `dev:frontend` — same as above, scoped to one side. Backend checks `.venv/bin/uvicorn` fallback to system uvicorn; frontend `npm --prefix apps/web run dev -- --host 0.0.0.0 --port <DEV_FRONTEND_PORT>`.
- `start` — `uvicorn apps.api.app.main:create_app --factory --host 0.0.0.0 --port 8000` (prefers `.venv` uvicorn). Cwd: repo root.
- `test` — pytest (apps/api) with `.venv` python; if `apps/web/package.json` contains `test` script, run `npm run test` in `apps/web/`.
- `lint` — ruff check `app` in backend; optional frontend lint if `package.json` contains `lint`. Scopes: all/backend/frontend.
- `build` — run `npm run build` in `apps/web/`; if backend present, copy `apps/web/dist` → `apps/api/app/web/static`.
- `openapi-typescript` — `python -m apps.api.app.scripts.generate_openapi --output apps/api/app/openapi.json`, then `npx openapi-typescript` → `apps/web/src/generated-types/openapi.d.ts`. Skips frontend if missing.
- `routes` / `routes:backend` — `python -m apps.api.app.scripts.api_routes` with optional args; tries `ADE_PYTHON`, then platform python.
- `docker:build` — `docker compose -f infra/compose.yaml build`.
- `docker:up` — `docker compose -f infra/compose.yaml up --build`.
- `docker:down` — `docker compose -f infra/compose.yaml down`.
- `docker:logs` — `docker compose -f infra/compose.yaml logs -f`.
- `docker:test` — `docker compose -f infra/compose.yaml run --rm ade python -c "import importlib; importlib.import_module('apps.api.app.main')"` (smoke import).
- `clean` / `clean:force` — rm `.venv`, `apps/api/app/web/static`, `apps/web/node_modules`, `apps/web/dist`, `node_modules`. Interactive unless `--yes` or `clean:force`.
- `reset` / `reset:force` — run backend reset storage script (`apps.api.app.scripts.reset_storage`), then `npm run clean:force` and `npm run setup`. Interactive unless `reset:force`/`--yes`.
- `ci` — sequential: setup → openapi-typescript → lint → test → build; collects summary JSON and marks skipped routes for routerless frontend.
- `workpackage` — node-based manager under `.workpackage/` with locking + JSON pkg index.

## Observed env/paths/tools

- Backend working directory assumed repo root or `apps/api` for tests/lint.
- Frontend working directory assumed `apps/web`.
- Env variables surfaced: `DEV_BACKEND_PORT`, `DEV_FRONTEND_PORT`, `ADE_PYTHON` (route listing fallback), `ADE_*` storage/DSN in backend scripts, interactive prompts in clean/reset unless `--yes`/force lifecycle.
- External tools: uvicorn, pytest, ruff, npm, npx (concurrently, openapi-typescript), docker compose, Alembic via backend scripts, node for workpackage helper.
