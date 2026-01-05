---
title: Runs & Builds (Worker Queue Model)
---

# Runs & Builds (Worker Queue Model)

This document describes how ADE uses the database as the queue for builds and runs. The API and worker are **not** coupled at runtime; they only interact via SQL (and shared storage paths).

## Overview

- **API** creates `builds` and `runs` rows (status = `queued`).
- **Worker** claims rows, executes jobs, writes NDJSON event logs, and updates status.
- **Client** reads events and outputs via the API (which reads from disk + DB).

## Queue model (standard DB queue)

Each job type lives in its own table:

- `builds`: build jobs for configuration environments
- `runs`: run jobs for processing documents

The worker uses **atomic claim + lease** semantics:

1. **Claim**: update one `queued` row to `running/building`, set `claimed_by` and `claim_expires_at`.
2. **Heartbeat**: periodically extend `claim_expires_at` while the subprocess runs.
3. **Complete**: mark `succeeded/failed`, clear `claimed_by` and `claim_expires_at`.

If a lease expires, the worker either re-queues the job or fails it once max attempts are exceeded.

## Build → Run lifecycle

Runs are only claimed if their `build_id` is ready:

1. API resolves a build for a configuration (reuse or create).
2. API stores `build_id` on the run row when enqueuing.
3. Worker only claims runs with `build_id = NULL` **or** `build.status = ready`.

This guarantees that a run never starts against a missing or failed build.

## Logs & events

- Worker appends NDJSON to `events.ndjson` for both builds and runs.
- API exposes **events list**, **events stream (SSE)**, and **events download** endpoints by reading the same files.

## Failure semantics

- **Run timeout**: worker terminates the subprocess, marks the run failed, and releases the claim.
- **Build timeout**: worker marks the build failed and releases the claim.
- **Failed build**: queued runs referencing the build are marked failed with a clear error message.

## Scaling

- Multiple worker instances can run concurrently (processes or hosts).
- For SQL Server: row locking hints avoid contention.
- For SQLite: WAL + busy timeouts reduce lock errors (still best for low concurrency).
