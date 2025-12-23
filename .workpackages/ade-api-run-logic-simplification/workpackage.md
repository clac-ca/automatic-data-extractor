> **Agent Instructions (read first)**
>
> * Treat this work package as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as tasks are completed, and add new items when new work is discovered.
> * Prefer small, incremental commits aligned to checklist items.
> * If the plan must change, **update this document first**, then update the code.

---

## What we are fundamentally doing

We are simplifying ADE’s run/build orchestration so it is correct under concurrency and easy to explain:

* A **run** is one concrete execution of the engine for one document.
* A **build** is a reusable prepared environment for a specific configuration fingerprint.
* The API uses a simple, configurable **queue** so runs start at a controlled rate (1000 submissions do not mean 1000 concurrent executions).
* Build creation and execution are **deduplicated**, so 1000 runs do not trigger 1000 builds.
* Timeout handling is simple and does not require a separate scheduler service.
* The design must work on **SQLite, MSSQL, and Postgres**.
* We do not need backwards compatibility; schema and API changes can be in-place.

---

## Work Package Checklist

* [x] Finalize “Pass 1” behavior decisions (statuses, limits scope, error codes)
* [ ] Update schema in `apps/ade-api/migrations/versions/0001_initial_schema.py` (runs/builds invariants, remove retry fields)
* [ ] Implement build dedupe by `(configuration_id, fingerprint)` with get-or-create logic
* [ ] Implement a simple run queue (enforce `ADE_MAX_CONCURRENCY` / `ADE_QUEUE_SIZE`)
* [ ] Implement timeouts + stuck-state cleanup (no external scheduler)
* [ ] Update OpenAPI/TS types + frontend assumptions for new run/build semantics
* [ ] Update docs (runs semantics, queue behavior, retry wording)

> **Agent note:**
> Add or remove checklist items as needed. Keep brief status notes inline, for example:
> `- [x] Implement build dedupe — <commit or short note>`

---

# ADE API Run Logic Simplification

## 1. Objective

**Goal:**
Make run execution simple, predictable, and scalable:

* Runs are first-class, independent executions.
* Builds are shared and deduplicated.
* The API schedules execution through a queue and enforces a concurrency limit.
* Timeouts do not leave runs/builds stuck in an “in progress” state.

You will:

* Simplify the run domain model (remove retry semantics; require exactly one input document per run).
* Simplify build selection (get-or-create by fingerprint; execute a build at most once).
* Add a simple queue that limits concurrent run execution (configurable via `Settings` / env vars).
* Define and implement timeout behavior that is correct on SQLite, MSSQL, and Postgres.

The result should:

* Avoid burst overload: 1000 run submissions do not start 1000 builds or 1000 engine processes.
* Be readable and maintainable (small functions, explicit names, minimal branching).
* Keep the system behavior easy to explain to non-technical stakeholders.

Non-goals:

* Introduce a third-party queue system (Celery/Redis/etc.).
* Preserve backwards compatibility for legacy columns or API shapes.
* Implement a distributed multi-machine worker fleet (this design should not block future scaling, but it is not required now).

---

## 2. Context (Starting point)

Current implementation characteristics (high-level):

* Run submission starts a background task per request. If 1000 runs are submitted, 1000 background tasks may start immediately.
* Build orchestration includes complex branching and uses process-local task registries to avoid duplicate build runners.
* The database schema includes retry concepts (`attempt`, `retry_of_run_id`) even though the engine has no retry mode.
* Some fields that should identify a run are optional in the schema today (`input_document_id`, `build_id`), which conflicts with the desired model.
* Settings include `max_concurrency`, `queue_size`, and `run_timeout_seconds`, but those settings are not enforced.

This work is needed because:

* We need predictable performance and resource usage under bursts.
* We want an execution model that is straightforward: create runs quickly; run them later in a controlled way; reuse builds.

Constraints:

* Must support SQLite, MSSQL, and Postgres.
* We are free to modify the initial migration and update code/tests accordingly (no backwards compatibility requirement).

---

## 3. Target architecture / structure (ideal)

Desired end state:

* A run is created quickly and stored as `queued`.
* A worker pool starts runs up to a configured concurrency limit.
* A run references exactly one input document and exactly one build.
* Builds are reused and deduplicated by `(configuration_id, fingerprint)`.
* Timeouts are enforced during execution; stuck states are corrected during normal operation.

```text
apps/ade-api/
  migrations/versions/0001_initial_schema.py       # runs/builds schema changes (in-place)
  src/ade_api/features/runs/                       # run lifecycle + worker pool
  src/ade_api/features/builds/                     # build dedupe + claim/execute semantics
  src/ade_api/settings.py                          # enforce max_concurrency/queue_size/run_timeout_seconds
apps/ade-web/                                      # OpenAPI/types and UI wording updates as needed
docs/                                              # docs updated to describe the new behavior
```

