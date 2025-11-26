# 11 – ADE event model, streaming, and persistence

This document defines the **unified ADE event model** shared across:

- `ade_engine` telemetry (`events.ndjson`),
- ADE API run streaming,
- ADE API build streaming, and
- backend persistence and reporting.

It is the architectural target for ade-engine + ade-api and should be treated
as the single “language” for events. Engine and API implementations can
evolve toward this shape additively.

For engine-side details (how events are emitted from `ade_engine`), see
`07-telemetry-events.md`. For artifact structure, see `06-artifact-json.md`.

---

## 1. Design principles

1. **One envelope, many event types**

   All events share one envelope (`ade.event/v1`) with a `type` discriminator.
   Engine telemetry, run streaming, and build streaming all use it.

2. **Artifact is the audit; events are the timeline**

   - `artifact.json` – final, human-readable snapshot of a run.
   - ADE events – chronological logs of everything that happened.

3. **Shared environment semantics**

   Env readiness (missing venv, digest mismatch, Python mismatch,
   `forceRebuild`) behaves consistently across `/build` and `/runs`. The same
   env fields and values appear in events.

4. **SQL stores summaries, not raw logs**

   Databases hold statuses and aggregates (run/build summaries). Raw
   per-event logs stay in files or object storage.

5. **Additive and versioned**

   - Envelope includes `schema` and `version`.
   - New event types and fields are added without breaking consumers.
   - Breaking changes require a new schema family or major version bump.

---

## 2. ADE event envelope (`ade.event/v1`)

Every event is an ADE Event with this high-level shape:

