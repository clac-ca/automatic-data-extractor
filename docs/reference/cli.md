# CLI reference

## Root CLI

```bash
ade start            # start api + worker + web (default)
ade dev              # start api dev + worker + web dev
ade test             # run api + worker + web tests
ade reset            # reset db + storage + local data/venv (destructive)
```

`ade reset` requires `--yes`.

Ports (fixed):
- `ade dev`: web on `http://localhost:8000`, API on `http://localhost:8001`
- `ade start`: web on `http://localhost:8000`, API on `http://localhost:8001`

Ports are fixed: web `8000`, API `8001`.

Env equivalents: `ADE_INTERNAL_API_URL` (origin only, no `/api`), `ADE_PUBLIC_WEB_URL`.

Service selection:

- `ADE_SERVICES=api,worker,web` (default)
- `ADE_SERVICES=api` (only API)
- `ADE_SERVICES=worker` (only worker)
- `ADE_SERVICES=web` (only web)

You can also pass `--services` to `ade start` and `ade dev`.

Migrations on start:
- `ade start` and `ade dev` run `ade db migrate` by default when starting `api` and/or `worker`.
- Disable with `--no-migrate` or `ADE_DB_MIGRATE_ON_START=false`.

## API

```bash
ade api start
ade api dev
ade api routes
ade api types
ade api users
ade api test
ade api lint
```

## Worker

```bash
ade worker start
ade worker dev
ade worker gc
ade worker test
```

## Web

```bash
ade web start
ade web dev
ade web build
ade web test
ade web test:watch
ade web test:coverage
ade web lint
ade web typecheck
ade web preview
```

## Database

```bash
ade db migrate
ade db history
ade db current
ade db stamp <rev>
ade db reset
```

## Storage

```bash
ade storage check
ade storage reset
```
