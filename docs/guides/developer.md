# Developer guide

## Repo layout

```
backend/
  ade-api/       # FastAPI backend
  ade-worker/    # Background worker
  ade-db/        # Shared DB schema + migrations
  ade-storage/   # Shared blob storage helpers
frontend/
  ade-web/       # React/Vite SPA
```

## Common commands

```bash
# Start everything (dev)
ade dev

# Start everything (prod-style)
ade start

# Per-service
ade api dev
ade worker start
ade web dev

# Tests
ade test
ade api test
ade worker test
ade web test

# OpenAPI types for frontend
ade api types
```

## Migrations

Apply migrations with:

```bash
ade db migrate
```

## Where to make changes

- API routes and business logic: `backend/ade-api/src/ade_api/`
- Worker runtime: `backend/ade-worker/src/ade_worker/`
- Database models and migrations: `backend/ade-db/src/ade_db/`
- Blob storage helpers: `backend/ade-storage/src/ade_storage/`
- Frontend UI: `frontend/ade-web/src/`
