# Docs/code parity — job runtime (queue, deps, hooks)

Owner: jkropp
Status: active (implementation)
Created: 2025-11-03T20:20:00Z
Last reviewed: 2025-11-03T23:55:00Z

---

## Objective

Align the **developer docs** and the **runtime** for job submission/processing, per-config dependency install, lifecycle hooks, and network policy. When behavior diverges, either implement the documented contract or update the docs—favoring implementation where feasible.

---

## Repository reconnaissance

* `backend/app/features/jobs/router.py` responds with **201** and returns a completed `JobRecord`; there is no async queue or `202 Accepted` path today, and HTTP headers/body lack a `Location` pointer or `{ status: "queued" }` payload.
* `backend/app/features/jobs/service.py` executes jobs inline by calling `JobOrchestrator.run(...)` after marking the row `running`; saturation/back-pressure are absent.
* `backend/app/features/configs/service.py::activate_version` only updates workspace state—no dependency install, `on_activate` hook execution, or environment metadata persistence.
* `backend/app/features/jobs/orchestrator.py` always shells out with `sys.executable`; it never consults a per-config venv and always injects `config/vendor` onto `PYTHONPATH`.
* `backend/app/features/jobs/runtime/pipeline.py` enforces hook ordering and deep-copies artifacts, but `on_activate` hooks are never invoked because activation skips runtime code, so the documented deps-first-then-hooks activation contract is unmet.
* `backend/tests/api/jobs/test_jobs_router.py` asserts the current synchronous flow (201 + succeeded status); docs/tests will need wholesale updates for the queued contract.
* Developer docs still reference `engine.defaults.allow_net` and per-job `vendor/` installs even though runtime uses `runtime_network_access` and never runs `pip`.

---

## Scope

**In scope (P0 unless marked):**

* Job queue with bounded workers, `202 Accepted` semantics, `429` back‑pressure, status polling, and `/retry`.
* Activation‑time dependency install (one **venv per config version**), job execution using that venv, and audit of installed packages (deps installed **before** hooks, with hooks running inside the venv).
* Lifecycle hook behavior parity (`on_activate`, `on_job_start`, `on_after_extract`, `after_mapping`, `after_transform`, `after_validate`, `on_job_end`) with read‑only artifact snapshots and annotation returns.
* Network policy: runtime network **off by default**, activation network **allowed for installs**; flag to permit runtime network when explicitly enabled.
* Docs updates to match runtime (or vice versa) for queue, deps, hooks, and logs.

**Out of scope / defer (P1 unless noted):**

* Digest‑keyed shared venv cache (reuse across configs with identical `requirements.txt`).
* Offline installs (wheelhouse / build cache).
* Job cancellation and pause/resume.
* UI flows (except where needed to expose new states).

---

## Current gaps (audit)

* **Queue semantics** (`backend/app/features/jobs/router.py`, `service.py`): API currently returns `201` and blocks while the worker runs; docs promise a `202` queue, worker pool, and `429` back-pressure.
* **Dependency handling** (`backend/app/features/configs/service.py`): Docs describe `requirements.txt` installs during activation; runtime never creates per-version environments.
* **Hooks** (`backend/app/features/jobs/runtime/pipeline.py`): Stage hooks largely match docs, but `on_activate` is never executed and activation failures never gate publishing.
* **Network policy** (`backend/app/features/jobs/worker.py`): Runtime disables sockets based on env, yet activation-time installs are unspecified and docs reference `allow_net` instead of `runtime_network_access`.
* **Logs & metadata** (`backend/app/features/jobs/storage.py` + docs): Runtime emits structured `events.ndjson`/`run-request.json`, while docs assume plaintext logs and omit environment metadata.

---

## Deliverables & acceptance

### D1 — Queued job runner (P0)

**Deliver:** Introduce an async job manager (e.g., `backend/app/features/jobs/manager.py`) that owns a bounded queue and worker tasks running within a **single process/pod**. `JobsService.submit_job` should enqueue work instead of executing inline, `POST /jobs` must return `202 Accepted` with a `Location` header plus `{ job_id, status: "queued" }`, and saturation should produce `429 Too Many Requests` with a `Retry-After` hint. Extend `GET /jobs/{id}` to surface queue timestamps, attempts, retry lineage, and heartbeat data so the manager can rehydrate queued/running jobs on restart (stale "running" jobs fall back to `queued`). `POST /jobs/{id}/retry` should enqueue a fresh attempt linked to the prior run. Worker startup should rehydrate queue state from persistence.

