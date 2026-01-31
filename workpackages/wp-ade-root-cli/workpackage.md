# Work Package: Root ADE CLI via ade-api

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Remove the separate `ade-cli` package and define a single `ade` console script entry point in `ade-api`, delegating to `ade-api`, `ade-worker`, and web commands. Root `ade` owns orchestration (`start`/`dev`) while service CLIs keep their own commands. The API remains API-only; the web UI is served by nginx (from the same image) via `ade web serve`. `ade start` runs API + worker + nginx in one container, with an option to run a subset of services in one container.

### Scope

- In:
  - Remove the `ade-cli` package and any plugin wiring introduced for it.
  - Add `ade` entry point to `ade-api` (and keep `ade-api` CLI).
  - Implement a minimal root CLI that delegates to `ade-api`, `ade-worker`, and `ade-web` (npm scripts) where appropriate.
  - Add root `ade start` (api + worker + nginx) and `ade dev` (api + worker + web dev server).
  - Make `ade-api start` API-only (no web mount).
  - Serve the SPA from nginx (in the same image), not the API.
  - Provide a `ade web serve` command for running nginx.
  - Allow running any subset of services in one container via a simple `ade start` selector (e.g., api+web).
  - Update setup/docs to reflect the new CLI layout and usage.
  - Use standard structure and naming with minimal complexity/abstractions.
- Out:
  - Changing the semantics of existing `ade-api`/`ade-worker` commands.
  - Reworking web build/test tooling beyond wiring nginx serve.
  - Large dependency upgrades unrelated to the CLI restructuring.

### Work Breakdown Structure (WBS)

1.0 Design and decisions
  1.1 Define ownership and command surface
    - [x] Confirm `ade-api` owns the root `ade` entry point.
    - [x] Enumerate which subcommands map to `ade-api`, `ade-worker`, and web (npm).
    - [x] Decide which commands remain only in per-service CLIs (if any).
    - [x] Use conditional dev command registration (Option A) based on dev-only dependency presence.
    - [x] Define root `ade start`/`ade dev` orchestration behavior (start = api + worker + nginx).
    - [x] Confirm `ade-api start` is API-only and root `ade start` serves web via nginx.
    - [x] Confirm SPA is served by nginx from the same image (not the API).
    - [x] Decide how to select subsets of services for `ade start`.

2.0 Remove ade-cli package
  2.1 Delete package and references
    - [x] Remove `apps/ade-cli` and `apps/ade-cli-dev` packages.
    - [x] Remove `ade-cli` references from setup scripts and docs.
    - [x] Update any imports or tooling that referenced `ade-cli`.

3.0 Implement root `ade` CLI in ade-api
  3.1 Add entry point
    - [x] Add `ade` console script in `apps/ade-api/pyproject.toml`.
  3.2 Implement root CLI module
    - [x] Create a minimal `ade_api/cli_root.py` (or similar) that registers subcommands.
    - [x] Hook `ade-api` CLI under `ade api` and `ade-worker` under `ade worker`.
    - [x] Provide web wrappers that shell to npm (dev/build/test/lint) with clear errors if Node is missing.
    - [x] Gate dev-only commands based on a dev-only dependency (Option A).
  3.3 Root orchestration commands
    - [x] Add root `ade start` (api + worker + nginx).
    - [x] Add root `ade dev` (api + worker + web dev server with reload).
    - [x] Remove `ade-api start-all` and update container entrypoints to use `ade start`.
    - [x] Ensure `ade-api start` is API-only.
    - [x] Add `ade web serve` (nginx) and wire into root start.

4.0 Docker and web serving
  4.1 Update root image
    - [x] Build `apps/ade-web` in the main Dockerfile and copy dist into the image.
    - [x] Install nginx in the main image and run it as the non-root user.
  4.2 Remove separate web image
    - [x] Remove `apps/ade-web/Dockerfile` and related web image artifacts.

5.0 Update docs and setup
  5.1 Update setup scripts
    - [x] Adjust `setup.sh` to install `ade-api`/`ade-worker` and explain `ade` entry point ownership.
  5.2 Update docs
    - [x] Update developer/admin docs to reference `ade` from `ade-api` and per-service CLIs.
    - [x] Update docker-compose files for one-image and split-service patterns.
    - [x] Document nginx-based `ade web serve` and `ade start` service selection.

6.0 Validation
  6.1 Command matrix
    - [x] Enumerate root + service command surfaces to validate (help output + basic execution).
    - [x] Root: `ade --help`, `ade start --help`, `ade dev --help`, `ade web serve --help`
    - [x] API: `ade api --help`, `ade api start --help`, `ade api dev --help`
    - [x] Worker: `ade worker --help`, `ade worker start --help`
    - [x] Web (dev-only): `ade web dev --help`, `ade web build --help`, `ade web lint --help`, `ade web test --help`
  6.2 Dev install
    - [x] `python -m pip install -e apps/ade-api[dev] -e apps/ade-worker[dev]` provides `ade`.
    - [x] `ade --help` shows root commands; `ade api --help` and `ade worker --help` work.
    - [x] `ade start --help`, `ade dev --help`, and `ade web serve --help` show orchestration commands.
  6.3 Production image
    - [x] Docker image build exposes `ade` and includes nginx + web dist.
    - [x] Container `ade start` launches API + worker + nginx.
    - [x] Container `ade web serve` serves the SPA and proxies `/api` to the API.

### Open Questions

- npm invocation: run from `apps/ade-web` (repo-root detection required).
- Dev dependency gate: use `pytest` (installed via `ade-api[dev]`).

---

## Acceptance Criteria

- The `ade` command is provided by `ade-api` and works on Linux/Windows when installed in a venv or image.
- Commands remain owned by their services; root CLI is a thin delegator without bespoke repo checks.
- `ade start` runs API + worker + nginx; `ade dev` runs API + worker + web dev server with reload.
- `ade-api start` is API-only (no SPA mount).
- The SPA is served by nginx from the main image (or via `ade web serve`) with `/api` proxying to the API.
- The same image can run API-only, worker-only, web-only, or full stack via CLI selection.
- `ade-cli` and plugin packages are removed cleanly.
- Docs and setup instructions reflect the new structure.

---

## Definition of Done

- WBS tasks are complete and checked.
- Docs updated to reflect new CLI ownership and usage.
- Root CLI validated in dev install and Docker image.
