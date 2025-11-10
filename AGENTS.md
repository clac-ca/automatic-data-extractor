# AGENTS.md
ADE is a lightweight, configurable engine for normalizing Excel/CSV files at scale.

## Monorepo overview

* **Frontend** — React (Vite) SPA to author config packages and trigger builds/runs.
* **Backend** — FastAPI service that stores metadata, builds isolated Python environments, and orchestrates jobs.
* **Engine** — Installable `ade_engine` package that executes detectors/hooks and writes outputs.
* **Config packages** — Installable `ade_config` projects you author; versioned and built per workspace.

## ⚡ Available Tools

> You can use either ade <script> or npm run <script> — both are synced.

```bash
npm run setup              # Install deps (.venv + web node_modules)
npm run dev                # FastAPI + React dev servers
npm run test               # Run all tests
npm run build              # Build SPA → apps/api/app/web/static
npm run start              # Serve API + SPA
npm run openapi-typescript # Generate TS types from OpenAPI
npm run routes:frontend    # List React Router routes
npm run routes:backend     # List FastAPI routes
npm run workpackage        # Manage work packages (CLI JSON interface)
npm run clean:force        # Force delete build/.venv
npm run reset:force        # Clean + setup fresh
npm run ci                 # Full CI pipeline (lint, test, build)

```

```text
automatic-data-extractor/
├─ apps/                                   # Deployable applications
│  ├─ api/                                 # FastAPI service (serves /api + static SPA)
│  │  ├─ app/
│  │  │  ├─ api/                           # Exception handlers + API helpers
│  │  │  ├─ features/                      # Domain-first modules (auth, configs, jobs, etc.)
│  │  │  │  ├─ auth/                       # Example feature module
│  │  │  │  │  ├─ router.py                # HTTP routes for this feature
│  │  │  │  │  ├─ service.py               # Business logic
│  │  │  │  │  ├─ repository.py            # DB persistence
│  │  │  │  │  └─ schemas.py               # Pydantic I/O models
│  │  │  ├─ scripts/                       # App-scoped CLIs (seed, migrate, etc.)
│  │  │  ├─ shared/                        # Cross-cutting infra (settings, db, logging)
│  │  │  │  ├─ dependency.py               # Global FastAPI dependencies (auth, RBAC, services)
│  │  │  ├─ web/static/                    # ← Built SPA copied here at image build time (DO NOT COMMIT)
│  │  │  ├─ templates/                     # Optional: Jinja2 emails/server-rendered templates
│  │  │  │  └─ config_packages/            # Bundled ADE config package templates
│  │  │  │     ├─ default/
│  │  │  │     │  ├─ template.manifest.json
│  │  │  │     │  └─ src/ade_config/                # Detectors/hooks + runtime manifest/env
│  │  │  │     │     ├─ manifest.json
│  │  │  │     │     ├─ config.env
│  │  │  │     │     ├─ column_detectors/
│  │  │  │     │     ├─ row_detectors/
│  │  │  │     │     └─ hooks/
│  │  │  │     └─ <other-template>/...
│  │  │  └─ main.py                        # Mounts /api routers; serves SPA from ./web/static
│  │  ├─ migrations/                       # Alembic migrations
│  │  ├─ alembic.ini                       # Alembic config
│  │  ├─ pyproject.toml                    # Python project metadata
│  │  └─ tests/
│  │     ├─ unit/                          # Fast, isolated logic tests
│  │     ├─ integration/                   # DB + API tests with test app
│  │     └─ e2e/                           # Optional full pipeline/contract tests
│  └─ web/                                 # React SPA (Vite)
│     ├─ src/                              # Routes, components, features
│     ├─ public/                           # Static public assets
│     ├─ package.json
│     └─ vite.config.ts
│
├─ packages/                               # Reusable Python libraries
│  └─ ade-engine/                          # installable package: ade_engine
│     ├─ pyproject.toml
│     ├─ src/ade_engine/                   # Engine runtime (I/O, pipeline, hooks)
│     └─ tests/                            # Engine unit tests
│
├─ specs/                                   # JSON Schemas & formal definitions
│  ├─ config-manifest.v1.json
│  └─ template-manifest.v1.json
│
├─ examples/                                # Sample inputs/outputs
├─ docs/                                    # Developer guides, HOWTOs, runbooks
├─ scripts/                                 # Repo-level helper scripts
│
├─ infra/                                   # Deployment infrastructure
│  ├─ docker/
│  │  └─ api.Dockerfile                     # Multi-stage build: web → api/app/web/static
│  ├─ compose.yaml                          # Local prod-style stack
│  └─ k8s/                                  # Optional: Helm/manifests
│
├─ Makefile                                 # Developer entrypoints
├─ .env.example                             # Example env vars
├─ .editorconfig
├─ .pre-commit-config.yaml
├─ .gitignore
└─ .github/workflows/                       # CI (lint, test, build, publish)
```

Everything ADE produces (config_packages, venvs, jobs, logs, cache, etc..) is persisted under `./data/...` by default. Override `ADE_DOCUMENTS_DIR`, `ADE_CONFIGS_DIR`, `ADE_VENVS_DIR`, `ADE_JOBS_DIR`, or `ADE_PIP_CACHE_DIR` to relocate any storage area.

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
│     ├─ .venv/                     # One Python venv per config
│     │  └─ <config_id>/
│     │     ├─ bin/python
│     │     ├─ ade-runtime/
│     │     │  ├─ packages.txt
│     │     │  └─ build.json
│     │     └─ <site-packages>/
│     │        ├─ ade_engine/
│     │        └─ ade_config/
│     ├─ jobs/
│     │  └─ <job_id>/
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

1. Run `npm run ci`.
2. Read JSON output (stdout).
3. Fix first error.
4. Re-run until `"ok": true`.

---

## 🔧 TODO IN FUTURE WHEN POSSIBLE

* Add linting/formatting: `ruff`/`black` (Python), `eslint`/`prettier` (JS).

---

## 🤖 Agent Rules

1. Always run `npm run test` before committing and `npm run ci` before pushing or opening a PR.

---

**End of AGENTS.md**
