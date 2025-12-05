# AGENT QUICKSTART FOR `ade` CLI

Start by exploring the built-in help:

```bash
ade --help                # list commands
ade <command> --help      # inspect flags for any command
ade engine --help         # pass-through to ade_engine CLI (also try ade engine run --help)
```

Key commands (invoke with `ade <command> --help` for full flags):

- `setup` — one-time repo setup (env, hooks).
- `dev` — run backend/frontend dev servers (`--backend-only/--frontend-only`).
- `start` — serve API + built SPA.
- `build` — build frontend assets.
- `tests` — run Python/JS test suites.
- `lint` — lint/format (Python/JS) helpers.
- `bundle` — bundle files/dirs into Markdown for LLM/code review context (filters, include/exclude patterns, optional clipboard).
- `types` — generate frontend types from OpenAPI.
- `migrate` — run DB migrations.
- `routes` — list FastAPI routes.
- `users` — manage users/roles (see help for subcommands).
- `docker` — local Docker helpers.
- `clean` / `reset` — remove build artifacts/venvs/cache.
- `ci` — full pipeline (lint, test, build).
- `engine` — pass-through to `ade_engine` CLI for manual runs; use this to inspect or execute engine runs directly.

Notes for agents:

- Always check `--help` before guessing flags.
- `ade engine` forwards arguments verbatim; use it to discover current ade_engine run flags (output/events file options, etc.).
- Respect repo structure: commands assume you’re at the repo root. Use `ade --help` to confirm available commands in this environment.

Quick examples:

```bash
# Run both dev servers (backend+frontend)
ade dev

# Backend-only dev server on a custom port
ade dev --backend-only --backend-port 9000

# Build frontend assets
ade build

# Run all tests
ade tests

# Bundle files for LLM review
ade bundle --ext md --out /tmp/bundle.md docs/

# Bundle mixed files with filters (no clipboard)
ade bundle --include \"src/**\" --include \"apps/ade-api/src/ade_api/**/*.py\" --exclude \"**/__pycache__/**\" --out /tmp/bundle.md --no-clip

# Bundle a couple of specific files quickly
ade bundle README.md apps/ade-api/AGENTS.md --out /tmp/bundle.md

# Generate frontend types from OpenAPI
ade types

# Run the engine directly (see full flags with `ade engine run --help`)
ade engine run --input data/samples/example.xlsx --output-dir data/samples/output --events-dir data/samples/output
```
