# 11 – ADE event model, streaming, and persistence

This document specifies the **unified ADE event model** so that:

- engine telemetry,
- run streaming,
- build streaming,
- and reporting

all use the **same envelope and type names**.

It is the architectural target for `ade-engine` + `ade-api`. Engine and API
should evolve toward this shape additively.

---

## 1. Design principles

1. **Single event mental model**

   - One envelope (`ade.event/v1`) with a `type` discriminator.
   - Engine, run streaming, and build streaming all use it.

2. **Artifact is the audit; events are the timeline; summary is the dashboard**

   - `artifact.json` – canonical, human-readable snapshot after the run.
   - `events.ndjson` / streamed events – “how we got there”.
   - `run.summary` – compact metrics computed by the API for UIs and BI.

3. **Shared environment semantics**

   - Env readiness (`missing_env`, `digest_mismatch`, `python_mismatch`,
     `forceRebuild`) behaves the same whether invoked via `/build` or `/runs`.

4. **SQL stores summaries, not raw logs**

   - Database tables hold statuses and aggregates (run summaries, counts).
   - Full logs/telemetry stay in files or object storage.

5. **Additive and versioned**

   - New event types and fields are added without breaking consumers.
   - Envelope carries `schema` + `version`.

---

## 2. Event envelope: `ade.event/v1`

All ADE events share the same outer shape:

```jsonc
{
  "type": "run.created",              // primary discriminator
  "object": "ade.event",
  "schema": "ade.event/v1",
  "version": "1.0.0",
  "created_at": "2025-11-26T12:00:00Z",

  // Correlation context (nullable when not applicable)
  "workspace_id": "ws_123",
  "configuration_id": "cfg_123",
  "run_id": "run_123",
  "build_id": "b_123",

  // Payload namespaces (present as needed)
  "run": null,
  "build": null,
  "env": null,
  "validation": null,
  "execution": null,
  "output_delta": null,
  "log": null,
  "error": null
}
```

Conventions:

* `type` drives interpretation (e.g. `"run.created"`, `"build.progress"`,
  `"run.table.summary"`, `"build.log.delta"`, `"run.completed"`).
* `object`, `schema`, and `version` are constant per schema family.
* `created_at` is ISO 8601 UTC.
* Context IDs (`workspace_id`, `configuration_id`, `run_id`, `build_id`) may be
  `null` when not applicable (e.g. some engine events know only the `run_id`).

Payload namespaces:

* `run` – run-specific fields (status, options, phases, summary).
* `build` – build-specific fields (phase, status).
* `env` – environment plan / decisions.
* `validation` – validation-only modes.
* `execution` – process-level data (exit code, duration).
* `output_delta` – “something changed in outputs” (tables, files, etc.).
* `log` – passthrough stdout/stderr lines.
* `error` – structured error info.

Only the namespaces needed by that `type` are populated.

---

## 3. Canonical event sets

We group event types by domain: **builds** and **runs**.

### 3.1 Build stream (API-generated)

These events describe environment evaluation and build execution.

#### 3.1.1 `build.created`

Emitted when a build request is accepted/queued:

```jsonc
{
  "type": "build.created",
  "workspace_id": "ws_1",
  "configuration_id": "cfg_1",
  "build_id": "b_1",
  "build": {
    "status": "queued"
  }
}
```

#### 3.1.2 `build.plan`

Result of environment evaluation (environment manager):

```jsonc
{
  "type": "build.plan",
  "workspace_id": "ws_1",
  "configuration_id": "cfg_1",
  "build_id": "b_1",
  "env": {
    "should_build": true,
    "force": true,
    "reason": "force_rebuild",          // missing_env | digest_mismatch | engine_spec_mismatch | python_mismatch | force_rebuild | reuse_ok
    "engine_spec": "ade-engine==0.2.0",
    "engine_version_hint": "0.2.0",
    "python_bin": "/usr/bin/python3.11"
  }
}
```

