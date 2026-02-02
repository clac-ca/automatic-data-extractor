# Deployment guide

ADE ships as a single container image that can run any combination of services.

## Single container (all services)

The default image command runs all three services:

```bash
docker run --rm -p 8080:8080 -p 8000:8000 \
  -e ADE_DATABASE_URL=... \
  -e ADE_BLOB_CONNECTION_STRING=... \
  -e ADE_SECRET_KEY=... \
  ghcr.io/clac-ca/automatic-data-extractor:latest
```

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
