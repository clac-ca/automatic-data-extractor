# AGENTS.md
ADE is a lightweight, configurable engine for normalizing Excel/CSV files at scale.

## Repo map

```
automatic-data-extractor/
├─ apps/
│  ├─ ade-api/      # FastAPI backend (serves /api + built SPA)
│  ├─ ade-web/      # React/Vite SPA
│  ├─ ade-engine/   # Engine runtime (Python package + Typer CLI)
│  └─ ade-cli/      # Orchestration CLI (console script: ade)
├─ data/            # Workspaces, runs, docs, sample inputs/outputs
├─ docs/            # Guides, HOWTOs, runbooks
└─ scripts/         # Repo-level helper scripts
```

Docs to know:
- Top-level `docs/` (guides, admin, templates, events)
- Engine: `apps/ade-engine/docs/` (runtime, manifest, IO, mapping, normalization, telemetry, CLI)
- Frontend: `apps/ade-web/docs/` (architecture, routing, data layer, auth, UI/testing)

## ade CLI essentials

Use `ade --help` and `ade <command> --help` for full flags; the engine CLI lives at `python -m ade_engine --help`.

- `ade setup` — one-time bootstrap (venv, hooks).
- `ade dev [--backend-only|--frontend-only] [--backend-port 9000]` — run dev servers.
- `ade start` — serve API + built SPA. `ade build` — build frontend assets.
- `ade tests`, `ade lint`, `ade ci` — validation pipelines. `ade types` — regen frontend API types.
- `ade migrate`, `ade routes`, `ade users`, `ade docker`, `ade clean` / `ade reset`, `ade bundle --ext md --out <file> [--include/--exclude ...]`.
- Config templates: `apps/ade-api/src/ade_api/templates/config_packages`; workspaces: `data/workspaces/<workspace_id>/...` (configs, venvs, runs, logs, docs).

### Help snapshots (truncated)

```bash
$ ade --help
Usage: ade [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  setup     Bootstrap repo env and hooks
  dev       Run backend/frontend dev servers
  start     Serve API + built SPA
  build     Build frontend assets
  tests     Run Python/JS tests
  lint      Lint/format helpers
  bundle    Bundle files into Markdown
  types     Generate frontend API types
  migrate   Run DB migrations
  routes    List FastAPI routes
  users     Manage users/roles
  docker    Local Docker helpers
  clean     Remove build artifacts/caches
  reset     Clean + venv reset
  ci        Full lint/test/build pipeline
```

```bash
$ python -m ade_engine --help
Usage: python -m ade_engine [OPTIONS] COMMAND [ARGS]...

Commands:
  process  Process inputs with the ADE engine (file/batch)
  config   Create and validate config packages
  version  Show engine version
```

## Engine CLI quick runs (current)

- Entrypoint: `python -m ade_engine process ...` or `ade-engine process ...`
- Output defaults (file mode): if no flags, writes `<input_parent>/<input_stem>_normalized.xlsx` and logs beside it. `--output` must be a `.xlsx` file. `--output-dir` changes only the directory. Batch mode always requires `--output-dir`; logs default beside outputs.

```bash
# 1) Scaffold a config package from the bundled template
ade-engine config init my-config --package-name ade_config

# 2) Validate the config package can be imported/registered
ade-engine config validate --config-package my-config

# 3) Process a single file (defaults output next to input)
ade-engine process file \
  --input data/samples/CaressantWRH_251130__ORIGINAL.xlsx \
  --config-package my-config

# 3b) Single file with explicit output dir
ade-engine process file \
  --input data/samples/CaressantWRH_251130__ORIGINAL.xlsx \
  --output-dir ./output \
  --config-package my-config

# 4) Process a batch directory (output dir required)
ade-engine process batch \
  --input-dir data/samples \
  --output-dir ./output/batch \
  --include "*.xlsx" \
  --config-package my-config
```

## Bundle examples

```bash
# Bundle docs as Markdown
ade bundle --ext md --out /tmp/bundle.md docs/

# Bundle with filters (skips __pycache__ automatically)
ade bundle --include "src/**" --include "apps/ade-api/src/ade_api/**/*.py" \
           --out /tmp/bundle.md

# Copy a bundle to the clipboard (opt-in)
ade bundle README.md apps/ade-api/AGENTS.md --clip

# Bundle specific files quickly
ade bundle README.md apps/ade-api/AGENTS.md --out /tmp/bundle.md
```

## Frontend API types

- Generated types: `apps/ade-web/src/generated-types/openapi.d.ts`.
- If missing/stale, run `ade types` before touching frontend API code.
- Import shapes via curated schema module (`@schema`) instead of `@generated-types/*`.

## 🤖 Agent rules

1. Always run `ade tests` before committing and `ade ci` before pushing or opening a PR.