If `should_build` is `false`, no venv work is done; the API typically emits
`build.completed` shortly after with `status: "active"` and an env reason of
`"reuse_ok"`.

#### 3.1.3 `build.progress`

Emitted as build phases advance:

```jsonc
{
  "type": "build.progress",
  "build_id": "b_1",
  "build": {
    "phase": "create_venv",             // create_venv | upgrade_pip | install_engine | install_config | verify_imports | collect_metadata
    "message": "Starting build"
  }
}
```

#### 3.1.4 `build.log.delta`

Passthrough of build stdout/stderr:

```jsonc
{
  "type": "build.log.delta",
  "build_id": "b_1",
  "log": {
    "stream": "stdout",                 // stdout | stderr
    "message": "Collecting ade-engine==0.2.0"
  }
}
```

#### 3.1.5 `build.completed`

Terminal summary:

```jsonc
{
  "type": "build.completed",
  "build_id": "b_1",
  "build": {
    "status": "active",                 // active | failed | canceled
    "exit_code": 0,
    "summary": "Build succeeded"
  },
  "env": {
    "reason": "force_rebuild"
  }
}
```

When `env.should_build` was `false`, `status` is usually `"active"` with
`summary: "Reused existing build"` and `env.reason: "reuse_ok"`.

---

### 3.2 Run stream (API + engine)

Run streams combine:

* API wrapper events (created, env plan, completion),
* engine telemetry (phases, tables, results),
* API-computed run summaries.

#### 3.2.1 `run.created`

Emitted by the API when the run is accepted:

```jsonc
{
  "type": "run.created",
  "workspace_id": "ws_1",
  "configuration_id": "cfg_1",
  "run_id": "run_1",
  "run": {
    "status": "queued",
    "mode": "test",                     // production | test | validation
    "options": {
      "dryRun": false,
      "validateOnly": false,
      "forceRebuild": true
    }
  }
}
```

#### 3.2.2 `run.env.plan`

Environment evaluation for this run (reusing the same logic as `/build`):

```jsonc
{
  "type": "run.env.plan",
  "workspace_id": "ws_1",
  "configuration_id": "cfg_1",
  "run_id": "run_1",
  "env": {
    "should_build": true,
    "force": true,
    "reason": "force_rebuild",
    "engine_spec": "ade-engine==0.2.0",
    "engine_version_hint": "0.2.0"
  }
}
```

If the run triggers a build inline, the API may also emit `build.*` events on
the same stream for that `build_id`.

#### 3.2.3 Engine `run.*` events

While the engine runs, it writes `run.*` events to `events.ndjson` (see
`07-telemetry-events.md`):

* `run.started` – engine view of run start.
* `run.pipeline.progress` – phase transitions with small counters.
* `run.table.summary` – per-table row/issue counts.
* `run.note` – high-level notes.
* `run.completed` / `run.failed` – engine-level completion.

The API typically forwards these envelopes as-is to clients.

#### 3.2.4 `run.completed` (API wrapper + summary)

Once the engine process completes and the API has read `artifact.json` and
`events.ndjson`, it emits a **single canonical** `run.completed` event with a
run summary:

```jsonc
{
  "type": "run.completed",
  "workspace_id": "ws_1",
  "configuration_id": "cfg_1",
  "run_id": "run_1",
  "created_at": "2025-11-26T12:10:12Z",

  "run": {
    "status": "succeeded",             // succeeded | failed | canceled
    "mode": "test",
    "options": {
      "dryRun": false,
      "validateOnly": false,
      "forceRebuild": true
    },

    "execution_summary": {
      "exit_code": 0,
      "duration_ms": 10000
    },

    "env_summary": {
      "status": "active",              // active | failed | reused
      "reason": "force_rebuild"        // from env.reason
    },

    "artifact_path": "logs/artifact.json",
    "events_path": "logs/events.ndjson",
    "output_paths": ["output/output.xlsx"],

    "summary": {
      "schema": "ade.run_summary/v1",
      "version": "1.0.0",
      "run": { "... run identity subset ..." },
      "core": { "... flat metrics for BI ..." },
      "breakdowns": { "... by_file / by_field metrics ..." }
    }
  },

  "error": null
}
```