```jsonc
{
  "type": "run.created",          // primary discriminator
  "object": "ade.event",
  "schema": "ade.event/v1",
  "version": "1.0.0",

  "created_at": "2025-11-26T12:00:00Z",

  "workspace_id": "ws_123",
  "configuration_id": "cfg_123",
  "run_id": "run_123",
  "build_id": null,

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

### 2.1 Fields

* `type: str`  
  Event name; namespace prefixes are conventional:

  * `run.*` – run lifecycle and internals.
  * `build.*` – build lifecycle and env.
  * `env.*` – optional env-only events (can also be embedded in `run.*` /
    `build.*`).
  * others as needed (`audit.*`, etc.).

* `object: "ade.event"`  
  Constant allowing clients to distinguish these from other stream objects.

* `schema: "ade.event/v1"`  
  Schema family identifier (see §7).

* `version: string`  
  Semantic version for this schema family (e.g. `1.0.0`).

* `created_at: ISO 8601 timestamp`  
  When the event was produced (UTC).

* `workspace_id`, `configuration_id`, `run_id`, `build_id`  
  Correlation identifiers. They may be `null` when not applicable (e.g. build
  events have `build_id` but no `run_id`). Semantics:

  * `workspace_id` – ADE workspace/tenant.
  * `configuration_id` – config/manifest identifier.
  * `run_id` – ADE run identifier (API-level run object).
  * `build_id` – ADE build identifier (virtual environment build).

* Namespaced payload objects:

  * `run` – run lifecycle and internal status.
  * `build` – build lifecycle and status.
  * `env` – environment planning and diffs.
  * `validation` – validation issues and summaries.
  * `execution` – execution status (exit codes, timing, resource usage).
  * `output_delta` – output-related deltas (like table summaries).
  * `log` – log lines (stdout/stderr, or structured logs).
  * `error` – structured error information.

Only a subset of payload namespaces is present in any given event; `null`
values mean “not applicable”.

---

## 3. Event families

This section defines the canonical event types and which parts of the envelope
they use. The sets are split into build and run domains.

### 3.1 Build event family (API-side)

Build events are emitted by ADE API when a user requests:

```http
POST /workspaces/:workspace/configurations/:configuration/build
```

#### 3.1.1 `build.created`

Emitted when a build request is accepted.

Payload:

```jsonc
{
  "type": "build.created",
  "build_id": "b_123",
  "workspace_id": "ws_1",
  "configuration_id": "cfg_1",
  "build": {
    "status": "queued"
  }
}
```

#### 3.1.2 `build.plan`

Emitted when env evaluation completes (shared with run env planning).

`env` payload:

```jsonc
"env": {
  "should_build": true,
  "force": true,
  "reason": "force_rebuild",  // "missing_env" | "digest_mismatch" | "engine_spec_mismatch" | "python_mismatch" | "force_rebuild" | "reuse_ok"
  "engine_spec": "ade-engine==0.2.0",
  "engine_version_hint": "0.2.0",
  "python_bin": "/usr/bin/python3.11"
}
```

If `env.should_build == false`, a subsequent `build.completed` is still
emitted (with `build.status: "active"` and `env.reason: "reuse_ok"`), but
there is no actual build process.

#### 3.1.3 `build.progress`

Emitted during build steps when `env.should_build == true`.

`build` payload:

```jsonc
"build": {
  "phase": "create_venv",          // "create_venv" | "upgrade_pip" | "install_engine" | "install_config" | "verify_imports" | "collect_metadata"
  "message": "Starting virtualenv"
}
```

#### 3.1.4 `build.log.delta`

Structured logs from the build process:

```jsonc
"log": {
  "stream": "stdout",              // or "stderr"
  "message": "Collecting ade-engine==0.2.0"
}
```

#### 3.1.5 `build.completed`

Terminal event for builds.

Possible statuses:

* `build.status: "active"` – env is ready for use.
* `build.status: "failed"` – build failed.
* `build.status: "canceled"` – build was canceled by the system/user.

Example payload:

```jsonc
"build": {
  "status": "active",
  "exit_code": 0,
  "summary": "Build succeeded"
},
"env": {
  "reason": "force_rebuild"
}
```

If the build fails:

```jsonc
"build": {
  "status": "failed",
  "exit_code": 1
},
"error": {
  "code": "build_failed",
  "message": "pip install exited with code 1",
  "details": { "...": "..." }
}
```

---

### 3.2 Run event family (API + engine)

Run events describe the lifecycle and internals of a single ADE run. They are
emitted by both:

* ADE API (wrapper lifecycle, env planning, summary).
* `ade_engine` (pipeline phases, table summaries, validation issues).

#### 3.2.1 `run.created` (API)

Emitted when a run is accepted.

Payload:

```jsonc
"run": {
  "status": "queued",
  "mode": "test",         // e.g. "test" | "production" | "validation"
  "options": {
    "dryRun": false,
    "validateOnly": false,
    "forceRebuild": true
  },
  "document_id": "doc_123"  // optional, backend ID
}
```

#### 3.2.2 `run.env.plan` (API)

Same `env` payload as `build.plan`, but scoped to a run:

```jsonc
"env": {
  "should_build": true,
  "force": true,
  "reason": "force_rebuild",
  "engine_spec": "ade-engine==0.2.0",
  "engine_version_hint": "0.2.0",
  "python_bin": "/usr/bin/python3.11"
}
```

The API may emit additional `run.env.progress` / `run.env.log.delta` events if
it chooses to perform the build inline for this run.

#### 3.2.3 `run.started` (engine)

Emitted by the engine when pipeline execution begins.

```jsonc
"run": {
  "engine_version": "0.2.0"
}
```

The API may also emit its own `run.started` when it hands the run off to a
worker. Implementations should agree on which side “owns” this event or
coordinate to avoid duplicates.

#### 3.2.4 `run.pipeline.progress` (engine)

Emitted at each pipeline phase:

```jsonc
"run": {
  "phase": "extracting",          // "initialization" | "load_config" | "extracting" | "mapping" | "normalizing" | "writing_output" | "hooks" | "completed" | "failed"
  "message": "Reading 1 source file",
  "file_count": 1
}
```

#### 3.2.5 `run.table.summary` (engine)

Emitted once per table, after mapping and normalization.

```jsonc
"output_delta": {
  "kind": "table_summary",
  "table": {
    "source_file": "input.xlsx",
    "source_sheet": "Sheet1",
    "table_index": 0,
    "row_count": 123,
    "validation_issue_counts": {
      "error": 2,
      "warning": 5
    }
  }
}
```

#### 3.2.6 `run.validation.issue.delta` (engine, optional)

Fine-grained streaming of validation issues.

```jsonc
"validation": {
  "source_file": "input.xlsx",
  "source_sheet": "Sheet1",
  "row_index": 10,
  "field": "email",
  "code": "invalid_format",
  "severity": "error",
  "message": "Email must look like user@domain.tld",
  "details": {
    "value": "foo@"
  }
}
```

This event is optional; `artifact.json` remains the canonical list of issues.

#### 3.2.7 `run.note` (engine / hooks)

Narrative notes aligned with artifact `notes`:

```jsonc
"run": {
  "message": "Run started",
  "level": "info",
  "details": {
    "config_version": "1.2.3"
  }
}
```

#### 3.2.8 `run.log.delta` (API and/or engine)

Structured logs from the run process:

```jsonc
"log": {
  "stream": "stdout",
  "message": "mode: normal"
}
```

#### 3.2.9 `run.completed` (engine)

Engine-level terminal state. This describes the result of pipeline execution;
it does not know about env/builder or DB persistence.

```jsonc
"run": {
  "engine_status": "succeeded",     // or "failed"
  "error": null
}
```

If the engine fails:

```jsonc
"run": {
  "engine_status": "failed"
},
"error": {
  "code": "pipeline_error | config_error | input_error | hook_error | unknown_error",
  "message": "Short human-readable summary",
  "details": { "...": "..." }
}
```

#### 3.2.10 `run.completed` (API)

API emits its own `run.completed` summarizing the entire ADE run:

```jsonc
"run": {
  "status": "succeeded",           // final run status
  "mode": "test",
  "options": { "forceRebuild": true, "validateOnly": false },
  "execution_summary": {
    "exit_code": 0,
    "duration_ms": 10000
  },
  "env_summary": {
    "status": "active",            // "active" | "failed" | "reused"
    "reason": "force_rebuild"
  },
  "validation_summary": {
    "status": "passed",            // "passed" | "failed" | "skipped"
    "issue_counts": {
      "error": 2,
      "warning": 5
    }
  },
  "artifact_path": "logs/artifact.json",
  "events_path": "logs/events.ndjson",
  "output_paths": ["output/output.xlsx"],
  "processed_files": ["input/input.xlsx"]
}
```

On failure, `run.status` is `"failed"` and `error` is populated.

API and engine implementations should agree on how to disambiguate engine-level
vs API-level `run.completed`. One simple approach is:

* Engine uses `run.engine_status` (with a `run.completed` event).
* API uses `run.status` (also with `run.completed`), and consumers look at the
  presence of `run.status` to detect the system-wide terminal state.

---

### 3.3 Validation-only runs

When ADE is invoked in “validation-only” mode (`validateOnly: true`), the
event flow becomes:

1. `run.created` (API) – `run.mode: "validation"` or `options.validateOnly: true`.

2. `run.env.plan` (API) – env planning (if needed for manifest inspection).

3. `run.validation.started` (API or engine) – begin validation.

4. Zero or more `run.validation.issue.delta` events.

5. `run.validation.completed` – aggregated validation status:

   ```jsonc
   "validation": {
     "status": "failed",
     "issue_counts": {
       "error": 3,
       "warning": 12
     }
   }
   ```

6. `run.completed` (API) – final status, possibly with an artifact path if you
   choose to persist validation results as a mini-artifact.

Whether a full `artifact.json` is written for validation runs is a design
choice; the event model supports either.

---

## 4. Example: build + run streaming

A typical sequence of events for “build if needed, then run” might look like:

```text
# Build (API)
{"type":"build.created", ...}
{"type":"build.plan", ... "env":{"should_build":true,"reason":"digest_mismatch"}}
{"type":"build.progress", ... "build":{"phase":"create_venv"}}
{"type":"build.log.delta", ...}
{"type":"build.progress", ... "build":{"phase":"install_engine"}}
{"type":"build.progress", ... "build":{"phase":"install_config"}}
{"type":"build.completed", ... "build":{"status":"active"},"env":{"reason":"digest_mismatch"}}

