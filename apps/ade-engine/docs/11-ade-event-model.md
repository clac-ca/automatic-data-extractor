# 11 – ADE event model, streaming, and persistence

This document defines the **unified ADE event model** for:

* engine telemetry
* run streaming (SSE / websockets)
* build streaming
* reporting & analytics

It’s heavily inspired by the OpenAI **Responses** event model, but adapted to ADE’s domains: **builds**, **runs**, **tables**, and **validation**.

Engine and API should evolve toward this shape additively.

---

## 1. Design principles

### 1.1 Lessons from the Responses API

From the Responses streaming model we adopt:

1. **Event types as contracts**
   Every event has a `type` like `response.created`, `response.output_text.delta`, etc.
   For ADE we follow the same pattern: `console.line`, `run.table.summary`, `build.completed`, etc.

2. **Flat envelopes, focused payloads**
   Responses events are shallow:

   ```jsonc
   { "type": "response.output_text.delta", "item_id": "…", "delta": "In", "sequence_number": 1 }
   ```

   We do the same: common fields at the top level, plus a small, event-specific payload.

3. **Resource snapshots vs. granular deltas**
   Some events carry a full `response` object (`response.completed`), others only the piece that changed (`part`, `item`, `delta`...).
   For ADE:

   * lifecycle events (`run.completed`, `build.completed`) can carry a full *resource snapshot* (e.g. a run summary),
   * granular events (`console.line`, `run.table.summary`, `run.validation.issue`) only carry just enough to render UI / metrics.

4. **Sequence numbers for streaming order**
   Responses uses `sequence_number` so clients can reconstruct the stream.
   ADE will use a `sequence` field with the same semantics.

5. **Narrow, semantic event types**
   Responses splits behaviour into many semantic types instead of one overloaded blob.
   ADE does the same: instead of a giant `run` bucket, we use specific types: `run.started`, `run.phase.started`, `run.table.summary`, `run.validation.summary`, etc.

### 1.2 ADE-specific goals

1. **One mental model**

   * One envelope (`ade.event/v1`) shared by engine, API, and streaming.
   * Build, run, and console events “feel” the same.

2. **Events are the source of truth**

   * Event stream (`events.ndjson` or SSE) is the **timeline**.
   * API builds a compact `run_summary` from events for UI & analytics.

3. **Flat, query-friendly fields**

   * IDs, statuses, and metrics are top-level when possible.
   * Only use nested objects for clear domain resources (e.g. `run_summary`, `table`, `validation_issue`), not generic `run/build/env` buckets.

4. **Console as first-class**

   * `console.line` is the standard stdout/stderr event shape across build and run (`payload.scope` distinguishes).

5. **Additive and versioned**

   * We add new event types and optional fields.
   * Breaking changes require schema/major version changes.

---

## 2. ADE event envelope

All ADE events share the same outer shape:

```jsonc
{
  "type": "console.line",               // primary discriminator
  "event_id": "evt_01JK3J0YRKJ...",
  "created_at": "2025-11-26T12:00:00Z",

  // ordering within a stream (optional but recommended)
  "sequence": 42,                       // monotonically increasing per run stream

  // correlation context (nullable when not applicable)
  "workspace_id": "ws_123",
  "configuration_id": "cfg_123",
  "build_id": "b_123",
  "run_id": "run_123",

  // event producer (optional)
  "source": "engine",                   // engine | api | worker-X | cli | web

  // event-specific payload
  "payload": {
    "scope": "run",
    "stream": "stdout",
    "message": "Installing engine…"
  }
}
```

Notes:

* **`type`**: always of the form `<subject>.<verb_or_noun>`, e.g.
  `console.line`, `run.started`, `run.table.summary`, `build.completed`.
* **`sequence`**:

  * Optional in persisted NDJSON (file order may be enough).
  * Strongly recommended in SSE streaming so clients can handle out-of-order delivery.
* **IDs**:

  * `workspace_id`, `configuration_id` provide tenant & config context.
  * `run_id` anchors events to one pipeline execution.
  * `build_id` anchors events to one environment build.

Everything else in the event is **type-specific payload**.

---

## 3. Event taxonomy

We organize ADE events into a small set of domains:

1. **Run lifecycle** (`run.*`)
2. **Build lifecycle** (`build.*`)
3. **Console / stdout events** (`console.line` with `scope`)
4. **Table & validation events** (`run.table.*`, `run.validation.*`)
5. **Job / queue events** (`job.*`) – optional, for the orchestrator
6. **Error events** (`error`) – stream-level failures

Below are the canonical types and payloads.

---

## 4. Run lifecycle events (`run.*`)

### 4.1 `run.queued`

