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

Optional: copy `.env.example` to `.env` only when you need to override defaults.
Default local compose runs in development auth-bypass mode (`ADE_AUTH_DISABLED=true`).

Note: the container entrypoint fixes `/var/lib/ade/data` permissions (runs as root briefly, then drops to `adeuser`). The default compose uses a named volume, so runtime state stays out of the repo. If you prefer seeing files in `./backend/data`, switch the compose mount to a bind mount.

Open the web UI at `http://localhost:8000`.

URL overrides:
- Update `ADE_PUBLIC_WEB_URL` if the public web host or scheme changes.

## Stop and reset

```bash
# Stop containers

docker compose down

# Full reset (database + storage + ADE data)

docker compose down -v
```
