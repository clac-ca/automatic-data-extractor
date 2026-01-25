# AGENT QUICKSTART FOR `ade` CLI

Start by exploring the built-in help:

```bash
ade --help                       # list commands
ade <command> --help             # inspect flags for any command
python -m ade_engine --help # engine CLI (installed via ade-worker; invoked directly)
```

Fast reference (run `--help` for details):

- `ade setup` — one-time repo setup (env, hooks).
- `ade dev [--api-only|--web-only|--worker-only|--no-worker] [--api-port 9000]` — run dev services (api/web/worker; runs migrations first).
- `ade start` — start API + worker together (single-container mode; runs migrations).
- `ade api dev|start|migrate|routes|users|types|test` — API-specific commands.
- `ade web dev|build|test` — web-specific commands.
- `ade worker dev|start|test` — worker-specific commands.
- `ade cli test` — CLI tests.
- `ade test [suite] [targets...]` — run unit/integration/all tests by target.
- `ade lint`, `ade ci` — validation pipelines.
- `ade bundle --ext md --out <file> [--include/--exclude ...]` — bundle files/dirs into Markdown.
- `ade clean` / `ade reset` — remove artifacts or reset local state.
- `ade docker build|run|api|worker|shell` — local Docker image shortcuts.

### Help snapshots (truncated)

```bash
$ ade --help
Usage: ade [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  setup     Bootstrap repo env and hooks
  dev       Run API/web dev servers (+ worker, runs migrations first)
  start     Start API + worker together (single-container mode)
  build     Build web assets
  test      Run test suites by target
  lint      Lint/format helpers
  bundle    Bundle files into Markdown
  docker    Local Docker helpers
  clean     Remove build artifacts/caches (use --all to drop node_modules)
  reset     Drop DB tables + reset storage + clean artifacts
  ci        Full lint/test/build pipeline
  api       API-specific commands
  web       Web-specific commands
  worker    Worker-specific commands
  cli       CLI-specific commands
```

```bash
$ python -m ade_engine process file --help
Usage: python -m ade_engine process file [OPTIONS]

Options:
  -i, --input PATH               Single input file
  -o, --output PATH              Output .xlsx file path (optional)
      --output-dir PATH          Output directory (optional)
      --logs-dir PATH            Logs directory (optional)
  -s, --input-sheet TEXT         Optional worksheet(s)
  --log-format [text|ndjson] Log output format
  --log-level TEXT               Log level
  --debug / --no-debug           Enable debug logging
  --quiet / --no-quiet           Reduce output
  --config-package PATH          Config package directory
      --help                     Show this message and exit.
```

Notes for agents:

- Always check `--help` before guessing flags.
- Use `python -m ade_engine ...` for engine runs; the `ade` wrapper no longer mounts the engine CLI.
- Respect repo structure: commands assume you’re at the repo root. Use `ade --help` to confirm available commands in this environment.

Quick examples:

```bash
# Run dev services (api+web+worker)
ade dev

# API-only dev server on a custom port
ade dev --api --api-port 9000

# Dev without the worker
ade dev --no-worker

# Worker only
ade dev --worker

# Run the worker
ade worker start

# Build web assets
ade build

# Run unit tests for all targets (default)
ade test

# Run integration tests for API + worker
ade test integration api worker

# Bundle files for LLM review
ade bundle --ext md --out /tmp/bundle.md docs/

# Bundle mixed files with filters (skips __pycache__ automatically)
ade bundle --include \"src/**\" --include \"apps/ade-api/src/ade_api/**/*.py\" --out /tmp/bundle.md

# Copy a bundle to the clipboard (opt-in)
ade bundle README.md apps/ade-api/AGENTS.md --clip

# Bundle a couple of specific files quickly
ade bundle README.md apps/ade-api/AGENTS.md --out /tmp/bundle.md

# Generate frontend types from OpenAPI
ade api types

# Run the engine directly (see full flags with `python -m ade_engine run --help`)
ade-engine config init ./tmp/my-config --package-name ade_config
python -m ade_engine process file --input data/samples/CaressantWRH_251130__ORIGINAL.xlsx --output-dir data/samples-output --logs-dir data/samples-output --config-package ./tmp/my-config
```
