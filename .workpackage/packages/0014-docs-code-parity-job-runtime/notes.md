# Docs/code parity — job runtime (queue, deps, hooks)

Owner: jkropp
Status: active
Created: 2025-11-03T20:20:00Z

---

## Objective

Align the **developer docs** and the **runtime** for job submission/processing, per-config dependency install, lifecycle hooks, and network policy. When behavior diverges, either implement the documented contract or update the docs—favoring implementation where feasible.

---

## Scope

**In scope (P0 unless marked):**

* Job queue with bounded workers, `202 Accepted` semantics, `429` back‑pressure, status polling, and `/retry`.
* Activation‑time dependency install (one **venv per config version**), job execution using that venv, and audit of installed packages.
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

* **Queue semantics**: API returns `201` and runs work inline; docs describe queued `202`, worker pool, and `429` back‑pressure.
* **Dependency handling**: Docs mention `requirements.txt` installs; runtime does not run `pip` nor isolate per config version.
* **Hooks**: Docs describe gating `on_activate` and stage‑specific hook ordering; runtime only partially aligns.
* **Network policy**: Docs imply network gating; runtime needs explicit enforcement for activation vs runtime.
* **Logs**: Docs mention simple logs; runtime emits structured `events.ndjson`/`run-request.json`—docs must reflect this.

---

## Deliverables & acceptance

### D1 — Queued job runner (P0)

**Deliver:** Background queue with bounded concurrency; `POST /jobs` returns `202` + job resource; saturation returns `429`. `GET /jobs/{id}` exposes state machine (`queued → running → succeeded|failed`) and timestamps. `POST /jobs/{id}/retry` enqueues a new attempt with link to prior.

**Acceptance:**

* [ ] Load test proves `429` when queue is full; no inline execution on submit.
* [ ] Integration tests cover submit → poll → output/artifact download; retry path updates `attempt` and links history.
* [ ] Structured events (`events.ndjson`) include `enqueue`, `start`, `exit`, `retry`, `error`, with durations.

### D2 — Activation‑time deps & venv per config version (P0)

**Deliver:** On config **activation**, if `requirements.txt` exists, create venv at `/var/lib/ade/venvs/<config_version_id>/` and `pip install -r`. Persist venv path and installed packages. Jobs run the worker using that venv’s Python if present; otherwise base interpreter.

**Acceptance:**

* [ ] Activation fails with diagnostic on `pip` error; jobs are not runnable until activation succeeds.
* [ ] Artifact or job metadata records `engine.environment.packages` (name+version) on first run or via activation snapshot.
* [ ] No per‑job installs; repeated jobs reuse the same venv.

### D3 — Hook lifecycle parity (P0)

**Deliver:** Enforce documented hook groups and order. `on_activate` runs synchronously during activation and blocks on error. Stage hooks receive a **deep‑copied, read‑only** artifact snapshot and may return a small dict to append to `artifact.annotations[]` with `stage`, `hook`, and timestamp.

**Acceptance:**

* [ ] Tests show each hook executes at the correct point with read‑only artifact and that returned annotations are persisted.
* [ ] Activation fails if any `on_activate` hook errors; other stages do not abort the job unless they raise.
* [ ] Hook enable flags in manifest respected.

### D4 — Network policy enforcement (P0)

**Deliver:** Network **allowed during activation** for `pip` by default; **blocked during job runtime** unless manifest `engine.defaults.runtime_network_access: true`. Replace ambiguous `allow_net` with `runtime_network_access` in code/docs.

**Acceptance:**

* [ ] Worker socket creation blocked when `runtime_network_access` is false (tests verify).
* [ ] Activation installs work under default policy; runtime remains offline unless opt‑in.

### D5 — Documentation parity & examples (P0)

**Deliver:** Update developer docs to reflect: queued runner/API; activation‑time deps with venv path; hook lifecycle; network policy; structured logs & request artifacts. Provide a minimal example manifest with `runtime_network_access` and `requirements.txt`.

**Acceptance:**

* [ ] Docs match endpoints, states, and file paths produced by the system.
* [ ] Quickstart: activate config with deps → submit job → inspect artifact/output → view events.

---

## Implementation plan (checklist)

### Phase A — Queue & API

* [ ] Add `JobState` machine and persisted fields: `queued_at`, `started_at`, `completed_at`, `attempt`, `error_message`.
* [ ] Introduce in‑process worker pool (configurable size); pluggable queue interface for future external broker.
* [ ] `POST /jobs` → create record, enqueue, return `202` with `Location`.
* [ ] Saturation policy → `429 Too Many Requests` with `Retry-After`.
* [ ] `GET /jobs/{id}` → json with state and links (`/artifact`, `/output`, `/logs`).
* [ ] `POST /jobs/{id}/retry` → idempotent retry creation, links attempts.
* [ ] Emit `events.ndjson` entries for enqueue/start/exit/retry/error.

### Phase B — Activation‑time venv

* [ ] On activation: if `requirements.txt` present → `python -m venv /var/lib/ade/venvs/<config_version_id>` then `pip install -r`.
* [ ] Persist `venv_path` and list of installed packages.
* [ ] Worker launcher selects venv Python when present.
* [ ] Add health check: verify venv integrity (python exists, import of installed packages succeeds).
* [ ] Migrate away from any “vendor/” concept; **no per‑job site‑packages**.
* [ ] Clear diagnostics on failure; re‑activation reattempts install.

### Phase C — Hooks

* [ ] Guarantee hook groups/order; respect `enabled`.
* [ ] Run `on_activate` with failure gating.
* [ ] Pass deep‑copied artifact snapshot to stage hooks; append returned dicts to `artifact.annotations[]` with ISO timestamp.
* [ ] Tests for each stage ordering and error handling.

### Phase D — Network policy

* [ ] Rename `allow_net` → `runtime_network_access` (manifest default `false`).
* [ ] Enforce socket denial in worker when `false`.
* [ ] Allow activation network for `pip`; document separation.
* [ ] Tests: activation installs OK; runtime detectors/validators fail on net unless opt‑in.

### Phase E — Docs parity

* [ ] Update: `02-job-orchestration.md` (queue, 202/429, polling, retry, logs).
* [ ] Update: `01-config-packages.md` (activation installs, venv path, artifact fields).
* [ ] Update: `12-glossary.md` (hook lifecycle, network policy).
* [ ] Add: minimal example manifest snippet with `engine.defaults.runtime_network_access` and `requirements.txt`.

---

## Milestones

* **M1 (P0):** Queue/API + events + tests passing.
* **M2 (P0):** Activation‑time venv + worker venv launch + recorded packages.
* **M3 (P0):** Hook lifecycle parity shipped.
* **M4 (P0):** Runtime network policy enforced and documented.
* **M5 (P0):** Docs updated and reviewed.

---

## Risks & mitigations

* **Queue starvation / unbounded growth:** enforce queue size + `429`; metrics + alerts.
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
* 2025-11-03T20:34:00Z • Naming: replace `allow_net` with `runtime_network_access` across manifest, worker, and docs.
* 2025-11-03T20:36:00Z • Docs to update: `01-config-packages.md`, `02-job-orchestration.md`, `12-glossary.md`.