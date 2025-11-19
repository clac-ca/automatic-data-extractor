# ade CLI behavior notes

`ade` (from `apps/ade-cli`) is the canonical orchestration entrypoint. Key expectations:

- **Working directories** — Backend commands run from repo root or `apps/ade-api/` as appropriate; frontend commands run from `apps/ade-web/`. Docker helpers run at repo root.
- **Virtualenv resolution** — Prefers `.venv/bin/python`/`.venv/Scripts/python.exe` + matching `uvicorn`. Create the venv once (e.g., `python3 -m venv .venv && pip install --no-cache-dir -e apps/ade-cli -e packages/ade-schemas -e apps/ade-engine -e apps/ade-api` or `source setup.sh`); commands fall back to `sys.executable` when needed.
- **Ports** — Dev mode respects `DEV_BACKEND_PORT`/`DEV_FRONTEND_PORT` (defaults: backend 8000 or 8001 when frontend also running; frontend 8000).
- **Build outputs** — Frontend build artifacts are copied to `apps/ade-api/src/ade_api/web/static`. OpenAPI JSON is emitted to `apps/ade-api/src/ade_api/openapi.json`; TypeScript types to `apps/ade-web/src/generated-types/openapi.d.ts`.
- **Run modes** — `ade dev` uses the Vite dev server (no build needed). `ade start` serves the built SPA; run `ade build` first or FastAPI will return `{"detail":"SPA build not found"}`.
- **Safety** — `clean` prompts unless `--yes`; `reset` reuses backend reset script (with `--yes`) before re-running setup. Docker helpers are thin wrappers around `docker compose`.
- **Parity notes** — `ade migrate` runs Alembic upgrades; `ade workpackage` still delegates to the legacy Node helper until migrated. Cross-platform verification and deeper smoke runs remain TODO (see workpackage).
