# AGENTS.md

This file is **for AI coding agents** working on the `ade` codebase. ADE is a lightweight, configurable engine for normalizing Excel/CSV files at scale.

## Repo map

```
automatic-data-extractor/
├─ backend/
│  ├─ pyproject.toml   # Unified backend project metadata/scripts/deps
│  ├─ uv.lock          # Unified backend lockfile
│  ├─ src/             # Python packages (ade, ade_api, ade_worker, ade_db, ade_storage)
│  └─ tests/           # Backend test suites (api + worker)
├─ frontend/
│  ├─ src/             # React/Vite SPA source
│  └─ public/          # Static web assets
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
./setup.sh
```

```bash
# CLI discovery (source of truth)
cd backend && uv run ade --help
cd backend && uv run ade-api --help
cd backend && uv run ade-worker --help
cd backend && uv run ade-engine --help
```

```bash
# Common workflows
cd backend && uv run ade dev              # api + worker + web (reload)
cd backend && uv run ade start            # api + worker + web (prod-style)
cd backend && uv run ade api dev          # api only (reload)
cd backend && uv run ade worker start
cd backend && uv run ade web dev
```

```bash
# Quality checks
cd backend && uv run ade api types
cd backend && uv run ade api lint
cd backend && uv run ade api test
cd backend && uv run ade worker test
cd backend && uv run ade web lint
cd backend && uv run ade web test
cd backend && uv run ade test
```

```bash
# Build web assets
cd backend && uv run ade web build
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

## Frontend API types

- Generated types: `frontend/src/types/generated/openapi.d.ts`.
- If missing/stale, run `ade api types` before touching frontend API code.
- Import shapes via curated types module (`@schema`) instead of `@schema/*`.

## Agent primer (collaboration norms)

- Default branch: `development` (PRs and direct work target this branch).
- Commit style: Conventional Commits (`feat:`, `fix:`, `deps:`, `chore:`).
- Use `deps:` for dependency updates that should trigger a patch release.
- Stage only task-related files; avoid bundling unrelated changes.
- Versions/changelog are managed by Release Please; do not bump `VERSION` or `CHANGELOG.md` manually unless requested.
- Official releases are created from `main`; `development` and `main` are branch channels for image tags.
- SemVer mapping:
  - `fix:` / `deps:` -> patch release
  - `feat:` -> minor release
  - `feat!:` or `BREAKING CHANGE:` footer -> major release
- If a specific version must be forced, use a `Release-As: X.Y.Z` footer in the commit body.
- Runtime version metadata (`ADE_APP_VERSION`, `ADE_APP_COMMIT_SHA`) is CI-managed; do not ask users to set these in `.env` for normal deployments.
- Production deployments should pin immutable release tags via `ADE_DOCKER_TAG=vX.Y.Z`.
- See `CONTRIBUTING.md` for the full collaboration and release flow.

## 🤖 Agent rules

1. Always run `cd backend && uv run ade test` (or the affected service tests) before committing and run the relevant frontend/backend checks for touched areas.
