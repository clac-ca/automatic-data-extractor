# Runs & Environments (Worker Queue Model)

This document describes how ADE uses the database as a queue for **runs** and
worker-owned **environments**. The API and worker communicate only via SQL and
shared storage paths.

---

## Core rules

* Runs are the **only queued jobs** created by the API.
* Environments are **worker-owned cache rows** keyed by configuration + dependency digest.
* Runs are only claimed when a matching environment is `ready`.
* Leases (`claim_expires_at`) protect long-running work and allow recovery.

---

## Lifecycle (happy path)

1. API inserts a `runs` row (`status=queued`).
2. Worker ensures a matching `environments` row exists (`status=queued`).
3. Worker claims the environment (`status=building`) and provisions the venv.
4. Environment becomes `ready`.
5. Worker claims the run (`status=running`) and executes the engine.
6. Worker marks the run `succeeded` or `failed`.

---

## Crash recovery

* If a worker crashes mid-environment build, the lease expires and another
  worker can requeue and rebuild.
* If a worker crashes mid-run, the run lease expires and the run is retried or
  failed based on attempt counts.

---

## No in-place rebuilds

Dependency changes create a **new** environment (new `deps_digest`). In-flight
runs keep using their current environment; old environments are removed only
by GC when they are cold and unreferenced.
