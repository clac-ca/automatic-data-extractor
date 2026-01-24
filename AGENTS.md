# AGENTS.md

This file is **for AI coding agents** working on the `ade` codebase. ADE is a lightweight, configurable engine for normalizing Excel/CSV files at scale.

## Repo map

```
automatic-data-extractor/
├─ apps/
│  ├─ ade-api/      # FastAPI backend (API only)
│  ├─ ade-web/      # React/Vite SPA
│  ├─ ade-worker/   # Background worker (builds + runs).
│  └─ ade-cli/      # Orchestration CLI (console script: ade)
├─ data/            # Workspaces, runs, docs, sample inputs/outputs
├─ docs/            # Guides, HOWTOs, runbooks
└─ scripts/         # Repo-level helper scripts
```

## Ownership boundaries

### `ade-api` (control plane)
- Auth and user/domain workflows
- Configurations lifecycle (draft/active/archived)
- Documents upload/storage metadata
- Create run intent (insert `runs` rows)
- Read/report run status/results and stream run events

### `ade-worker` (data plane)
- Claim/leasing semantics, retries/backoff, timeouts
- Environment provisioning and reuse
- Subprocess execution and NDJSON event logs
- Artifact storage paths and cleanup decisions
- Updating run results and statuses

### `ade-engine` (runtime engine, external repo)
- Core normalization/processing pipeline and domain logic
- CLI commands (`process`, `config`, `version`) and engine runtime APIs
- IO, mapping, validation, normalization rules, telemetry hooks

### `ade-config` (config packages)
- User-authored configuration package contents (mappings, schemas, rules, assets)
- Dependency manifests that drive `deps_digest` (e.g. `pyproject.toml`, `requirements*.txt`)
- Installs into the environment via editable install for rapid iteration

### `ade-web` (frontend SPA)
- UI/UX, routing, client-side state management
- Auth integration and API consumption
- Live updates via run/document event streams when available

## ade CLI essentials

```bash
# Dev env (repo root)
bash scripts/dev/setup.sh
```

```bash
# CLI discovery (source of truth)
ade --help
ade <command> --help
ade-engine --help
```

```bash
# Common workflows
ade dev
ade dev --no-worker
ade dev --api-only
ade dev --web-only
ade dev --worker-only
ade dev --api-port 9000

ade start
ade api
ade worker
```

```bash
# Quality checks
ade types
ade lint --scope backend
ade lint --scope frontend
ade lint --fix
ade tests
ade ci
ade ci --skip-types
ade ci --skip-tests
```

```bash
# Utilities
ade build
ade bundle --ext md --out /tmp/bundle.md docs/
ade clean --yes
ade reset --yes
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

- Generated types: `apps/ade-web/src/types/openapi.d.ts`.
- If missing/stale, run `ade types` before touching frontend API code.
- Import shapes via curated types module (`@schema`) instead of `@schema/*`.

## 🤖 Agent rules

1. Always run `ade tests` before committing and `ade ci` before pushing or opening a PR.
