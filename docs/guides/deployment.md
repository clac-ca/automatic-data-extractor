# Deployment guide

ADE ships as a single container image that can run any combination of services.

## Single container (all services)

The default image command runs all three services:

```bash
docker run --rm -p 8000:8000 \
  -e ADE_DATABASE_URL=... \
  -e ADE_BLOB_CONNECTION_STRING=... \
  -e ADE_SECRET_KEY=... \
  ghcr.io/clac-ca/automatic-data-extractor:latest
```

Note: ports are fixed (API `8001`, web `8000`). Use Docker port mappings to
expose different external ports. nginx proxies `/api` to `ADE_INTERNAL_API_URL`
which must be an origin (no `/api` path).

For split containers, set `ADE_INTERNAL_API_URL=http://api:8001` in the web
container.

## Split containers (recommended at scale)

Use `ADE_SERVICES` to control which services run in a container:

- `ADE_SERVICES=api` for API only
- `ADE_SERVICES=worker` for worker only
- `ADE_SERVICES=web` for web only
- `ADE_SERVICES=api,web` for API + web together

The repo includes Docker Compose examples:

- `docker-compose.yaml` (local development)
- `docker-compose.prod.yaml` (split services)

## Migrations

Apply database migrations before starting services:

```bash
ade db migrate
```

If you prefer to manage migrations manually (outside app startup), set
`ADE_DB_MIGRATE_ON_START=false` in your environment (or `.env`) and run the
migration command before launching containers.

Example (one-off migration with the image):

```bash
docker run --rm \
  -e ADE_DATABASE_URL=postgresql+psycopg://user:pass@pg.example.com:5432/ade?sslmode=verify-full \
  ghcr.io/clac-ca/automatic-data-extractor:latest \
  ade db migrate
```
