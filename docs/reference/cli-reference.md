# CLI Reference

## If You Are New

Use this pattern locally inside this repository:

```bash
cd backend && uv run <command>
```

Example:

```bash
cd backend && uv run ade --help
```

`uv run` ensures commands use the repo's Python environment.

## Root CLI: `ade`

| Command | What it does |
| --- | --- |
| `ade start` | Start API + worker + web |
| `ade dev` | Start API + worker + web in dev mode |
| `ade test` | Run API, worker, and web tests |
| `ade reset` | Reset DB/storage/local state (destructive) |
| `ade api ...` | Run API subcommands |
| `ade worker ...` | Run worker subcommands |
| `ade db ...` | Run DB subcommands |
| `ade storage ...` | Run storage subcommands |
| `ade web ...` | Run web/frontend subcommands |
| `ade infra ...` | Manage local infra stack (Postgres + Azurite) |

Key options for `ade start`/`ade dev`:

- `--services`
- `--migrate` / `--no-migrate`
- `--open` (open ADE web in the default browser when the web service is reachable)
- `ADE_API_PROCESSES` applies to `ade start`; `ade dev` keeps API reload mode (single process)

## API CLI: `ade-api`

| Command | What it does |
| --- | --- |
| `ade-api dev` | Run API in development mode |
| `ade-api start` | Run API in production-style mode |
| `ade-api test <suite>` | Run tests (`unit`, `integration`, `all`) |
| `ade-api lint` | Run lint/type checks |
| `ade-api routes` | Print route list |
| `ade-api types` | Generate OpenAPI + TypeScript types |

Common API options:

- `ade-api start --processes N`
- `ade-api dev --processes N` (disables reload when `N > 1`)

## Worker CLI: `ade-worker`

| Command | What it does |
| --- | --- |
| `ade-worker start` | Start worker |
| `ade-worker dev` | Start worker in dev mode |
| `ade-worker test <suite>` | Run tests (`unit`, `integration`, `all`) |
| `ade-worker gc` | Run one garbage-collection pass |

## DB CLI: `ade-db`

| Command | What it does |
| --- | --- |
| `ade-db migrate [revision]` | Apply migrations |
| `ade-db history [range]` | Show migration history |
| `ade-db current` | Show current revision |
| `ade-db stamp <revision>` | Set revision without running migrations |
| `ade-db reset --yes` | Reset schema and re-migrate (destructive) |

## Storage CLI: `ade-storage`

| Command | What it does |
| --- | --- |
| `ade-storage check` | Test storage connection |
| `ade-storage reset --yes --mode <prefix-or-container>` | Delete blobs (destructive) |

## Web Commands: `ade web`

| Command | What it does |
| --- | --- |
| `ade web start` | Serve built frontend via nginx |
| `ade web dev` | Start Vite dev server |
| `ade web build` | Build web assets |
| `ade web test` | Run frontend tests |
| `ade web lint` | Run frontend lint |
| `ade web typecheck` | Run frontend typecheck |

## Quick Recipes

```bash
cd backend && uv run ade infra up
cd backend && uv run ade infra info
cd backend && uv run ade infra down -v --rmi all
cd backend && uv run ade dev
cd backend && uv run ade dev --open
cd backend && uv run ade start --services worker --no-migrate
cd backend && uv run ade db migrate
cd backend && uv run ade api types
```