**Acceptance:**

* [x] `POST /jobs` returns `202 Accepted` with `Location: /api/v1/.../jobs/{id}` and body `{ job_id, status: "queued" }`.
* [x] Under configured saturation, the service returns `429 Too Many Requests` with `Retry-After: <seconds>` and queue metadata (e.g., `{ queue_size, max_concurrency }`).
* [x] `GET /jobs/{id}` exposes `queued_at`, `started_at`, `completed_at`, and attempt counters reflecting `enqueue → start → exit/error` transitions.
* [x] Worker startup rehydrates queued jobs from persistence; jobs lacking a heartbeat for >N seconds are marked back to `queued`.
* [x] No synchronous execution path remains; service tests guard against inline worker invocation.
* [x] Worker events include structured `enqueue`, `start`, `exit`, `retry`, `error` records emitted to storage using the `{ ts, event, job_id, attempt, state, duration_ms?, detail? }` schema.

### D2 — Activation-time deps & venv per config version (P0)

**Deliver:** During `ConfigsService.activate_version` (and publish paths that auto-activate), detect `requirements.txt`, create a virtualenv under `/var/lib/ade/venvs/<config_version_id>/`, install dependencies using hardened `pip install -r` flags (`--no-input --disable-pip-version-check`), then run `pip freeze` into `activation/packages.txt`. Execute `on_activate` hooks **after dependencies install** using the venv interpreter, capture hook diagnostics, and persist metadata (venv path, package list, install logs, hook annotations) under config storage (e.g., `/configs/<version>/activation/{log.txt, packages.txt, venv_path.json}`). Update `JobOrchestrator` to launch workers with the venv interpreter and surface `engine.environment.packages` through job/activation metadata. Ensure installs run once per version, reuse the same venv, and defer GC/disk reclamation (one venv per config version in v1).

**Acceptance:**

* [x] Activation fails fast on dependency install errors with actionable diagnostics and leaves the version inactive.
* [x] `activation/packages.txt` exists, is referenced from job detail/artifact metadata, and reflects the frozen environment.
* [x] Worker uses the venv interpreter (`sys.executable` recorded in `run-request.json`); per-job vendor installs are removed.
* [x] `on_activate` hooks run after dependencies inside the venv; failures block activation and persist diagnostics.

### D3 — Hook lifecycle parity (P0)

**Deliver:** Execute manifest `on_activate` hooks during activation using the stored package, aborting on failure. Confirm runtime hook execution order matches docs, tighten artifact immutability guarantees (deep copies or frozen views), ensure hook annotations share a consistent schema (e.g., `{stage, hook, annotated_at, detail?}`), and respect hook enable flags everywhere. Persist hook annotations alongside job artifacts and activation metadata.

**Acceptance:**

* [x] `on_activate` runs after dependency installs within the venv; failure blocks activation and records diagnostics.
* [ ] Runtime hook order matches `on_job_start → on_after_extract → after_mapping → after_transform → after_validate → on_job_end` exactly.
* [ ] Hook return dicts appear in `artifact.annotations[]` with `{stage, hook, annotated_at}` (and optional `detail`).
* [ ] Artifacts remain read-only to hooks; tests enforce immutability.
* [ ] Hook enable/disable flags honored consistently across activation and runtime.

### D4 — Network policy enforcement (P0)

**Deliver:** Allow outbound network during activation installs, then enforce socket blocking in the worker when `runtime_network_access` is false. Accept legacy `engine.defaults.allow_net` manifest fields for one release window, map them to `runtime_network_access`, and emit a deprecation diagnostic during validation. Propagate manifest/env toggles cleanly through activation and runtime, expose overrides in metadata for auditing, and keep runtime default offline.

**Acceptance:**

* [ ] Worker socket creation fails by default and succeeds only when `runtime_network_access` (or legacy `allow_net`) enables it.
* [ ] Validation maps `allow_net` to `runtime_network_access` with a warning diagnostic.
* [ ] Runtime metadata exposes the resolved network access flag for audit.

### D5 — Documentation parity & examples (P0)

**Deliver:** Refresh developer docs to cover the queued API (including headers/bodies for 202/429), activation-time dependency flow with venv storage paths, hook lifecycle (including `on_activate` ordering), network policy defaults, structured logs/events schema, and manifest validation changes (e.g., `allow_net` deprecation, manifest version bump). Provide an example manifest showing `requirements.txt` plus `engine.defaults.runtime_network_access`.

