# System Architecture

## Purpose

Explain ADE components and how they interact.

## Main Components

- **API (`ade-api`)**
  - receives web/API requests
  - stores metadata (workspaces, documents, runs)
- **Worker (`ade-worker`)**
  - claims queued runs
  - executes processing in background
- **Database (`ade-db`)**
  - stores relational metadata and run state
- **Storage (`ade-storage`)**
  - stores uploaded files, outputs, and run logs in blob storage
- **Web (`ade-web`)**
  - user interface for upload, run management, and review

## Control Plane vs Data Plane

- **Control plane**: API + web operations (create runs, manage users, query status)
- **Data plane**: worker runtime (claim, execute, retry, persist artifacts)

## Data Flow (Simple)

1. user uploads document in web UI
2. API stores metadata and queues run
3. worker claims run and processes file
4. worker writes outputs and `events.ndjson`
5. API serves status/output to UI and clients

## Deployment Shapes

### Azure Container Apps (Default Production)

- one container app (`ade-app`)
- services: `ADE_SERVICES=api,worker,web`
- external ingress on port `8000`
- persistent mount at `/var/lib/ade/data`

### Azure Container Apps Split (Advanced)

- one app for `api,web`
- one app for `worker`
- use when you need independent API and worker scaling

### Self-Hosted Compose (Non-Default)

- `docker-compose.prod.yaml`: one app service (`api,worker,web`)
- `docker-compose.prod.split.yaml`: split app (`api,web`) and worker (`worker`)