API has accepted a run and put it in the queue.

```jsonc
{
  "type": "run.queued",
  "schema": "ade.event/v1",
  "created_at": "2025-11-26T12:00:00Z",
  "sequence": 1,

  "workspace_id": "ws_1",
  "configuration_id": "cfg_1",
  "job_id": "job_1",
  "run_id": "run_1",

  "status": "queued",                  // queued
  "mode": "execute",                   // execute | validate | preview
  "input_uri": "s3://bucket/input.xlsx",
  "requested_by": "user_123",
  "metadata": {
    "trigger": "ui"                    // ui | api | schedule | test
  }
}
```

### 4.2 `run.started`

Engine or worker has actually started processing the run.

```jsonc
{
  "type": "run.started",
  "schema": "ade.event/v1",
  "created_at": "2025-11-26T12:00:03Z",
  "sequence": 2,

  "workspace_id": "ws_1",
  "configuration_id": "cfg_1",
  "run_id": "run_1",

  "status": "in_progress",             // in_progress
  "mode": "execute",
  "input_uri": "s3://bucket/input.xlsx",
  "metadata": {
    "worker": "worker-7"
  }
}
```

### 4.3 `run.phase.started` / `run.phase.completed` (optional but useful)

Phases help with progress bars and understanding where time went.

```jsonc
{
  "type": "run.phase.started",
  "schema": "ade.event/v1",
  "created_at": "2025-11-26T12:00:05Z",
  "sequence": 3,

  "run_id": "run_1",

  "phase": "mapping",                  // ingest | detect_tables | mapping | validation | export
  "metadata": {
    "input_file": "input.xlsx"
  }
}
```

```jsonc
{
  "type": "run.phase.completed",
  "schema": "ade.event/v1",
  "created_at": "2025-11-26T12:02:10Z",
  "sequence": 10,

  "run_id": "run_1",

  "phase": "mapping",
  "duration_ms": 125000,
  "metrics": {
    "tables_mapped": 3,
    "rows_seen": 4821
  }
}
```

### 4.4 `run.completed`

Canonical “final state” for a run (from the API). This is the ADE analogue of `response.completed` / `response.failed` / `response.incomplete` rolled into one, with a `status` enum.

```jsonc
{
  "type": "run.completed",
  "schema": "ade.event/v1",
  "created_at": "2025-11-26T12:05:30Z",
  "sequence": 99,

  "workspace_id": "ws_1",
  "configuration_id": "cfg_1",
  "job_id": "job_1",
  "run_id": "run_1",

  "status": "succeeded",               // succeeded | failed | canceled | incomplete
  "mode": "execute",

  "execution": {
    "exit_code": 0,
    "duration_ms": 327000
  },

  "env": {
    "status": "active",                // active | failed | reused
    "reason": "force_rebuild"          // reuse_ok | digest_mismatch | engine_spec_mismatch | ...
  },

  "events_path": "s3://.../run_1/events.ndjson",
  "output_paths": [
    "s3://.../run_1/output.parquet"
  ],

  // Snapshot of aggregated results: ADE’s equivalent of a "resource" object
  "run_summary": {
    "schema": "ade.run_summary/v1",
    "version": "1.0.0",

    "core": {
      "tables_detected": 3,
      "tables_mapped": 3,
      "rows_seen": 4821,
      "rows_with_errors": 5
    },

    "by_file": [
      {
        "source_file": "input.xlsx",
        "tables_detected": 3,
        "rows_seen": 4821
      }
    ],

    "by_table": [
      {
        "table_id": "tbl_001",
        "source_file": "input.xlsx",
        "source_sheet": "Sheet1",
        "row_count": 4821,
        "issues_total": 5
      }
    ]
  },

  "error": null
}
```

For failed runs:

```jsonc
{
  "type": "run.completed",
  "status": "failed",
  "execution": { "exit_code": 1, "duration_ms": 5000 },
  "error": {
    "code": "missing_required_column",
    "message": "Column `email` not found in any detected table"
  }
}
```

The **run summary** is computed by the API from the engine’s `events.ndjson`, similar to how the Responses API infers final resource state from its own events.

---

## 5. Build lifecycle events (`build.*`)

Builds have a similar set of lifecycle events, but focused on environment creation and engine installation.

### 5.1 `build.created`

```jsonc
{
  "type": "build.created",
  "schema": "ade.event/v1",
  "created_at": "2025-11-26T11:50:00Z",
  "sequence": 1,

  "workspace_id": "ws_1",
  "configuration_id": "cfg_1",
  "build_id": "b_1",

  "status": "queued",                  // queued
  "reason": "force_rebuild",           // reuse_ok | missing_env | force_rebuild | ...
  "metadata": {
    "requested_by": "user_123"
  }
}
```

