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
$ python -m ade_engine run --help
Usage: python -m ade_engine run [OPTIONS]

Options:
  -i, --input PATH               Source file(s) (repeatable)
      --input-dir PATH           Recurse for inputs
      --include TEXT             Glob applied under --input-dir
      --exclude TEXT             Glob to skip under --input-dir
  -s, --input-sheet TEXT         Optional worksheet(s)
      --output-dir PATH          Output directory (default: ./output)
      --logs-dir PATH            Logs directory (default: ./logs)
      --log-format [text|ndjson] Log output format
      --meta TEXT                KEY=VALUE metadata (repeatable)
      --config-package TEXT      Config package name or path
      --help                     Show this message and exit.
```

## Engine CLI smoke tests (revamped)

`apps/ade-engine/src/ade_engine/cli/app.py` is a Typer CLI invoked as `python -m ade_engine ...`. It resolves inputs, drops most implicit defaults, and writes artifacts into explicit `--output-dir`/`--logs-dir` roots (defaults: `./output`, `./logs`).

- Inputs: combine `--input` (repeatable) and `--input-dir` with `--include/--exclude` (defaults to `*.xlsx, *.csv` when not provided).
- Outputs: always land in `<output_dir>/<input_stem>_normalized.xlsx`.
- Logs: `--log-format text|ndjson` (default text). Log files are written under `--logs-dir` as `<input_stem>_engine.log` (text) or `<input_stem>_engine_events.ndjson` (ndjson). A one-line summary always prints in text mode.
- Metadata: `--meta KEY=VALUE` attaches to every emitted event.

### Quick text-mode run (good sanity check)

Use the template config package shipped in the repo and a sample input:

```bash
python -m ade_engine run \
  --input data/samples/CaressantWRH_251130__ORIGINAL.xlsx \
  --config-package data/templates/config_packages/default \
  --output-dir data/samples-output \
  --logs-dir data/samples-output
```

Expected: output at `data/samples-output/CaressantWRH_251130__ORIGINAL_normalized.xlsx`, logs at `data/samples-output/CaressantWRH_251130__ORIGINAL_engine.log`, and a one-line summary on stdout.

### NDJSON stream run (for API-style validation)

```bash
python -m ade_engine run \
  --input data/samples/CaressantWRH_251130__ORIGINAL.xlsx \
  --config-package data/templates/config_packages/default \
  --log-format ndjson \
  --output-dir /tmp/ade-engine/ndjson-smoke \
  --logs-dir /tmp/ade-engine/ndjson-smoke
```

Expected: NDJSON events in `/tmp/ade-engine/ndjson-smoke/CaressantWRH_251130__ORIGINAL_engine_events.ndjson` with output at `/tmp/ade-engine/ndjson-smoke/CaressantWRH_251130__ORIGINAL_normalized.xlsx`.

### Batch multiple inputs

```bash
python -m ade_engine run \
  --input-dir data/samples \
  --config-package data/templates/config_packages/default \
  --include "*.xlsx" --exclude "detector-pass*" \
  --output-dir /tmp/ade-engine/batch \
  --logs-dir /tmp/ade-engine/batch
```

Outputs/logs use the flat `<output_dir>/<input_stem>_normalized.xlsx` and matching log names; choose unique output/log roots when processing many files.

## Bundle examples

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