**Acceptance:**

* [ ] Docs show request/response examples with headers (`Location`, `Retry-After`) and polling flow diagrams.
* [ ] Config packages doc shows activation flow diagram, venv storage path, and hook ordering.
* [ ] Glossary aligns hook stages and network policy names; schemas/manifests bumped as needed with migration guidance.

---

## Implementation plan (checklist)

### Phase A — Queue & API

* [x] Add an async `JobQueueManager` with bounded workers, metrics, and graceful shutdown hooks (new module under `backend/app/features/jobs/`).
* [x] Update `JobsService.submit_job` to enqueue and return immediately; propagate saturation via `JobSubmissionError` so the router emits `429` + `Retry-After`.
* [x] Adjust `backend/app/features/jobs/router.py` + schemas to return `202`, include `Location`, and expose queue timestamps/links.
* [x] Extend persistence (`models.py`, `repository.py`, `schemas.py`) to track queue timestamps, attempts, retry lineage, and expose `events.ndjson` URIs.
* [x] Persist worker heartbeats / last_seen to support rehydration and stale-run detection on restart.
* [x] Ensure worker lifecycle appends `enqueue`/`start`/`finish`/`retry`/`error` events to storage with durations.

### Phase B — Activation-time venv (deps first, then `on_activate`)

* [x] Extend config storage metadata to track activation environment (venv path, installed packages, install log, timestamps).
* [x] Run activation pipeline: detect `requirements.txt`, build virtualenv, install dependencies (`pip install -r` with hardened flags), capture `pip freeze`, snapshot environment metadata, then execute `on_activate` hooks using the venv interpreter.
* [x] Update `JobOrchestrator` to use the venv interpreter/site-packages; remove vendor-based PYTHONPATH injection and call out no GC (one venv per config version).
* [ ] Provide health checks + reactivation paths when venv creation fails, surfacing errors through API responses/logs and leaving the version inactive.

### Phase C — Hooks

* [ ] Wire activation hook execution into `ConfigsService.activate_version`, sharing manifest/context and persisting structured results/errors.
* [ ] Harden runtime hook pipeline to enforce ordering, immutability, and annotation schema consistency.
* [ ] Expand tests for activation + runtime hooks (services + worker) covering success/failure/annotation cases.

### Phase D — Network policy

* [ ] Audit code/docs for lingering `allow_net` references; migrate to `runtime_network_access` nomenclature.
* [ ] Ensure activation installs run with temporary network access and capture audit logs of dependency downloads; runtime remains offline unless explicitly enabled.
* [ ] Reinforce worker socket patching + env propagation; add tests that simulate blocked/allowed connections and cover legacy `allow_net` mapping.
* [ ] Surface manifest/global overrides in API responses for observability.

### Phase E — Docs parity

* [x] Update: `02-job-orchestration.md` (queued lifecycle, polling/retry examples, structured events/logs).
* [x] Update: `01-config-packages.md` (activation flow, venv storage, `on_activate`, environment metadata).
* [x] Update: `05-pass-transform-values.md` + `12-glossary.md` for runtime network terminology and hook lifecycle definitions.
* [ ] Refresh schemas/examples to include `runtime_network_access`, environment metadata, event schema, and manifest snippets with `requirements.txt` plus legacy `allow_net` deprecation note.

---

### Near-term vertical slices (next three PRs)

1. **Queue skeleton & 202/429 contract**
   * Add `JobQueueManager` (bounded asyncio queue; N workers; single-process assumption) and flip `POST /jobs` to enqueue + `202` with `Location` header/body payload.
   * Emit `429` with `Retry-After` when saturated; persist queue timestamps/events; add feature flag for rollback.
   * Update API tests in `backend/tests/api/jobs/` for the new contract.
2. **Activation pipeline: venv + deps + `on_activate`**
   * Extend `ConfigsService.activate_version` to create the venv, install deps (hardened pip flags), freeze, and run hooks within the venv.
   * Persist activation metadata under config storage; orchestrator uses venv interpreter; remove vendor PYTHONPATH injection.
   * Add service tests covering install failure and hook failure gating activation.
