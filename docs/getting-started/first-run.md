# First run (local dev)

## 1) Configure environment

Create `.env` in the repo root (or set variables in your shell). At minimum:

```env
ADE_DATABASE_URL=postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable
ADE_BLOB_CONNECTION_STRING=UseDevelopmentStorage=true
ADE_BLOB_CONTAINER=ade
ADE_SECRET_KEY=change-me-to-a-long-random-value
```

## 2) Run migrations

If you use `ade dev` or `ade start`, migrations run automatically by default.
To skip auto-migrate, set `ADE_DB_MIGRATE_ON_START=false` or pass `--no-migrate`.

```bash
ade db migrate
```

## 3) Start services

```bash
# All services (API + worker + web)
ade dev

# Or start a single service
ade api dev
ade worker start
ade web dev
```
