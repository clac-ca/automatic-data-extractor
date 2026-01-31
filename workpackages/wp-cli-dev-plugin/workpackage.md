# Work Package: ADE CLI Dev Plugin via Extras

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Split runtime and dev-only CLI commands using a plugin entry point so `ade-cli` stays lean in production while `ade-cli[dev]` exposes the full dev subcommand set. The base `ade` command will load optional plugins if installed, without bespoke repo checks.

### Scope

- In:
  - Add a plugin loading mechanism to `ade-cli` (entry points).
  - Create a dev plugin package that registers dev-only commands.
  - Wire `ade-cli[dev]` to install the plugin package.
  - Update docs/setup so dev installs get the extra commands.
  - Follow standard project structure and naming conventions with minimal complexity/abstractions.
- Out:
  - Refactors of dev command behavior or semantics.
  - Changing runtime command functionality.
  - Large dependency upgrades unrelated to the plugin change.

### Work Breakdown Structure (WBS)

1.0 Design and decisions
  1.1 Define command split and plugin boundaries
    - [x] Enumerate which subcommands are runtime-safe vs dev-only.
    - [x] Choose plugin group name (e.g., `ade_cli.plugins`) and plugin package name.
    - [x] Decide how `ade-cli[dev]` resolves the plugin in this repo (published vs local path).
    - [x] Decide plugin loading behavior (best-effort with warnings vs hard fail).

2.0 Plugin architecture implementation
  2.1 Add plugin loader to base CLI
    - [x] Add entry point loading in `ade_cli/cli.py` with safe error handling.
    - [x] Ensure base CLI imports only runtime modules by default.
    - [x] Make `ade reset` runnable without a repo checkout (skip repo-only cleanup when absent).
  2.2 Create dev plugin package
    - [x] Add new package (e.g., `apps/ade-cli-dev`) with `pyproject.toml` and minimal `src/`.
    - [x] Implement `register(app)` that adds dev subcommands by importing existing dev command modules.
    - [x] Add entry point registration in the plugin package.
  2.3 Wire extras
    - [x] Update `apps/ade-cli/pyproject.toml` `dev` extra to include the plugin package.
    - [x] Update `setup.sh` (and any dev docs) to install dev extras so `ade` shows dev commands.

3.0 Validation and docs
  3.1 Validate CLI behavior
    - [x] `pip install -e apps/ade-cli` shows runtime commands only.
    - [x] `pip install -e apps/ade-cli[dev]` shows dev commands in `ade --help`.
    - [x] Production Docker image builds without dev plugin and `ade --help` excludes dev commands.
  3.2 Documentation
    - [x] Update README/AGENTS or CLI docs to describe dev plugin behavior and install commands.

### Open Questions

- Dev extra should reference the local plugin package for repo installs (confirmed).
- Runtime commands: start, reset/clean, api, worker. Dev-only commands: dev, build, lint, test, ci, docker, bundle, web, cli, setup.
- Plugin loader should be best-effort with warnings on plugin load/register failures.

---

## Acceptance Criteria

- `ade-cli` alone exposes only runtime-safe subcommands and runs in the production image.
- Installing `ade-cli[dev]` adds the dev subcommand set without bespoke repo checks.
- The dev plugin package registers subcommands via entry points and is documented in setup instructions.

---

## Definition of Done

- WBS tasks are complete and checked.
- Docs updated to reflect dev plugin installation.
- CLI behavior validated for both prod and dev install paths.
