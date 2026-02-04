# Quickstart (Docker Compose)

This is the fastest way to run ADE locally with a Postgres database and Azurite
(Azure Blob emulator).

## Requirements

- Docker (with Docker Compose)
- Git

## Run

```bash
git clone https://github.com/clac-ca/automatic-data-extractor
cd automatic-data-extractor

# Start ADE + dependencies (migrations run automatically)

docker compose up --build
```

Note: the container entrypoint fixes /app/backend/data permissions (runs as root briefly, then drops to `adeuser`). The default compose bind-mounts `./backend/data`, so it will appear in your repo (gitignored) after first run.

Open the web UI at `http://localhost:8000`.

URL overrides:
- Update `ADE_INTERNAL_API_URL` if the API host changes (for split containers). Use the origin only (no `/api` path).
- Update `ADE_PUBLIC_WEB_URL` if the public web host or scheme changes.

## Stop and reset

```bash
# Stop containers

docker compose down

# Full reset (database + storage + ADE data)

docker compose down -v
```