3. **Runtime network gating & `allow_net` deprecation**
   * Enforce `runtime_network_access` in the worker (socket patch + tests) and accept legacy `allow_net` with warning diagnostics.
   * Surface runtime network flag in job/artifact metadata; document the behavior.
   * Prep docs for manifest/schema updates in the follow-up docs PR.

---

### Day-one checklist

* [ ] Draft ADR at `docs/developers/design-decisions/dd-????-queued-runner-and-activation-env.md` capturing queue semantics (202/429, single-node, rehydration), deps-before-hooks activation, per-version venv, and runtime network policy default.
* [ ] Create stubs for `backend/app/features/jobs/manager.py`, `backend/app/features/jobs/models.py` (state enums/heartbeat), and `backend/app/features/configs/activation_env.py` (venv helpers).
* [ ] Flip router/service to return `202` + `Location` behind `ADE_QUEUE_ENABLED` flag; keep legacy tests as `_legacy` fixtures for comparison.
* [ ] Add manifest validation mapping `engine.defaults.allow_net` → `engine.defaults.runtime_network_access` with a deprecation diagnostic.

---

## Testing & validation plan

* Expand backend API tests for queued submission, polling, retry semantics, `Retry-After`, and artifact retrieval under the queued flow.
* Add service-level tests for activation env install success/failure, hook execution (deps-before-hooks), and metadata persistence.
* Introduce worker-level tests (possibly invoking subprocesses) to validate network blocking, venv interpreter selection, heartbeat recovery, and hook immutability.
* Ensure docs updates reference generated schemas/examples; consider smoke checks if available.

---

## Open questions / follow-ups

* How should the queue manager lifecycle integrate with FastAPI startup/shutdown (lifespan vs background task)?
* Single-node guarantee in v1: do we need explicit guardrails/config to prevent multi-pod workers, or is documentation sufficient?
* How aggressive should heartbeat-based requeue timing be, and where do we persist heartbeat timestamps?
* Do we need migrations to store venv metadata, activation diagnostics, heartbeat, or retry lineage beyond existing columns?
* Should runtime network overrides be configurable per workspace/job beyond the manifest default (e.g., admin override flag)?

---

## Milestones

* **M1 (P0):** Queue/API + events + tests passing.
* **M2 (P0):** Activation‑time venv + worker venv launch + recorded packages.
* **M3 (P0):** Hook lifecycle parity shipped.
* **M4 (P0):** Runtime network policy enforced and documented.
* **M5 (P0):** Docs updated and reviewed.

---

## Risks & mitigations

* **Queue starvation / unbounded growth:** enforce queue size + `429`; metrics + alerts; heartbeat-driven requeue on restart.
* **Dependency install flakiness:** pin `pip` flags; timeout + retries; clear diagnostics.
* **Hook errors blocking activation:** surface actionable errors; safe no‑ops for non‑activation hooks.
* **Regressions in existing synchronous flows:** feature flag the queue path; migrate gradually.

---

## Telemetry (nice to have)

* Queue depth, wait time, run time, success/failure rates, retry counts.
* Activation install duration and failure reasons.
* Hook timing and error counts.
* Network policy violations prevented at runtime.

---

## Notes

* 2025-11-03T20:32:00Z • Decision: **no per‑job site‑packages**; use **one venv per config version** at activation.
* 2025-11-03T20:34:00Z • Naming: replace `allow_net` with `runtime_network_access` across manifest, worker, and docs; accept legacy field for one release with deprecation diagnostic.
* 2025-11-03T20:36:00Z • Docs to update: `01-config-packages.md`, `02-job-orchestration.md`, `12-glossary.md`.
* 2025-11-03T21:30:00Z • Event schema: `{ ts, event, job_id, attempt, state, duration_ms?, detail? }`; events include `enqueue`, `start`, `exit`, `retry`, `error`.
* 2025-11-03T21:31:00Z • Manifest/schema: bump manifest minor version if we add `engine.environment` or rename fields; validation must emit actionable guidance.
* 2025-11-03T22:40:00Z • Phase A shipped: queue manager, 202/429 API, retry route, heartbeats, rehydration, and normalized events are live behind the default path; saturation no longer persists failed rows.
* 2025-11-03T22:42:00Z • Next up: start Phase B by adding `backend/app/features/configs/activation_env.py`, wiring `ConfigsService.activate_version` to create/use per-version venvs (deps → `on_activate`), and pointing the orchestrator at the venv interpreter; follow with network policy + docs (Phases D/E).
