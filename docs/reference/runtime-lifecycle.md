# Runtime Lifecycle

## Purpose

Explain how runs move through states and how retries/leases work.

## Run States

- `queued`: waiting for worker pickup
- `running`: currently being processed by a worker
- `succeeded`: completed successfully
- `failed`: completed with error

## Run State Changes

- `queued -> running`
  - worker claims run
  - lease metadata is written
- `running -> succeeded`
  - worker stores success result
- `running -> queued`
  - failure happened but retries are still available
- `running -> failed`
  - no retries left or terminal failure condition

## Environment States

- `queued`
- `building`
- `ready`
- `failed`

An environment is the Python runtime + config-package install context used by the worker for runs.

## Lease and Retry Basics

- `ADE_WORKER_LEASE_SECONDS`: how long a claim is valid without renewal
- worker heartbeats extend active lease
- failed runs can be requeued with exponential backoff
- backoff controls:
  - `ADE_WORKER_BACKOFF_BASE_SECONDS`
  - `ADE_WORKER_BACKOFF_MAX_SECONDS`

## Artifact Paths

Run events are uploaded to blob storage at:

- `<workspace_id>/runs/<run_id>/logs/events.ndjson`

## Retention Controls

| Setting | Purpose |
| --- | --- |
| `ADE_WORKER_ENV_TTL_DAYS` | remove old environments |
| `ADE_WORKER_RUN_ARTIFACT_TTL_DAYS` | remove old run artifact folders |
| `ADE_DOCUMENT_CHANGES_RETENTION_DAYS` | remove old document change entries |
