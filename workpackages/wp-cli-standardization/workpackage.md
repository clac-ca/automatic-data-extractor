# Work Package: CLI Standardization Across Services

Guiding Principle:
Make ADE CLI commands consistent, discoverable, and unsurprising across all services.

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Standardize CLI structure and command surfaces across the root `ade` CLI and all service CLIs (`ade-api`, `ade-worker`, `ade-db`, `ade-storage`, `ade web`). Ensure each CLI follows the same Typer patterns (app setup, callbacks, error handling, help output), aligns on naming conventions, and uses consistent command semantics. Keep web commands mapped to npm scripts (no custom Node wrapper). Update the CLI reference and validate the command matrix.

### Standard CLI template (Typer)

```python
app = Typer(add_completion=False, invoke_without_command=True, help="...")

@app.callback()
def _main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())

@app.command()
def start(...): ...

if __name__ == "__main__":
    app()
```

### Naming conventions and semantics

- Root: `ade start`, `ade dev`, `ade test`.
- Services: `start`, `dev`, `test` where applicable; `lint`/`typecheck` for code quality; `routes`/`types`/`users` only for API.
- DB: `migrate`, `history`, `current`, `stamp`.
- Storage: `check`.
- Web: `dev`, `build`, `test`, `test:watch`, `test:coverage`, `lint`, `typecheck`, `preview`, `start` (nginx entrypoint).

### Delegation rules

- `ade <service>` is a thin delegator that forwards args to the service CLI.
- Delegators must be Typer apps with `invoke_without_command=True` and
  `context_settings={"allow_extra_args": True, "ignore_unknown_options": True}`.
- If invoked without args, delegators pass `--help` to the service CLI.
- Delegators set `help_option_names=[]` so `ade <service> --help` is forwarded.

### Command matrix (current)

- Root: `ade start`, `ade dev`, `ade test`
- API: `ade-api` / `ade api` -> `start`, `dev`, `migrate`, `routes`, `types`, `test`, `lint`, `users`
- Worker: `ade-worker` / `ade worker` -> `start`, `dev`, `gc`, `test`
- DB: `ade-db` / `ade db` -> `migrate`, `history`, `current`, `stamp`
- Storage: `ade-storage` / `ade storage` -> `check`
- Web: `ade web` -> `start`, `dev`, `build`, `test`, `test:watch`, `test:coverage`, `lint`, `typecheck`, `preview`

### Typer capabilities to use consistently

- App setup: `invoke_without_command=True` with a callback that prints help when no subcommand is invoked (no_args_is_help is disallowed due to exit code 2).
- Delegation: `context_settings={"allow_extra_args": True, "ignore_unknown_options": True}` for pass-through subcommands.
- Delegation help passthrough: set `help_option_names=[]` on delegator commands so `--help` forwards to the service CLI.
- Help text: use `help=` on apps/commands and docstrings for arguments/options.
- Help formatting: keep default help formatting (no custom rich markup unless explicitly needed).
- Errors: keep Typer's pretty exceptions defaults (do not disable).
- Completion: set `add_completion=False` everywhere (do not expose built-in completion options).
- Output style: ASCII-only output; prefer `->` for subprocess commands and `error:`/`warning:` prefixes (no emoji).
- Types: rely on type hints for conversion/validation (e.g., `bool`, `Path`, `Enum`, `datetime`).
- Options: prefer `Annotated[...]` when adding `Option`/`Argument` metadata.
- Flags: keep Typer's default `--flag/--no-flag` pairs (no custom names unless required).
- Required options: use `Annotated[..., Option()]` with no default when needed.
- Option names: use default `--param-name` unless there is a strong reason to override.

### Scope

- In:
  - Audit and align CLI structure, naming, and help output for root and service CLIs.
  - Standardize command naming conventions (start/dev/test/lint/etc.) and options.
  - Ensure `--help` and running a CLI without a subcommand shows help.
  - Ensure `ade <service>` delegates cleanly and passes through unknown args.
  - Keep `ade web` commands mapped to npm scripts.
  - Update CLI reference documentation and help matrix.
- Out:
  - Changing service runtime behavior beyond CLI wiring.
  - Adding new product features unrelated to CLI consistency.
  - Reworking web build/test tooling beyond command wiring.

### Work Breakdown Structure (WBS)

1.0 Standards and assessment
  1.1 Define CLI conventions (structure, naming, help behavior, error handling)
    - [x] Document the standard CLI template for Typer apps (app init, callback, commands, exit handling).
    - [x] Define naming conventions and command semantics across services.
    - [x] Define delegation rules for `ade <service>`.
    - [x] Document Typer context settings for delegation (allow_extra_args/ignore_unknown_options).
    - [x] Document help formatting and pretty exceptions defaults.
    - [x] Document completion behavior (`add_completion=False` everywhere).
    - [x] Document standard parameter types and option/argument patterns.
  1.2 Inventory current command surfaces
    - [x] Capture the current command matrix for root and services.
    - [x] Identify inconsistencies and gaps vs the standard template.

2.0 Per-CLI standardization (subpackages)
  2.1 Subpackage: root-cli
    - [x] Execute subpackage: root-cli
  2.2 Subpackage: api-cli
    - [x] Execute subpackage: api-cli
  2.3 Subpackage: worker-cli
    - [x] Execute subpackage: worker-cli
  2.4 Subpackage: db-cli
    - [x] Execute subpackage: db-cli
  2.5 Subpackage: storage-cli
    - [x] Execute subpackage: storage-cli
  2.6 Subpackage: web-cli
    - [x] Execute subpackage: web-cli

3.0 Validation and docs
  3.1 Update CLI reference
    - [x] Update `docs/reference/cli.md` with any new or changed commands (no changes required).
  3.2 Validate command matrix
    - [x] Verify `--help` output for root and each service CLI.
    - [x] Verify running `ade`, `ade-api`, `ade-worker`, `ade-db`, `ade-storage` with no subcommand shows help.
    - [x] Verify `ade <service>` delegates and forwards args correctly.

### Open Questions

- None. Decisions locked: root `ade` in `backend/cli.py`, service CLIs in each package, `ade web` uses npm scripts.

---

## Acceptance Criteria

- Root and service CLIs follow the same Typer structure and help behavior.
- `ade`, `ade-api`, `ade-worker`, `ade-db`, and `ade-storage` show help when invoked with no subcommand.
- `ade <service>` delegates cleanly with consistent error handling.
- Command names and semantics are consistent across services (start/dev/test, etc.).
- Web commands remain mapped to npm scripts with clear help output.
- CLI reference docs reflect the final command surface.

---

## Definition of Done

- WBS tasks complete and checked.
- Command matrix validated.
- Docs updated.
