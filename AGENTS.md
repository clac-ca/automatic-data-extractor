# AGENTS.md
ADE is a lightweight, configurable engine for normalizing Excel/CSV files at scale.

## Monorepo overview

* **Frontend** — React (Vite) SPA to author config packages and trigger builds/runs.
* **Backend** — FastAPI service that stores metadata, builds isolated Python environments, and orchestrates runs.
* **Engine** — Installable `ade_engine` package that executes detectors/hooks and writes outputs.
* **Config packages** — Installable `ade_config` projects you author; versioned and built per workspace.

## ⚡ Available Tools

> The Python `ade` CLI (from `apps/ade-cli`) is the canonical entrypoint.

```bash
ade dev                   # FastAPI + React dev servers (--backend/--frontend to scope)
ade test                  # Run all tests
ade bundle                # Bundle files/dirs into LLM-ready Markdown; copies to clipboard
ade build                 # Build SPA → apps/ade-api/src/ade_api/web/static
ade start                 # Serve API + SPA
ade openapi-types         # Generate TS types from OpenAPI
ade routes                # List FastAPI routes
ade clean --yes           # Delete build/.venv/node_modules
ade reset --yes           # Clean + storage reset + setup
ade ci                    # Full pipeline (lint, test, build)
```

- `ade bundle` is the copy/paste helper for agents: like the old copy-code script, but richer. Point it at files/dirs, filter with `--ext/--include/--exclude`, and use `--out`/`--no-clip`/`--head`/`--tail` to control the bundle.

### Frontend API types

- Generated TypeScript types live in `apps/ade-web/src/generated-types/openapi.d.ts`. If that file is missing (or clearly stale), run `ade openapi-types` to regenerate it before touching frontend API code.
- Import API shapes from the curated schema module (`import type { SessionEnvelope } from "@schema";`). Avoid importing from `@generated-types/*` directly—add re-exports in `src/schema/` when new stable types are needed.
- Treat manual types as view-model helpers only; when adding params or schemas, update the OpenAPI spec and rerun the generator instead of editing the generated file.

```text
automatic-data-extractor/
├─ apps/                                   # Deployable applications + tooling
│  ├─ ade-api/                             # FastAPI service (serves /api + static SPA)
│  │  ├─ pyproject.toml
│  │  ├─ src/ade_api/                      # Settings, routers, features, shared modules, templates, web assets
│  │  ├─ migrations/                       # Alembic migrations
│  │  └─ tests/                            # Unit + integration tests
│  ├─ ade-cli/                             # Python orchestration CLI (console script: ade)
│  │  ├─ pyproject.toml
│  │  └─ src/ade_tools/
│  ├─ ade-engine/                          # installable package: ade_engine
│  │  ├─ pyproject.toml
│  │  ├─ src/ade_engine/                   # Engine runtime (I/O, pipeline, hooks)
│  │  └─ tests/                            # Engine unit tests
│  └─ ade-web/                             # React SPA (Vite)
│     ├─ src/                              # app/, screens/, shared/, ui/, schema/, generated-types/, test/
│     ├─ public/                           # Static public assets
│     ├─ package.json
│     └─ vite.config.ts
│
├─ packages/                               # Reusable Python libraries
│  └─ ade-engine/                          # installable package: ade_engine
│     ├─ pyproject.toml
│     └─ src/ade_engine/
│
├─ specs/                                   # JSON Schemas & formal definitions
│  ├─ config-manifest.v1.json
│  └─ template-manifest.v1.json
│
├─ examples/                                # Sample inputs/outputs
├─ docs/                                    # Developer guides, HOWTOs, runbooks
├─ scripts/                                 # Repo-level helper scripts
│
│
├─ .env.example                             # Example env vars
├─ .editorconfig
├─ .pre-commit-config.yaml
├─ .gitignore
└─ .github/workflows/                       # CI (lint, test, build, publish)
```

### Frontend screen-first (routerless) layout

The React SPA at `apps/ade-web/` uses a history-based navigation helper instead of React Router. Screen code lives under `src/screens/<ScreenName>/`, and everything a screen needs (components, hooks, sections) is co-located beneath that folder. The `src/ui/` directory holds presentational primitives such as `Tabs`, `Button`, and `Input`. Use the path aliases configured in `tsconfig.json`/`vite.config.ts` (`@app/*`, `@screens/*`, `@ui/*`, `@shared/*`, `@schema/*`, `@generated-types/*`, `@test/*`) for imports instead of deep relative paths.

Navigation helpers live in `@app/nav` (`history.tsx`, `Link.tsx`, `urlState.ts`). Consume `useNavigate`/`useLocation` from there, and render links with `Link`/`NavLink` from the same module.

Everything ADE produces (config_packages, venvs, runs, logs, cache, etc..) is persisted under `./data/workspaces/<workspace_id>/...` by default. Set `ADE_WORKSPACES_DIR` to move the workspace root, or override `ADE_DOCUMENTS_DIR`, `ADE_CONFIGS_DIR`, `ADE_VENVS_DIR`, or `ADE_RUNS_DIR` to relocate a specific storage type—ADE always nests the workspace ID under the override.

```text
./data/
├─ workspaces/
│  └─ <workspace_id>/
│     ├─ config_packages/           # Source-of-truth configs (GUI-managed)
│     │  └─ <config_id>/
│     │     ├─ pyproject.toml       # Config distribution metadata
│     │     ├─ requirements.txt     # Optional dependency overlay
│     │     └─ src/ade_config/
│     │        ├─ column_detectors/
│     │        ├─ row_detectors/
│     │        ├─ hooks/
│     │        ├─ manifest.json
│     │        └─ config.env
│     ├─ .venv/                     # One Python venv per configuration
│     │  └─ <config_id>/
│     │     ├─ bin/python
│     │     ├─ ade-runtime/
│     │     │  ├─ packages.txt
│     │     │  └─ build.json
│     │     └─ <site-packages>/
│     │        ├─ ade_engine/
│     │        └─ ade_config/
│     ├─ runs/
│     │  └─ <run_id>/
│     │     ├─ input/               # Uploaded files
│     │     ├─ output/              # Generated files
│     │     └─ logs/
│     │        ├─ artifact.json     # Human-readable narrative
│     │        └─ events.ndjson     # Append-only event log
│     └─ documents/
│        └─ <document_id>.<ext>     # Optional shared store
│
├─ db/app.sqlite                     # SQLite (dev) or DSN (prod)
├─ cache/pip/                        # pip cache (safe to delete)
└─ logs/                             # Central service logs
```

---

### Debug a Failing Build

1. Run `ade ci`.
2. Read JSON output (stdout).
3. Fix first error.
4. Re-run until `"ok": true`.

---

## 🔧 TODO IN FUTURE WHEN POSSIBLE

* Add linting/formatting: `ruff`/`black` (Python), `eslint`/`prettier` (JS).

---

## 🤖 Agent Rules

1. Always run `ade test` before committing and `ade ci` before pushing or opening a PR.

---

**End of AGENTS.md**
