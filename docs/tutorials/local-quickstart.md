# Local Quickstart

## Goal

Start ADE on your own machine, confirm it is working, and know how to stop or reset it.

## Before You Start

You need:

- Docker (with Docker Compose)
- Git

If these are not installed yet, install them first.

## Steps

1. Clone and start:

```bash
git clone https://github.com/clac-ca/automatic-data-extractor
cd automatic-data-extractor
docker compose up --build -d
```

1. Open the web app in a browser:

- `http://localhost:8000`

1. Optional status check:

```bash
docker compose ps
```

## Verify It Works

```bash
curl -sS http://localhost:8000/api/v1/health
curl -sS http://localhost:8000/api/v1/info
```

You should get JSON responses (not connection errors).

## Optional: Enable Built-In API Docs

API docs are opt-in. To enable ReDoc + Swagger UI locally:

```bash
echo "ADE_API_DOCS_ENABLED=true" >> .env
echo "ADE_API_DOCS_ACCESS_MODE=public" >> .env
docker compose up --build -d
```

Use `ADE_API_DOCS_ACCESS_MODE=authenticated` (default) to require sign-in.
After changing `.env`, always rerun `docker compose up --build -d` so API/web
containers restart with the new values.

Then open:

- `http://localhost:8000/api` (ReDoc)
- `http://localhost:8000/api/swagger` (Swagger UI)
- `http://localhost:8000/api/openapi.json` (OpenAPI JSON)

## Stop or Reset

Stop services:

```bash
docker compose down
```

Reset all local data (database, blob emulator, ADE runtime data):

```bash
docker compose down -v
```

## If Something Fails

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `404` on `/api` or `/api/swagger` | docs are disabled | set `ADE_API_DOCS_ENABLED=true` and restart containers |
| `/api` shows the SPA page instead of ReDoc | stale web container/nginx config | rerun `docker compose up --build -d` |
| `403` with `csrf_failed` in Swagger "Try it out" | session auth without CSRF cookie/header | sign in first or use `X-API-Key` auth in Swagger |
| Wrong request target in Swagger | incorrect base URL/proxy origin | verify `ADE_PUBLIC_WEB_URL` and open docs from web port `:8000` |

- Use [Triage Playbook](../troubleshooting/triage-playbook.md).
- If you changed settings manually, compare with [Environment Variables](../reference/environment-variables.md).

## Next Step

- Production setup: [Production Bootstrap](production-bootstrap.md)
