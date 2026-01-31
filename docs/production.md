# Production: API + Worker + Web (single image)

Standard deployment uses one image that can run the API, worker, and web UI
(via nginx). You can run them together in one container or split them across
containers using the same image.

## Build the image

```bash
docker build -t ade-app:local .
```

## Run with Compose (prod-like locally)

```bash
cp .env.example .env
ADE_IMAGE=ade-app:local docker compose -f docker-compose.prod.yaml up
# or split services
ADE_IMAGE=ade-app:local docker compose -f docker-compose.prod.split.yaml up
```

The split compose file runs `ade api start`, `ade worker start`, and `ade web serve`
as separate containers. The single-container file runs `ade start`.
Use `ade start --services api,web` (or `ADE_START_SERVICES=api,web`) if you want a
single container with a subset of services.

You must provide external Postgres + Storage (set `ADE_DATABASE_URL`,
`ADE_DATABASE_AUTH_MODE`, `ADE_BLOB_CONTAINER`, and one of
`ADE_BLOB_ACCOUNT_URL` (managed identity) or `ADE_BLOB_CONNECTION_STRING`
(connection string) in `.env`). Ensure the database named in
`ADE_DATABASE_URL` already exists before starting the containers, and that the
blob container is provisioned.

## Run with docker run

All-in-one:

```bash
docker run --rm -d --name ade \
  --env-file .env \
  -p 8000:8000 \
  ade-app:local ade start
```

Split containers (shared network so the web proxy can reach the API):

```bash
docker network create ade-net

docker run --rm -d --name ade-api --network ade-net --env-file .env \
  ade-app:local ade api start

docker run --rm -d --name ade-worker --network ade-net --env-file .env \
  ade-app:local ade worker start

docker run --rm -d --name ade-web --network ade-net -p 8000:8000 \
  -e ADE_WEB_PROXY_TARGET=http://ade-api:8000 \
  ade-app:local ade web serve
```

## CLI inside the container

You can run commands in a container shell:

```bash
docker run --rm -it ade-app:local /bin/bash
ade --help
ade-api --help
ade-worker --help
```

## Serving the React frontend in production

`ade start` and `ade web serve` run nginx inside the image and serve the built
SPA, proxying `/api` to the API service. The API remains API-only.
