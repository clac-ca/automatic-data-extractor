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

- `ade --help` and `ade <command> --help` surface all flags; `ade engine --help` mounts the engine Typer CLI.
- Common commands: `ade setup`, `ade dev`, `ade start`, `ade build`, `ade tests`, `ade lint`, `ade types`, `ade migrate`, `ade routes`, `ade users`, `ade docker`, `ade clean`/`ade reset`, `ade ci`, `ade bundle`.
- Config templates live under `apps/ade-api/src/ade_api/templates/config_packages`.
- Workspaces: `data/workspaces/<workspace_id>/...` (configs, venvs, runs, logs, docs).

## Engine CLI smoke tests (revamped)

`apps/ade-engine/src/ade_engine/cli.py` is a Typer CLI surfaced as `ade engine ...` (or `python -m ade_engine ...`). It now plans per-input outputs/logs, supports `--input-dir` globs, and defaults to clean stdout/stderr behavior.

- Inputs: combine `--input` (repeatable) and `--input-dir` with `--include/--exclude` (defaults to `*.xlsx, *.csv` when not provided).
- Outputs: if no flags are set, output lands in `<input_dir>/output/<input_stem>_normalized.xlsx`. When multiple inputs are provided, `--output-dir`/`--logs-dir` are nested per input stem to avoid collisions.
- Logs: `--log-format text|ndjson` (default text). Text mode writes readable lines to stderr and prints a summary to stdout; NDJSON mode streams to stdout unless `--logs-file/--logs-dir` is set, in which case it writes `engine_events.ndjson`. Text logs default to `engine.log`.
- Metadata: `--meta KEY=VALUE` attaches to every emitted event.

### Quick text-mode run (good sanity check)

Use the template config package shipped in the repo and a sample input:

```bash
ade engine run \
  --input data/samples/input/z_pass6_synthetic_contacts_net.xlsx \
  --config-package data/templates/config_packages/default \
  --output-dir data/samples/output/cli-smoke \
  --logs-dir data/samples/output/cli-smoke
```

Expected: output at `data/samples/output/cli-smoke/z_pass6_synthetic_contacts_net_normalized.xlsx`, logs at `data/samples/output/cli-smoke/engine.log`, and a one-line summary on stdout.

### NDJSON stream run (for API-style validation)

```bash
ade engine run \
  --input data/samples/input/z_pass6_synthetic_contacts_net.xlsx \
  --config-package data/templates/config_packages/default \
  --log-format ndjson \
  --output-dir /tmp/ade-engine/ndjson-smoke
```

Expected: NDJSON events on stdout (kept clean via `protect_stdout`), with output at `/tmp/ade-engine/ndjson-smoke/z_pass6_synthetic_contacts_net_normalized.xlsx`. Add `--logs-dir /tmp/ade-engine/ndjson-smoke` to also persist `engine_events.ndjson`.

### Batch multiple inputs

```bash
ade engine run \
  --input-dir data/samples/input \
  --config-package data/templates/config_packages/default \
  --include "*.xlsx" --exclude "detector-pass*" \
  --output-dir /tmp/ade-engine/batch \
  --logs-dir /tmp/ade-engine/batch
```

Outputs/logs are automatically split under `/tmp/ade-engine/batch/<input_stem>/...` so each file gets its own folder.

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
