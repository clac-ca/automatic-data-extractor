**Workpackage:** Migrate root npm orchestration to a top-level Python CLI (`ade`), adopt the `apps/packages/tools` structure, and move `package.json` into `apps/ade-web` (no root Makefile, no `bin/` directory).

> **Note:** Keep this workpackage current. Check off tasks as they’re completed and add subtasks when new work is discovered.  
> Python CLI (`ade`) is the **canonical entrypoint**. There is **no root Makefile** and **no root `bin/` wrappers** once this is done.

---

## Target repo structure (for reference)

The repo should converge towards this layout:

```text
automatic-data-extractor/
├── apps/                         # Runtime applications (entrypoints)
│   ├── ade-api/                  # FastAPI backend
│   │   ├── pyproject.toml        # project name: "ade-api"
│   │   ├── src/ade_api/          # Python package: ade_api
│   │   ├── migrations/
│   │   └── tests/
│   └── ade-web/                  # React SPA (Vite)
│       ├── package.json          # "name": "ade-web"
│       ├── src/
│       ├── public/
│       └── tests/
│
├── packages/                     # Reusable Python libraries
│   ├── ade-engine/
│   │   ├── pyproject.toml        # project name: "ade-engine"
│   │   ├── src/ade_engine/       # Python package: ade_engine
│   │   └── tests/
│   └── ade-schemas/
│       ├── pyproject.toml        # project name: "ade-schemas"
│       ├── src/ade_schemas/      # Python package: ade_schemas
│       └── tests/
│
├── tools/                        # Dev/ops tooling (CLIs, scripts)
│   └── ade-tools/
│       ├── pyproject.toml        # project name: "ade-tools"
│       │                         # exposes console script: ade = "ade_tools.cli:app"
│       ├── src/ade_tools/        # Python orchestration CLI (ade ...)
│       └── tests/
│
├── data/                         # Runtime / environment data (gitignored)
│   ├── config_packages/
│   ├── db/
│   ├── documents/
│   └── jobs/
│
├── docs/                         # Documentation
│   ├── admin-guide/
│   ├── developers/
│   └── workpackages/
│
├── infra/                        # Infra / deployment config
│   ├── docker/
│   │   ├── Dockerfile.api
│   │   ├── Dockerfile.web        # optional
│   │   └── ...
│   └── compose.yaml
│
├── scripts/                      # Repo-level helper scripts (shell/python)
│
├── pyproject.toml                # Shared tooling config only (ruff/pytest/mypy/etc.)
├── README.md
├── CHANGELOG.md
├── .env.example
├── .editorconfig
├── .pre-commit-config.yaml
└── etc...
````

> **Important:** We will **remove the root `bin/` directory** and any shell wrappers that previously provided an `ade` command. The `ade` command will now come from the `ade-tools` Python project via `[project.scripts]`.

---

## Phase 0 — Repo structure & naming alignment

* [ ] **Rename app folders for consistency:**

  * Rename `apps/api` → `apps/ade-api`.
  * Rename `apps/web` → `apps/ade-web`.
  * Update any hard-coded paths (Dockerfiles, compose, CI, scripts, docs, AGENTS) that reference `apps/api` or `apps/web`.

* [ ] **Ensure Python project metadata matches the structure:**

  * In `apps/ade-api/pyproject.toml`:

    * Set `name = "ade-api"` (or `ade_api` as appropriate).
    * Configure src layout so the package is `ade_api` under `src/ade_api/`.
  * In `packages/ade-engine/pyproject.toml`:

    * `name = "ade-engine"`, package `ade_engine` under `src/ade_engine/`.
  * In `packages/ade-schemas/pyproject.toml`:

    * `name = "ade-schemas"`, package `ade_schemas` under `src/ade_schemas/`.

* [ ] **Ensure frontend project metadata is aligned:**

  * In `apps/ade-web/package.json` (after it’s moved; see Phase 3):

    * Set `"name": "ade-web"`.

* [ ] **Root `pyproject.toml` as tooling-only:**

  * Ensure root `pyproject.toml` contains **only** shared `[tool.*]` sections (ruff, pytest, mypy, etc.).
  * Do **not** define a `[project]` at the root.

* [ ] **Create `tools/ade-tools` project skeleton:**

  * Create `tools/ade-tools/pyproject.toml` with:

    * `[project]` metadata (`name = "ade-tools"`).
    * A console script:

      ```toml
      [project.scripts]
      ade = "ade_tools.cli:app"
      ```
    * `src` layout configured so Python package is `ade_tools` under `src/ade_tools/`.
  * Create directories:

    * `tools/ade-tools/src/ade_tools/`
    * `tools/ade-tools/tests/`

* [ ] **Define the canonical entrypoint:**

  * Decide and document:

    * The canonical orchestration entrypoint is the **Python CLI** `ade` (console script from `ade-tools`).
    * CI, docs, and AGENTS must call `ade ...` (or `python -m ade_tools.cli ...`), **not** `npm run ...` or `make`.

* [ ] **Bootstrap / venv model (documented):**

  * Define the standard local setup from repo root:

    1. `python -m venv .venv`
    2. Activate venv.
    3. `pip install -e tools/ade-tools`
       (and editable installs for `apps/ade-api` + `packages/*` as needed; this can later be automated by `ade setup`).
  * Clarify that:

    * venv creation is a one-time manual step.
    * `ade setup` handles ADE-specific setup (editable installs, `npm install` in `apps/ade-web`, etc.), **not** venv creation.
  * Note explicitly: **no root `bin/` wrappers are required**; `ade` is provided by the venv’s `bin/`/`Scripts/` directory via the console script.

---

## Phase 1 — Inventory existing workflows & scaffold the CLI

* [ ] **Inventory current root workflows and behavior:**

  * List all existing root commands/scripts, including but not limited to:

    * `setup`
    * `dev`, `dev:backend`, `dev:frontend`
    * `test`
    * `build`
    * `ci`
    * `lint*`
    * `openapi-typescript`
    * `routes`
    * `docker:*` (build/up/down/logs/test/etc.)
    * `clean` / `reset`
    * `workpackage`
  * For each workflow, record:

    * Env vars read/set.
    * Working directory (root vs `apps/ade-api` vs `apps/ade-web`).
    * External tools invoked (npm, pytest, uvicorn, alembic, docker, openapi-typescript, etc.).
    * Expected outputs/side effects (generated artifacts, SPA build, migrations, etc.).

* [ ] **Define CLI subcommand mapping:**

  * Decide and document the mapping between old workflows and new `ade` commands, for example:

    * `npm run setup` → `ade setup`
    * `npm run dev` → `ade dev`
    * `npm run dev:backend` → `ade dev --backend`
    * `npm run dev:frontend` → `ade dev --frontend`
    * `npm run test` → `ade test`
    * `npm run build` → `ade build`
    * `npm run ci` → `ade ci`
    * `npm run openapi-typescript` → `ade openapi-types`
    * `npm run routes` → `ade routes`
    * `npm run docker:*` → `ade docker:*`
    * `npm run clean` / `reset` → `ade clean` / `ade reset`
    * etc.
  * Capture this mapping in `docs/developers/cli-mapping.md` (or similar) for future reference.

* [ ] **Scaffold the `ade-tools` CLI:**

  * In `tools/ade-tools/src/ade_tools/`:

    * Create `cli.py` with a CLI framework (`argparse`, `click`, or `typer`).
    * Define stub subcommands/options corresponding to the mapped workflows (no orchestration logic yet).
  * Ensure after `pip install -e tools/ade-tools`:

    * `ade --help` works.
    * `python -m ade_tools.cli --help` works.

* [ ] **Add initial tests for CLI wiring:**

  * In `tools/ade-tools/tests/`:

    * Add basic tests to confirm:

      * CLI entrypoint is importable.
      * `ade --help` exits successfully.
      * Each subcommand at least exists and parses arguments.

---

## Phase 2 — Implement orchestration logic & parity in `ade-tools`

* [ ] **Backend flows (apps/ade-api):**

  * Implement:

    * `ade dev --backend`: start the FastAPI dev server (matching current behavior).
    * `ade test`: run pytest across `apps/ade-api` and relevant `packages/*` as currently done.
    * `ade migrate` (if separate): run Alembic migrations as currently wired.
  * Ensure correct:

    * Working directory (`apps/ade-api` when appropriate).
    * Env var setup (e.g., app env, DB URL).

* [ ] **Frontend flows (apps/ade-web):**

  * Implement:

    * `ade dev --frontend`: `cd apps/ade-web` and run `npm install` (if needed) + `npm run dev`.
    * `ade build-frontend` (or include frontend build in `ade build`): `cd apps/ade-web` and run `npm run build`.
    * `ade openapi-types`: `cd apps/ade-web` and run the existing OpenAPI → TypeScript generation (e.g., `npx openapi-typescript ...`).
    * `ade routes`: `cd apps/ade-web` and run any existing route listing script.
  * Ensure:

    * Node and npm are invoked only under `apps/ade-web`.
    * Behavior matches existing npm-based scripts.

* [ ] **Integrated dev/build flows:**

  * Implement:

    * `ade dev`: orchestrate both backend and frontend (matching previous `npm run dev` semantics).
    * `ade build`: orchestrate backend build and frontend build, including copying SPA artifacts into the backend static dir if that’s the current pattern.

* [ ] **Docker helpers:**

  * Implement `ade docker:*` commands mirroring current Docker workflow, e.g.:

    * `ade docker:build` → `docker compose build` (or equivalent).
    * `ade docker:up` → `docker compose up -d`.
    * `ade docker:down` → `docker compose down`.
    * `ade docker:logs` → `docker compose logs` (with optional service args).
    * `ade docker:test` → run tests in containers as currently configured.
  * Ensure:

    * Commands run from the correct working directory (likely repo root).
    * Exit codes propagate failures properly.

* [ ] **Clean/reset flows:**

  * Implement:

    * `ade clean` / `ade reset` to remove build artifacts, caches, generated types, etc., matching current behavior.
  * Include safeguards so destructive operations are explicit and well-logged.

* [ ] **Behavioral fidelity & UX:**

  * For each CLI command:

    * Preserve key env vars and working directories.
    * Match or improve logging (clear “Starting X… / Done X / Failed X” messages).
    * Ensure non-zero exit codes on failure (for CI).
  * Document any intentional behavior differences in code comments and in a short `docs/developers/ade-cli-behavior.md`.

* [ ] **CLI tests & smoke checks:**

  * Extend tests in `tools/ade-tools/tests/` to:

    * Exercise major commands in a safe way (e.g., `ade dev --dry-run` if added, or via stubbed subprocess calls).
    * Ensure at least one CI job runs a minimal “smoke suite” of `ade` commands to catch regressions early.

---

## Phase 3 — Move Node project into `apps/ade-web` & update scripts

* [ ] **Relocate Node artifacts:**

  * Move root `package.json` and lockfile into `apps/ade-web/` (if not already there).
  * Ensure `apps/ade-web` contains:

    * `package.json` (`"name": "ade-web"`).
    * Any config currently at root that is truly frontend-specific (tsconfig, vite config, etc.), if applicable.

* [ ] **Update scripts that rely on root Node tooling:**

  * Update any scripts under `scripts/` (or elsewhere) that:

    * Assume `package.json` lives at the repo root.
    * Call `npm run ...` from root.
  * Refactor them to either:

    * Call `ade ...`, or
    * `cd apps/ade-web` before invoking npm (for frontend-only helpers that are intentionally independent of `ade`).

* [ ] **Document frontend-only workflows:**

  * Add or update `apps/ade-web/README.md` to include:

    * Local frontend-only commands:

      * `npm install`
      * `npm run dev`
      * `npm run build`
      * any other dev/test/lint tasks.
    * A note that the **normal** way to interact in the repo is via `ade` (e.g., `ade dev`, `ade build`), but frontend devs can still work directly under `apps/ade-web` if needed.

* [ ] **Remove root `bin/` directory and wrappers:**

  * Delete the root `bin/` directory and any prior `bin/ade` shell/PowerShell scripts that were used to expose an `ade` command.
  * Confirm that:

    * `ade` is now available via the Python console script installed into the venv (`.venv/bin/ade` or `.venv/Scripts/ade.exe`).
    * Docs reference this model (activate venv → run `ade ...`).

* [ ] **Remove root Node orchestration:**

  * After `ade` parity is proven (see Phase 5):

    * Remove any Node-based orchestration scripts previously used at root (e.g., `scripts/npm-*.mjs`).
    * Ensure there is no root `package.json`.

---

## Phase 4 — Docs, AGENTS, and CI migration

* [ ] **Update README and developer docs:**

  * In `README.md`, `docs/developers/*`, and quickstart docs:

    * Replace references to `npm run ...` and root-level Node orchestration with `ade ...`.
    * Document:

      * How to bootstrap: create venv, `pip install -e tools/ade-tools`, run `ade setup`.
      * Common workflows: `ade dev`, `ade test`, `ade build`, `ade ci`, `ade docker:*`, `ade openapi-types`, `ade routes`, `ade clean/reset`.
    * Explicitly mention that no root `bin/` wrapper is needed; `ade` comes from the Python project.

* [ ] **Update AGENTS and workpackages:**

  * In `AGENTS.md` and `docs/workpackages/*` / `docs/developers/workpackages/*`:

    * Ensure all instructions to AI agents use:

      * The new paths (`apps/ade-api`, `apps/ade-web`).
      * The new CLI (`ade ...`) instead of `npm run ...`.
    * Add a short section that explains the repo structure (`apps/packages/tools`) and the role of `ade`.

* [ ] **Update CI pipelines:**

  * Update all CI workflows (GitHub Actions, GitLab CI, etc.) to:

    * Create and activate a venv (or use system Python inside a CI image).
    * `pip install -e tools/ade-tools` (and other editable installs as needed, or delegate to `ade setup`).
    * Replace direct calls to old root scripts (`npm run ci`, etc.) with:

      * `ade setup`
      * `ade test`
      * `ade build`
      * `ade ci`
      * `ade docker:*` (where appropriate).
  * Ensure CI uses the same commands developers are expected to run locally.

---

## Phase 5 — Validation, cross-platform, and Docker acceptance

* [ ] **Functional parity validation:**

  * For each original workflow (from Phase 1 inventory):

    * Run the old command (if still available during migration) and the new `ade` command.
    * Confirm:

      * Exit codes behave as expected.
      * Artifacts are created in the same locations.
      * Dev servers start as before.
      * SPA builds and is served by `ade-api` as before.
  * Define acceptance criteria:

    * All previous workflows (`setup`, `dev`, `dev:backend`, `dev:frontend`, `test`, `build`, `ci`, Docker helpers, OpenAPI types, routes, clean/reset, workpackage) succeed via `ade` with no loss of functionality.

* [ ] **Cross-platform verification:**

  * Verify `ade` commands work on:

    * Windows (PowerShell or CMD with venv).
    * macOS.
    * Linux.
  * Confirm the documented bootstrap steps (venv + `pip install -e tools/ade-tools` + `ade setup`) function on all three.

* [ ] **Docker & Compose integration:**

  * Update Dockerfiles and `infra/compose.yaml` as necessary so images:

    * Install `ade-tools` (e.g., `pip install -e tools/ade-tools` or via built wheel).
    * Can run `ade` inside the container for ci/build/migrations, if desired.
  * Validate:

    * `docker compose up` brings up the system with the new structure (`apps/ade-api`, `apps/ade-web`).
    * Any containerized test or CI flows that rely on orchestration use `ade` and still pass.

---

When this workpackage is complete:

* The repo will follow the **`apps/ / packages/ / tools/`** pattern with consistent `ade-*` naming.
* `apps/ade-web` will own the frontend Node project (no root `package.json`).
* `tools/ade-tools` will provide a **Python-first, cross-platform CLI** `ade` that replaces all root npm orchestration.
* The old `bin/` directory and shell wrappers will be removed; `ade` will be provided via the Python console script in the venv.
* Root will be a clean, tooling-focused layer (shared `pyproject.toml`, docs, infra) with a single, intuitive way to run everything: **`ade`**.