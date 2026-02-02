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

# Start dependencies

docker compose up --build -d postgres azurite azurite-init

# Apply database migrations (first run only)

docker compose run --rm api ade db migrate

# Start ADE services

docker compose up -d api worker web
```

Open the web UI at `http://localhost:8080`.

## Stop and reset

```bash
# Stop containers

docker compose down

# Full reset (database + storage + ADE data)

docker compose down -v
```
