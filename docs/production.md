# Production: API + Worker + Web (single image)

Standard deployment uses one image that can run the API, worker, and web UI
(via nginx). Services run as separate containers using the same image.

## Build the image

```bash
docker build -t ade-app:local .
```

## Run with Compose (prod-like locally)

```bash
cp .env.example .env
ADE_IMAGE=ade-app:local docker compose -f docker-compose.prod.yaml up
```

The compose file runs `ade-api start`, `ade-worker start`, and nginx (via
`/usr/local/bin/ade-web-entrypoint`) as separate containers.

Before starting API/worker services, apply migrations explicitly:

```bash
docker run --rm --env-file .env ade-app:local ade-api migrate
```

You must provide external Postgres + Storage (set `ADE_DATABASE_URL`,
`ADE_DATABASE_AUTH_MODE`, `ADE_BLOB_CONTAINER`, and one of
`ADE_BLOB_ACCOUNT_URL` (managed identity) or `ADE_BLOB_CONNECTION_STRING`
(connection string) in `.env`). Ensure the database named in
`ADE_DATABASE_URL` already exists before starting the containers, and that the
blob container is provisioned.

Role-specific environment variables:

- API/worker: `ADE_DATABASE_URL`, `ADE_SECRET_KEY`, and the blob settings above.
- Web: `ADE_WEB_PROXY_TARGET` (optional; defaults to `http://api:8000`).

## Run with docker run

Split containers (shared network so the web proxy can reach the API):

```bash
docker network create ade-net

docker run --rm --name ade-migrate --network ade-net --env-file .env \
  ade-app:local ade-api migrate

docker run --rm -d --name ade-api --network ade-net --env-file .env \
  ade-app:local ade-api start

docker run --rm -d --name ade-worker --network ade-net --env-file .env \
  ade-app:local ade-worker start

docker run --rm -d --name ade-web --network ade-net -p 8080:8080 \
  -e ADE_WEB_PROXY_TARGET=http://ade-api:8000 \
  ade-app:local /usr/local/bin/ade-web-entrypoint
```

## CLI inside the container

You can run commands in a container shell:

```bash
docker run --rm -it ade-app:local /bin/bash
ade-api --help
ade-worker --help
```

## Serving the React frontend in production

`/usr/local/bin/ade-web-entrypoint` runs nginx inside the image and serves the
built SPA, proxying `/api` to the API service. The API remains API-only.