On failure:

* `run.status` is `"failed"`,
* `execution_summary.exit_code` is non-zero,
* `error` payload is populated using the same structure as `artifact.run.error`.

`run.summary` is defined in detail in `12-run-summary-and-reporting.md` and is
the **canonical shape** for:

* streaming to the front-end, and
* storing aggregated metrics in the `runs` table.

The engine itself does *not* populate `run.summary`; it is calculated by the
API from `artifact.json` + `events.ndjson`.

---

### 3.3 Validation-only runs

For `validateOnly` mode:

* The API still emits `run.created` and `run.env.plan`.

* If no engine execution is started, it emits:

  * `run.validation.started`,
  * optional `run.validation.issue.delta` events,
  * `run.validation.completed` with validation summary.

* Final `run.completed` still carries:

  * `run.status` and mode,
  * `run.summary` (validation metrics instead of row counts),
  * `artifact_path` and `events_path` if they exist.

Shape for validation events follows the same envelope; payloads live under the
`validation` namespace.

---

## 4. How engine and API cooperate

### 4.1 Engine responsibilities

The engine:

* accepts a `RunRequest`,

* writes:

  * `artifact.json` (audit snapshot),
  * `events.ndjson` (NDJSON with `ade.event/v1` run events),

* and exits with an appropriate code.

The engine:

* does **not** know about:

  * workspaces,
  * configuration IDs,
  * run request IDs,
  * database schemas.

* can include opaque metadata (e.g. `run_request_id`) in telemetry
  `metadata`/`run` payloads, but does not interpret it.

### 4.2 API responsibilities

The ADE API:

* manages venvs and builds (`build.*` events),
* manages queues and worker processes,
* owns:

  * `run.created` / `run.env.plan`,
  * `run.completed` (wrapper with summary),
  * persistence into the `runs` table and related tables.

On run completion, the API:

1. Reads `artifact.json` and `events.ndjson`.
2. Runs summarization code to produce `run.summary`.
3. Emits `run.completed` with:

   * engine outcome (`execution_summary`),
   * env outcome (`env_summary`),
   * paths to outputs/artifacts/events,
   * the summary object.
4. Upserts a row in `runs` table with:

   * identity fields (workspace, configuration, run),
   * status, mode, timestamps,
   * key metrics from `summary.core` as columns,
   * the full summary JSON (or a reference) for deeper analysis.

---

## 5. Persistence strategy

Guidelines:

* SQL tables store **summaries and statuses**, not raw logs:

  * `runs` – run identity, status, core metrics, and a summary JSON blob.
  * `run_field_metrics` (optional) – exploded `summary.breakdowns.by_field`
    for BI / Power BI.
  * `builds` – build identity, status, env reason, timings.

* Full event and log streams live in:

  * `artifact.json`,
  * `events.ndjson`,
  * optional external log storage (object store, log index).

This keeps database tables small and queryable, while preserving complete
details for audits and deep debugging.

---

## 6. Versioning and evolution

The event system is versioned via:

* `schema = "ade.event/v1"`,
* `version = "1.0.0"`.

Rules:

* **Additive changes** (safe):

  * new event types,
  * new optional fields in existing payload namespaces.

* **Breaking changes** (require planning):

  * changing payload shape for an existing `type`,
  * changing semantics of existing fields.

Breaking changes require:

* either a new `schema` (e.g. `"ade.event/v2"`),
* or a major version bump and a coordinated migration.

All changes should be covered by contract tests:

* engine event emission,
* API event wrapping,
* run summary generation,
* and persistence into the database.

`07-telemetry-events.md` focuses on engine emission details; this document is
the canonical reference for the **global ADE event model** and how streaming
and persistence fit together.