---

## 4. Design (four passes)

### Pass 1 — How the system should function (simple terms)

This pass describes system behavior from start to finish, without implementation details.

#### 1) Inputs

* A **document** is an uploaded file stored by the system and identified by `document_id`.
* A **configuration** is the set of rules/code used to process a document.
* A **run** is one execution of the engine for one `document_id` using one `configuration_id`.

#### 2) Creating a run

When a user triggers a run:

* The system creates a new run record immediately.
* The run record includes:
  * `workspace_id`
  * `configuration_id`
  * `input_document_id`
  * timestamps (created immediately; start/finish later)
  * status initially `queued`
* The system also assigns a build (`build_id`) that the run will use.
* If the queue is full (based on configuration), the system rejects the request with a clear “queue full” error and does not create a run.

#### 3) Builds (reused and deduplicated)

* A build is a prepared environment for a configuration fingerprint.
* If a matching build already exists and is ready, the run uses it.
* If a matching build does not exist, the system creates exactly one build record and starts its execution once.
* If many runs are created at once for the same fingerprint, they all reference the same build and do not create duplicates.

#### 4) Run execution queue (bounded concurrency)

* The system does not execute all runs immediately.
* A configurable limit controls how many runs may execute at the same time (`ADE_MAX_CONCURRENCY`).
* Runs beyond that limit remain queued until capacity is available.
* Runs are started in the order they were created, except when a run cannot start because its build is not ready.

#### 5) Running, cancelling, and “run again”

* When a run starts executing, the system marks it `running` and records `started_at`.
* When a run finishes, it is marked as one terminal outcome:
  * `succeeded`
  * `failed`
  * `cancelled`
  and the system records `finished_at`.
* Cancelling a run:
  * If the run has not started, it is marked `cancelled` and will not run.
  * If the run is running, the engine process is stopped and the run is marked `cancelled`.
* “Run again” always creates a new run record. Previous runs remain unchanged.

#### 6) Logs, events, and outputs

* A run should provide:
  * current status
  * a stream of logs/events while it is executing
  * a reference to output artifacts after completion

#### 7) Timeouts

* Builds have a configured timeout (`ADE_BUILD_TIMEOUT`).
* Runs have a configured timeout (`ADE_RUN_TIMEOUT_SECONDS`).
* When a timeout occurs, the system stops the relevant work and marks the build/run as failed with a clear message.
* The system should not leave builds/runs stuck as “in progress” indefinitely.

---

### Pass 2 — Data model and rules (technical, but readable)

#### Definitions

* **Fingerprint:** a deterministic identifier for the build inputs (configuration contents + engine spec/version).
* **Build:** a record representing a prepared environment for one fingerprint.
* **Run:** a record representing one execution for one input document using one build.

#### Run rules

Runs must satisfy:

* `workspace_id` is required.
* `configuration_id` is required.
* `input_document_id` is required (one run = one input document).
* `build_id` is required (the run always references the build it will use).
* Retry semantics are removed:
  * remove `attempt`
  * remove `retry_of_run_id`

Run status set (recommended):

* Non-terminal: `queued`, `running`
* Terminal: `succeeded`, `failed`, `cancelled`

There is no distinct `waiting_for_build` run status. When a run is blocked on its build, it remains `queued` and the build status (and/or run events) explains why it has not started.

#### Build rules

Builds must satisfy:

* Uniqueness:
  * `(configuration_id, fingerprint)` uniquely identifies a build row.
* `fingerprint` is required (non-null).
* Only one build execution should run for a given build row at a time.

Build status set:

* `queued`, `building`, `ready`, `failed`, `cancelled`

#### Settings (configuration knobs)

These are already present in `apps/ade-api/src/ade_api/settings.py` and must be enforced:

* `ADE_MAX_CONCURRENCY` (`Settings.max_concurrency`)
  * Default: 2.
  * Server-level setting; enforced per API process.
  * Maximum number of runs that may be executing at once in a single API process.
* `ADE_QUEUE_SIZE` (`Settings.queue_size`)
  * Maximum number of non-terminal runs allowed (recommended: count runs in `queued` and `running`).
  * Server-level setting (not per workspace).
* `ADE_BUILD_TIMEOUT` (`Settings.build_timeout`)
  * Maximum time a build may spend in `building`.
* `ADE_RUN_TIMEOUT_SECONDS` (`Settings.run_timeout_seconds`)
  * Maximum time a run may spend in `running`.

#### Cross-database compatibility rules

To support SQLite, MSSQL, and Postgres:

* Use unique constraints to deduplicate builds.
* Use “compare-and-swap” updates to claim work:
  * `UPDATE ... WHERE status = ...`