# Run (API + engine)
{"type":"run.created", ... "run":{"status":"queued","mode":"test","options":{"forceRebuild":false}}}
{"type":"run.env.plan", ... "env":{"should_build":false,"reason":"reuse_ok"}}
{"type":"run.started", ... "run":{"engine_version":"0.2.0"}}
{"type":"run.pipeline.progress", ... "run":{"phase":"extracting"}}
{"type":"run.table.summary", ...}
{"type":"run.completed", ... "run":{"engine_status":"succeeded"}}
{"type":"run.completed", ... "run":{"status":"succeeded","execution_summary":{"exit_code":0,...},"artifact_path":"logs/artifact.json","output_paths":["output/output.xlsx"]}}
```

Consumers can:

* Filter by `type` prefix (`build.*`, `run.*`).
* Join runs and builds by `workspace_id` + `configuration_id`, or by explicit
  linking fields you choose to add.
* Build experience-specific projections (e.g. “current run progress bar”, or
  “recent build history” table).

---

## 5. Persistence and reporting

The event model is intentionally log-like. For operational storage and
reporting, ADE should treat events as source data and store summaries
elsewhere.

### 5.1 Database tables

At minimum, the backend should maintain:

* `runs` / `run_summaries`:

  * `run_id`, `workspace_id`, `configuration_id`
  * `status`, `mode`, timestamps
  * `env_reason`
  * `validation_error_count`, `validation_warning_count`
  * `artifact_path`, `events_path`, `output_paths_json`

* `builds` / `build_summaries`:

  * `build_id`, `configuration_id`, `workspace_id`
  * `status`, `env_reason`
  * `engine_spec`, `python_bin`
  * timestamps
  * `summary`, `exit_code`

These summaries can be derived from:

* ADE events (`run.completed`, `build.completed`, etc.).
* `artifact.json` (for run counts and validation metrics).

### 5.2 Logs and long-term storage

Raw event streams should be:

* Kept as files or in object storage (e.g., bucket per run/build).
* Indexed by log/observability tooling if needed (via log shipping).

The DB should not store every event as a row unless there is a clear need;
doing so will explode row counts with very little benefit.

---

## 6. Implementation guidance

### 6.1 Engine (`ade_engine`)

* Emit ADE events (`ade.event/v1`) to `events.ndjson` as described in
  `07-telemetry-events.md`:

  * `run.started`
  * `run.pipeline.progress`
  * `run.table.summary`
  * `run.validation.issue.delta` (optional)
  * `run.note`
  * `run.completed` (engine status)

* Keep event construction behind a small helper (`PipelineLogger` +
  `EventSink`) so future adjustments to the envelope are centralized.

* Ensure `events.ndjson` exists and is well-formed even on early failures.

### 6.2 ADE API

* For builds:

  * Use a shared `EnvironmentManager` to compute env plans
    (`should_build`, `reason`, etc.).
  * Emit `build.created`, `build.plan`, `build.progress`, `build.log.delta`,
    and `build.completed` accordingly.

* For runs:

  * Emit `run.created` when a run is accepted.
  * Use the same `EnvironmentManager` to emit `run.env.plan` (and optional
    `run.env.*` events).
  * When invoking the engine process:

    * Stream engine ADE events from `events.ndjson`.
    * Optionally wrap stdout/stderr as `run.log.delta`.
  * Emit the final API-level `run.completed` summarizing:

    * `status` (succeeded/failed),
    * env summary,
    * validation summary,
    * execution summary,
    * `artifact_path`, `events_path`, `output_paths`.

* Avoid introducing new event envelopes; everything should be an `ade.event`.

---

## 7. Versioning and evolution

The ADE event schema is versioned in two dimensions:

* `schema` – family identifier (`"ade.event/v1"`).
* `version` – semantic version inside that family (`"1.0.0"`, `"1.1.0"`, etc.).

### 7.1 Backwards-compatible changes

Allowed within the same schema family:

* Adding new event types.
* Adding new optional fields to existing payloads.
* Adding new enum values that callers are expected to treat as “unknown but
  ignorable”.

Consumers must:

* Ignore unknown `type` values.
* Ignore unknown fields in known types.

### 7.2 Breaking changes

Require either:

* A new schema family (`"ade.event/v2"`), or
* A major `version` bump and explicit migration steps.

Breaking changes include:

* Removing or renaming existing event types.
* Changing the meaning or type of existing fields.
* Changing correlation semantics (e.g., what `run_id` refers to).

---

With this model:

* Engine and API speak a single event language.
* UI and reporting code only need to understand `ade.event/v1` once.
* Future extensions (extra event families, new payload fields) can be added
  incrementally without breaking existing consumers.
