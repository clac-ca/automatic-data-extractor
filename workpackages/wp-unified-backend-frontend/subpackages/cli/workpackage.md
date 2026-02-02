# Work Package: Root ADE CLI + Service Delegation

Guiding Principle:
Make ADE a clean, unified, and easily operable system with one backend distribution, clear shared infrastructure, and a simple default workflow that still allows each service to run independently.


> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Implement a root `ade` CLI in the unified backend distribution that can start/dev/test all services by default and delegate to per-service CLIs for `api`, `worker`, and `web`. Ensure the CLI works for both local dev and containerized use.

### Scope

- In:
  - Root `ade` CLI with `start`, `dev`, `test`.
  - Subcommands: `ade api`, `ade worker`, `ade web`.
  - Support for `ADE_SERVICES` and optional `--services` argument.
  - Web commands delegating to npm/nginx entrypoint.
- Out:
  - Changes to the actual API/worker feature behavior.
  - Replacing existing `ade-api` and `ade-worker` commands.

### Work Breakdown Structure (WBS)

1.0 Root CLI package
  1.1 Create CLI package + entry point
    - [x] Add new Python module for `ade` (e.g. `ade_cli/cli.py`).
    - [x] Register `ade` console script in backend `pyproject.toml`.
  1.2 Core commands
    - [x] Implement `ade start` to run api+worker+web by default.
    - [x] Implement `ade dev` to run api dev + worker + web dev.
    - [x] Implement `ade test` to run api + worker + web tests.
    - [x] Add `--services` and `ADE_SERVICES` handling.

2.0 Service delegation
  2.1 API delegation
    - [x] Implement `ade api <args>` delegating to `ade-api` CLI.
  2.2 Worker delegation
    - [x] Implement `ade worker <args>` delegating to `ade-worker` CLI.
  2.3 Web delegation
    - [x] Implement `ade web start|dev|build|test|lint|typecheck|preview` via npm/nginx.
    - [x] Keep nginx start via `frontend/ade-web/nginx/entrypoint.sh` (standard entrypoint naming).
  2.4 DB delegation
    - [x] Implement `ade db migrate` (and optional history/current/stamp).
    - [x] Keep `ade api migrate` as an alias to `ade db migrate` (optional).

3.0 Operational details
  3.1 Process orchestration
    - [x] Spawn subprocesses with clean signal handling (tini in container).
    - [x] Fail fast if any child process exits unexpectedly.
  3.2 Docs touchpoints
    - [x] Update CLI usage in docs to reflect `ade` commands.

### Open Questions

- None.

---

## Acceptance Criteria

- `ade start` runs api + worker + web by default.
- `ade dev` runs api dev + worker + web dev.
- `ade test` runs all three test suites.
- `ade api`, `ade worker`, `ade web` delegate correctly to their service commands.
- `ade db migrate` executes migrations via the shared DB package.

---

## Definition of Done

- Root `ade` CLI is installed with the backend package.
- Commands function both locally and inside the container image.
- CLI usage is documented.