* Compute time thresholds in Python and compare timestamps directly in queries.
* Avoid DB-specific “job queue” features (e.g., `SKIP LOCKED`) unless we implement per-dialect alternatives.

---

### Pass 3 — Execution details (algorithms)

This pass defines the minimal algorithms needed for correctness under concurrency.

#### 1) Build get-or-create (dedupe)

Inputs: `configuration_id`, `fingerprint`

Algorithm:

1. Insert build row `(configuration_id, fingerprint, status='queued')`.
2. If insert fails because the row already exists, fetch the existing row.
3. Return the build row.

Guarantee: concurrent run submissions converge on one build row for a fingerprint.

#### 2) Build execution (single runner)

When a build needs to execute:

1. Claim build execution:
   * `UPDATE builds SET status='building', started_at=now WHERE id=:id AND status='queued'`
2. If claim succeeds (1 row updated), execute the build to completion and update status to `ready` or `failed`.
3. If claim does not succeed, another worker already owns execution; do not run a second build process.
4. Waiting behavior:
   * If a run needs this build, it waits for completion (via events/streaming or periodic status checks).

#### 3) Run submission

On `POST /configurations/{configuration_id}/runs`:

1. Require and validate `input_document_id` (document must exist in workspace).
2. Compute configuration fingerprint.
3. Get-or-create the build for that fingerprint.
4. If the build is not `ready`, start/continue the build execution (best-effort, idempotent).
5. Enforce `queue_size` if configured (reject if full).
6. Create run row with `status='queued'`, `build_id`, and timestamps.
7. Return the run immediately.

#### 4) Run execution workers (bounded worker pool)

The system runs a fixed-size worker pool:

* Worker count = `Settings.max_concurrency`.
* Workers are started at application startup.
* Each worker repeatedly:
  1. Select the next run candidate:
     * Oldest run where `runs.status='queued'` and the referenced build is terminal (`ready`, `failed`, or `cancelled`).
  2. If the build is `failed` or `cancelled`, mark the run `failed` with a clear “build failed” message and continue.
  3. If the build is `ready`, claim the run:
     * `UPDATE runs SET status='running', started_at=now WHERE id=:id AND status='queued'`
     * If the update affects 0 rows, another worker claimed it; continue.
  4. Execute the engine for the run (enforcing `run_timeout_seconds`).
  5. Record terminal status and `finished_at`.

Guarantees (simple and explicit):

* In a single API process, at most `max_concurrency` runs execute concurrently, because there are only that many workers.
* Runs are not started until the referenced build is terminal. “Waiting for build” is represented by `runs.status='queued'` plus the build status/events.
* If multiple API processes are deployed, each process runs its own worker pool. Total concurrency is the sum across processes.

#### 5) Timeouts and stuck-state cleanup (no external scheduler)

Timeout enforcement:

* Build execution enforces `build_timeout`.
* Run execution enforces `run_timeout_seconds`.

Stuck-state cleanup:

* During normal worker operation and/or normal status reads:
  * builds in `building` with `started_at` older than `build_timeout` are marked `failed` with a timeout message
  * runs in `running` with `started_at` older than `run_timeout_seconds` are marked `failed` with a timeout message

This avoids introducing a separate scheduler service while ensuring stuck states are eventually corrected.

---

### Pass 4 — Implementation plan (files, tests, acceptance)

#### 1) Schema changes (in-place)

Decision: modify `apps/ade-api/migrations/versions/0001_initial_schema.py` directly.

Planned schema changes:

Runs:

* Drop retry fields:
  * remove `attempt`
  * remove `retry_of_run_id` and its index
* Make identity fields required:
  * `input_document_id` non-nullable
  * `build_id` non-nullable
* Remove the `waiting_for_build` run status (keep `queued`, `running`, `succeeded`, `failed`, `cancelled`).

Builds:

* Add unique constraint/index:
  * `(configuration_id, fingerprint)` unique
* Remove the “one inflight build per configuration” partial index (`ux_builds_inflight_per_config`) and rely on fingerprint dedupe instead.

#### 2) API contract changes

* Require `input_document_id` at run creation (do not allow null runs).
* If `queue_size` is configured and the queue is full, reject run creation with HTTP 429 and a stable error code (e.g., `run_queue_full`).
* Ensure run responses clearly communicate:
  * status
  * build reference (or build-derived details)
  * where to stream events/logs and where to download outputs

#### 3) Code changes (high-level)

Runs:

* Add a run worker pool (size = `Settings.max_concurrency`) started at application startup.
* Enforce `Settings.queue_size` during run submission.
* Remove any retry/attempt handling in services and tests.
* Replace per-request run background tasks with the worker pool.
* Update `Settings.max_concurrency` default to 2 (so queueing is enabled by default).