### 5.2 `build.started`

```jsonc
{
  "type": "build.started",
  "schema": "ade.event/v1",
  "created_at": "2025-11-26T11:50:05Z",
  "sequence": 2,

  "workspace_id": "ws_1",
  "configuration_id": "cfg_1",
  "build_id": "b_1",

  "status": "in_progress"
}
```

### 5.3 `build.phase.started` / `build.phase.completed` (optional)

```jsonc
{
  "type": "build.phase.started",
  "schema": "ade.event/v1",
  "created_at": "2025-11-26T11:50:06Z",
  "sequence": 3,

  "build_id": "b_1",

  "phase": "create_venv",              // create_venv | upgrade_pip | install_engine | install_config | verify_imports
  "metadata": {}
}
```

### 5.4 `build.completed`

```jsonc
{
  "type": "build.completed",
  "schema": "ade.event/v1",
  "created_at": "2025-11-26T11:52:00Z",
  "sequence": 20,

  "workspace_id": "ws_1",
  "configuration_id": "cfg_1",
  "build_id": "b_1",

  "status": "active",                   // active | failed | canceled
  "duration_ms": 115000,

  "env": {
    "reason": "force_rebuild",
    "python_version": "3.11.8",
    "engine_version": "0.2.0"
  },

  "error": null
}
```

If the build fails:

```jsonc
{
  "type": "build.completed",
  "status": "failed",
  "error": {
    "code": "pip_error",
    "message": "Could not find a version that satisfies the requirement ade-engine==0.2.0"
  }
}
```

---

## 6. Console / stdout events (`console.line`)

Console events are ADE’s analogue to “stdout lines” and replace older shapes like `run.console` / `build.console`.

```jsonc
{
  "type": "console.line",
  "created_at": "2025-11-26T12:01:00Z",
  "sequence": 5,

  "workspace_id": "ws_1",
  "configuration_id": "cfg_1",
  "run_id": "run_1",
  "build_id": "b_1",

  "payload": {
    "scope": "run",                      // "run" | "build"
    "stream": "stdout",                  // stdout | stderr
    "level": "info",                     // info | warning | error | success | debug
    "message": "Mapping complete (tables=3, rows=4821)",
    "phase": "mapping",                  // optional
    "details": {
      "mapped": 12,
      "unmapped": 2
    }
  }
}
```

**Frontend rule of thumb:**

* Treat `console.line` events as **ordered console lines**; rely on `sequence` for ordering when present.
* Use `payload.scope` to split build vs run output in the UI.

---

## 7. Table & validation events (`run.table.*`, `run.validation.*`)

These events are the ADE version of the more granular Responses events like `response.output_item.added`, `response.output_text.delta`, etc. They let you build rich UIs without waiting for `run.completed`.

### 7.1 `run.table.summary`

Per-table summary (row counts, mapping stats, validation summary).

```jsonc
{
  "type": "run.table.summary",
  "schema": "ade.event/v1",
  "created_at": "2025-11-26T12:03:10Z",
  "sequence": 30,

  "workspace_id": "ws_1",
  "configuration_id": "cfg_1",
  "run_id": "run_1",

  "table_id": "tbl_001",
  "source_file": "input.xlsx",
  "source_sheet": "Sheet1",
  "table_index": 0,                     // 0-based

  "row_count": 4821,
  "column_count": 17,

  "mapped_fields": ["email", "created_at", "first_name"],
  "unmapped_column_count": 2,

  "validation": {
    "issues_total": 5,
    "issues_by_code": {
      "missing_email": 3,
      "bad_date": 2
    },
    "max_severity": "warning"         // info | warning | error
  },

  "details": {
    "header_row": 1,
    "data_range": "A1:Q4822"
  }
}
```

The front-end’s “table list” panel can be built incrementally from these events.

### 7.2 `run.validation.issue` (optional, for fine-grained UX)

Stream per-row/per-field issues, similar to how Responses streams deltas:

```jsonc
{
  "type": "run.validation.issue",
  "schema": "ade.event/v1",
  "created_at": "2025-11-26T12:03:12Z",
  "sequence": 31,

  "run_id": "run_1",
  "table_id": "tbl_001",

  "code": "missing_email",
  "severity": "warning",
  "message": "Email is required but missing",

  "row_index": 123,                     // 0-based, or raw row number
  "column": "email",

  "details": {
    "raw_value": "",
    "record_id": "rec_9aa2"
  }
}
```

This powers a streaming “Issues” panel while the run is still executing.

### 7.3 `run.validation.summary`

