# Deployment guide

ADE ships as a single image that can run any combination of services.

For production, the recommended default topology is one container:
- `app` container running `api + worker + web`

Use `docker-compose.prod.yaml`:

```bash
docker compose -f docker-compose.prod.yaml up -d
```

Scale-out alternative (split app + worker):

```bash
docker compose -f docker-compose.prod.split.yaml up -d
```

Scale workers independently with the split file:

```bash
docker compose -f docker-compose.prod.split.yaml up -d --scale worker=3
```

Required values (via `.env` next to compose file or shell env):
- `ADE_PUBLIC_WEB_URL`
- `ADE_DATABASE_URL`
- `ADE_BLOB_CONTAINER`
- `ADE_SECRET_KEY`
- exactly one of `ADE_BLOB_ACCOUNT_URL` or `ADE_BLOB_CONNECTION_STRING` (not both)

Optional:
- `ADE_DOCKER_TAG` (defaults to `main` and selects `ghcr.io/clac-ca/automatic-data-extractor:<tag>`)

`ADE_DOCKER_TAG` is compose-only image selection (not ADE runtime config). Prefer setting it per deploy command, for example:

```bash
ADE_DOCKER_TAG=development docker compose -f docker-compose.prod.yaml up -d
```

Changing `ADE_DOCKER_TAG` does not alter already running containers until you recreate them (and typically pull the new tag first).

## Scaling playbook

Worker throughput controls:
- `ADE_WORKER_CONCURRENCY`
  - Max concurrent runs processed by one worker process in one container.
  - Default: `2`.
- Split mode replicas
  - `docker compose -f docker-compose.prod.split.yaml up -d --scale worker=<N>`
  - Increases total worker containers.

API throughput controls:
- `ADE_API_WORKERS`
  - Number of uvicorn worker processes per container.
  - Default: `1`.
- App replicas (horizontal API scaling)
  - Requires a load balancer/reverse proxy in front of multiple app containers.
  - In plain Docker Compose with a single published `:8000` port, scaling `app` directly is not the first option.

Recommended experiment order:
1. Start with single-container mode (`docker-compose.prod.yaml`).
2. Increase `ADE_WORKER_CONCURRENCY` gradually (for example `2 -> 4 -> 6`) while watching CPU, memory, and run latency.
3. If runs are CPU- or memory-heavy, prefer horizontal scaling earlier (split mode + more worker containers) rather than very high in-container concurrency.
4. Increase `ADE_API_WORKERS` only if API latency/CPU is a bottleneck.
5. Move to split mode when you need stronger isolation or higher worker capacity.
6. In split mode, keep per-container worker concurrency moderate (for example `2`-`4`) and scale worker containers horizontally.

Example tuning commands:

```bash
# Single-container: more worker slots + more API workers
ADE_WORKER_CONCURRENCY=4 ADE_API_WORKERS=2 \
docker compose -f docker-compose.prod.yaml up -d

# Split mode: moderate per-container concurrency + more worker replicas
ADE_WORKER_CONCURRENCY=2 \
docker compose -f docker-compose.prod.split.yaml up -d --scale worker=3
```

## Migrations

Apply database migrations before starting services:

```bash
ade db migrate
```

If you prefer to manage migrations manually (outside app startup), set
`ADE_DB_MIGRATE_ON_START=false` in your environment (or `.env`) and run the
migration command before launching containers.

Multi-replica guidance:
- Run migrations once as a one-off job, then start all replicas with `ADE_DB_MIGRATE_ON_START=false`.
- Or enable auto-migrate on a single "leader" instance and set `ADE_DB_MIGRATE_ON_START=false` on others.

Migrations are serialized via a Postgres advisory lock, so concurrent starts will wait
instead of racing. It's still best practice to designate a single migration runner in
production.

Example (one-off migration with the image):

```bash
docker run --rm \
  -e ADE_DATABASE_URL=postgresql+psycopg://user:pass@pg.example.com:5432/ade?sslmode=verify-full \
  ghcr.io/clac-ca/automatic-data-extractor:latest \
  ade db migrate
```
