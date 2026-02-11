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

- Use [Triage Playbook](../troubleshooting/triage-playbook.md).
- If you changed settings manually, compare with [Environment Variables](../reference/environment-variables.md).

## Next Step

- Production setup: [Production Bootstrap](production-bootstrap.md)