Final aggregated validation metrics for the whole run (useful especially for validation-only mode):

```jsonc
{
  "type": "run.validation.summary",
  "schema": "ade.event/v1",
  "created_at": "2025-11-26T12:04:00Z",
  "sequence": 60,

  "run_id": "run_1",

  "issues_total": 5,
  "issues_by_code": {
    "missing_email": 3,
    "bad_date": 2
  },
  "issues_by_severity": {
    "warning": 5
  }
}
```

---

## 8. Job / queue events (`job.*`) – optional

If the orchestrator is exposed via SSE, we may also define:

```jsonc
{
  "type": "job.queued",
  "schema": "ade.event/v1",
  "created_at": "2025-11-26T11:59:00Z",
  "sequence": 1,

  "workspace_id": "ws_1",
  "configuration_id": "cfg_1",
  "job_id": "job_1",

  "status": "queued"
}
```

```jsonc
{
  "type": "job.started",
  "schema": "ade.event/v1",
  "created_at": "2025-11-26T11:59:05Z",
  "sequence": 2,

  "job_id": "job_1",
  "run_id": "run_1",
  "build_id": "b_1"
}
```

```jsonc
{
  "type": "job.completed",
  "schema": "ade.event/v1",
  "created_at": "2025-11-26T12:05:35Z",
  "sequence": 100,

  "job_id": "job_1",
  "status": "succeeded",              // succeeded | failed | canceled
  "error": null
}
```

These are optional; they’re mainly useful for a “queue” view or admin tooling.

---

## 9. Error events (`error`)

In addition to run/build `status: failed`, we keep a dedicated `error` event type for transport- or stream-level failures (similar to the Responses `error` event):

```jsonc
{
  "type": "error",
  "schema": "ade.event/v1",
  "created_at": "2025-11-26T12:00:10Z",
  "sequence": 999,

  "code": "INTERNAL_STREAM_ERROR",
  "message": "Upstream worker disconnected unexpectedly",
  "param": null
}
```

This is not tied to a particular `run_id` or `build_id` and should be treated as “the stream itself is in trouble”.

---

## 10. Streaming vs persistence

### 10.1 Engine responsibilities

The engine:

* accepts a `RunRequest`,
* emits `ade.event/v1` JSON lines to `events.ndjson`:

  * `console.line`, `run.phase.*`, `run.table.summary`, `run.validation.*`, `run.completed` (engine’s view),
* exits with an appropriate process exit code.

The engine doesn’t need to know:

* workspace IDs,
* configuration IDs,
* DB schema.

It can propagate opaque identifiers (like `run_id`) passed in via the request.

### 10.2 API responsibilities

The API:

* evaluates env / build needs,
* emits `build.*` events,
* spawns the engine and streams engine events to clients (possibly with additional `run.*` wrapper events),
* reads `events.ndjson` on completion,
* computes `run_summary` and emits **one canonical** `run.completed` event (see 4.4),
* persists run and build summaries into SQL tables.

### 10.3 Where things live

* **Raw events**: `events.ndjson` (or object storage) – complete timeline.
* **SQL**:

  * `runs` – identity, status, timestamps, and a denormalized slice of `run_summary.core`.
  * optional `run_table_metrics` / `run_field_metrics` – exploded breakdowns.
  * `builds` – build identity, status, env reason, durations.

---

## 11. Versioning and evolution

The event model is versioned via:

* `schema`: `"ade.event/v1"`,
* `version`: `"1.0.0"`.

### 11.1 Allowed (non-breaking) changes

* Adding new **event types**, e.g. `run.metrics` or `run.phase.started`.
* Adding new **optional fields** to existing event types.
* Extending `run_summary` with new fields while preserving existing ones.

### 11.2 Breaking changes

Examples:

* Removing or renaming fields in an event type.
* Changing the semantics of an existing field (e.g. status values).
* Changing the shape of `run_summary` in incompatible ways.

Breaking changes require:

* a new `schema` name (e.g. `"ade.event/v2"`) **or**
* a major `version` bump with a compatibility plan.

---

## 12. Summary

* ADE’s event model adopts the **Responses-style** approach:

  * `type`-driven events,
  * small, focused payloads,
  * optional resource snapshots (`run_summary`) for lifecycle events,
  * `sequence` numbers for streaming order.
* Console events are standardized as `console.line` with `scope`.
* Table and validation events are first-class, enabling rich UIs without waiting for `run.completed`.
* Raw events are the **timeline**; `run_summary` and SQL tables are the **dashboard** built on top.

This document is the canonical reference for how `ade-engine`, `ade-api`, and front-ends should emit, consume, and persist ADE events.