Builds:

* Implement build get-or-create by `(configuration_id, fingerprint)`.
* Ensure build execution is single-runner via a claim update (no process-local-only dedupe).

Timeouts:

* Enforce build timeout during build execution.
* Enforce run timeout during run execution.
* Add stuck-state cleanup in the worker pool and/or status reads.

#### 4) Test plan

Minimum tests for confidence:

* Build dedupe: concurrent build creation yields a single build row for a fingerprint.
* Queue: with `max_concurrency=1`, multiple queued runs never result in >1 running at the same time.
* Queue size: submissions over `queue_size` are rejected with a stable error.
* Timeout: a forced timeout produces a terminal failed run/build and does not leave an in-progress status.

#### 5) Acceptance criteria

This work is complete when:

* 1000 run submissions for the same configuration fingerprint create:
  * 1000 run rows (queued) and at most 1 build row for that fingerprint
  * at most 1 build execution in progress for that build row
* With `ADE_MAX_CONCURRENCY = N`, a single API process never executes more than N runs at once.
* Timeouts produce clear terminal states and do not leave permanent “running/building” records.
* Behavior is consistent on SQLite, MSSQL, and Postgres.

#### Final decisions (locked)

* Runs:
  * Statuses are `queued`, `running`, `succeeded`, `failed`, `cancelled`.
  * There is no `waiting_for_build` status; build waiting is derived from build state and events.
  * Retry is “create a new run” (no attempt/retry columns).
* Limits:
  * `ADE_MAX_CONCURRENCY` and `ADE_QUEUE_SIZE` are server-level limits (not per workspace).
  * Concurrency is enforced per API process via a fixed worker pool.

#### Simplifications checklist (verify removals/simplifications)

This checklist is specifically about confirming we actually removed complexity (not just moved it).

Runs (router + service):

* [ ] Remove per-request run execution via background tasks (delete `_execute_run_background` and `background_tasks.add_task` in `apps/ade-api/src/ade_api/features/runs/router.py`).
* [ ] Remove “execute while streaming” behavior from HTTP streaming paths; streaming endpoints only stream persisted/live events and do not start engine processes.
* [ ] Remove `RunStatus.WAITING_FOR_BUILD` and any logic that sets it (run always starts as `queued` until a worker claims it).
* [ ] Remove retry semantics from the run model and service (`attempt`, `retry_of_run_id`).
* [ ] Replace ad-hoc run execution triggers with a single worker entrypoint (one place that starts an engine process for a run).

Builds (service):

* [ ] Replace the build decision tree (`_resolve_build`) with a single get-or-create-by-fingerprint path plus claim semantics.
* [ ] Remove process-local build runner registries (`_global_build_tasks`, `launch_build_if_needed`) and rely on database uniqueness + claim updates.
* [ ] Ensure we do not “join” a build with a different fingerprint than the run expects.

Database / migrations:

* [ ] Remove `runs.attempt`, `runs.retry_of_run_id`, and `ix_runs_retry_of` from `apps/ade-api/migrations/versions/0001_initial_schema.py`.
* [ ] Make `runs.input_document_id` and `runs.build_id` non-null in `apps/ade-api/migrations/versions/0001_initial_schema.py`.
* [ ] Remove `ux_builds_inflight_per_config` (the “one inflight build per configuration” partial index) from `apps/ade-api/migrations/versions/0001_initial_schema.py`.
* [ ] Add unique `(builds.configuration_id, builds.fingerprint)` and make `builds.fingerprint` non-null in `apps/ade-api/migrations/versions/0001_initial_schema.py`.

Settings enforcement:

* [ ] Set `Settings.max_concurrency` default to `2` and ensure the worker pool size uses it (`apps/ade-api/src/ade_api/settings.py`).
* [ ] Enforce `Settings.queue_size` during run creation; return HTTP 429 with a stable error code (e.g., `run_queue_full`).
* [ ] Enforce `Settings.run_timeout_seconds` and `Settings.build_timeout` during execution and mark stuck records terminal during normal worker operation.

Frontend/docs alignment:

* [ ] Remove “retry run” wording and semantics from docs/UI; use “run again” = create a new run.
* [ ] Ensure the UI derives “waiting for build” from build state/events, not from a run status field.

---

## 5. Implementation notes for agents

* Prefer portable SQL and simple patterns:
  * unique constraints for dedupe
  * `UPDATE ... WHERE status=...` for claiming work
* Keep orchestration readable:
  * small functions with explicit names (`get_or_create_build`, `claim_next_run`, `expire_stuck_runs`)
  * minimal branching; prefer early returns
* When changing OpenAPI contracts, regenerate frontend types (`ade types`) and update any UI copy that mentions “retry” behavior.
