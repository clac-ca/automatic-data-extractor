# AGENTS.md
ADE is a lightweight, configurable engine for normalizing Excel/CSV files at scale.

## Monorepo cheat sheet

```
automatic-data-extractor/
├─ apps/
│  ├─ ade-api/      # FastAPI backend (serves /api + built SPA)
│  │  ├─ src/ade_api/             # core app code
│  │  ├─ migrations/              # Alembic migrations
│  │  └─ templates/config_packages# starter config packages
│  ├─ ade-web/      # React/Vite SPA
│  │  ├─ src/                    # app/, screens/, ui/, schema/, generated-types/
│  │  └─ docs/                   # frontend architecture guides
│  ├─ ade-engine/   # Engine runtime (Python package)
│  │  ├─ src/ade_engine/         # engine code
│  │  └─ docs/                   # engine runtime/CLI docs
│  └─ ade-cli/      # Orchestration CLI (console script: ade)
│     └─ src/ade_tools/          # CLI commands
├─ data/            # Workspaces, runs, docs
├─ docs/            # Guides, HOWTOs, runbooks
└─ scripts/         # Repo-level helper scripts
```

Config templates live under `apps/ade-api/src/ade_api/templates/config_packages`.
Workspaces: `data/workspaces/<workspace_id>/...` (configs, venvs, runs, logs, docs)

Docs:
- Top-level `docs/` (guides, admin, templates, events).
- Engine: `apps/ade-engine/docs/` (runtime, manifest, IO, mapping, normalization, telemetry, CLI).
- Frontend: `apps/ade-web/docs/` (architecture, routing, data layer, auth, UI/testing).

## ⚡ CLI (ade) quickstart

Run `ade --help` for the full list; `ade <command> --help` for flags. Key commands:

- `./.venv/bin/ade ade setup` — initial repo setup (env, hooks).
- `./.venv/bin/ade ade dev` — backend/frontend dev servers (`--backend-only/--frontend-only`).
- `./.venv/bin/ade ade start` — serve API + built SPA.
- `./.venv/bin/ade ade build` — build frontend assets into `apps/ade-api/src/ade_api/web/static`.
- `./.venv/bin/ade ade tests` — run Python/JS test suites.
- `./.venv/bin/ade ade lint` — lint/format helpers.
- `./.venv/bin/ade ade bundle` — bundle files/dirs into Markdown for LLM/code review (filters, include/exclude, `--out`, `--no-clip`).
- `./.venv/bin/ade ade types` — generate frontend types from OpenAPI.
- `./.venv/bin/ade ade migrate` — run DB migrations.
- `./.venv/bin/ade ade routes` — list FastAPI routes.
- `./.venv/bin/ade ade users` — manage users/roles (see subcommands).
- `./.venv/bin/ade ade docker` — local Docker helpers.
- `./.venv/bin/ade ade lint` — lint/format helpers (`--fix` to auto-fix issues; start here before manual fixes).
- `./.venv/bin/ade ade clean` / `ade reset` — remove build artifacts/venvs/cache.
- `./.venv/bin/ade ade ci` — full pipeline (lint, test, build).
- `./.venv/bin/ade ade engine ...` — full `ade_engine` CLI (mirrors `python -m ade_engine`).

### Engine CLI (via `ade engine`)

Use `ade engine run --help` to see all flags. Highlights:

```bash
ade engine run \
  --input data/samples/example.xlsx \
  --config-package "data/templates/config_packages/DaRT Remittance" \
  --output-dir /tmp/out \            # or --output-file /tmp/out/normalized.xlsx
  --logs-dir /tmp/out/logs           # or --logs-file /tmp/out/logs/engine_events.ndjson
```

- Multiple inputs: repeat `--input` to run each file separately.
- If `--logs-*` is omitted, events stream to stdout only (no file sink).
- Defaults: output → `<output-dir>/normalized.xlsx` (or `<input_dir>/output/normalized.xlsx` if no dir given).

### Bundle examples

```bash
# Bundle docs as Markdown
ade bundle --ext md --out /tmp/bundle.md docs/

# Bundle with filters, no clipboard
ade bundle --include "src/**" --include "apps/ade-api/src/ade_api/**/*.py" \
           --exclude "**/__pycache__/**" --out /tmp/bundle.md --no-clip

# Bundle specific files quickly
ade bundle README.md apps/ade-api/AGENTS.md --out /tmp/bundle.md
```

## Frontend API types

- Generated types: `apps/ade-web/src/generated-types/openapi.d.ts`.
- If missing/stale, run `ade types` before touching frontend API code.
- Import shapes via curated schema module (`@schema`) instead of `@generated-types/*`.

## 🤖 Agent rules

1. Always run `ade tests` before committing and `ade ci` before pushing or opening a PR.
