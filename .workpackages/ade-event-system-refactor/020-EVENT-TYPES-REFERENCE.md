# Event Types - Current vs New

This document defines:

1. The **canonical event envelope** (`AdeEvent`).
2. The **final set of event types** and their payloads.
3. A **migration table** mapping *current (v1)* events to *new* ones.

We are **not** keeping backwards compatibility. v1 events and schemas will be removed as part of this work.

---

## 1. Canonical envelope (`AdeEvent`)

Every event in the system is an `AdeEvent` with:

```jsonc
{
  "type": "run.phase.started",         // event type string
  "event_id": "evt_01JK3J0YRKJ...",    // globally unique
  "created_at": "2025-11-28T18:52:57.802612Z",  // ISO-8601 UTC
  "sequence": 23,                      // monotonic per run_id

  "source": "engine",                  // "api" | "engine" | "scheduler" | "worker"

  "workspace_id": "01KB4X3NBV07JBJS92MA5A1TSC",
  "configuration_id": "01KB4X3XK9GTZCVJ2E8DQRY910",
  "run_id": "run_01JK3HXPQKZ4P6RZ3BET8ESZ1T",
  "build_id": "build_01JK3HXRRTKPM3M3G7AQ23SCV7",

  "payload": { /* type-specific fields */ }
}
```

**Rules:**

* `event_id` and `sequence` are assigned **only by ade-api**.
* `sequence` is monotonic per `run_id`:

  * Includes **both** build and run events.
* `build_id`:

  * Present for all build events; optional for run events.
* Error details live in **payloads**, not in an envelope-level `error` field.

---

## 2. Final event types and payloads

### 2.1 Build lifecycle

#### `build.created` (kept, payload refined)

Emitted by ade-api when deciding which build to use for a run.

```jsonc
{
  "type": "build.created",
  "payload": {
    "status": "queued",                     // always "queued"
    "reason": "force_rebuild",              // "force_rebuild" | "cache_miss" | "cache_hit" | "manual"
    "engine_spec": "apps/ade-engine",
    "engine_version_hint": "0.2.0",
    "python_bin": "/usr/bin/python3.11",
    "should_build": true                    // false if we know we will reuse
  }
}
```

Replaces v1 `build.created` with slightly cleaned reason values and guarantees.

---

#### `build.started` (kept, payload refined)

```jsonc
{
  "type": "build.started",
  "payload": {
    "status": "building",             // always "building"
    "reason": "force_rebuild"
  }
}
```

---

#### `build.phase.started` (kept)

```jsonc
{
  "type": "build.phase.started",
  "payload": {
    "phase": "install_engine",        // "create_venv" | "upgrade_pip" | "install_engine" | "install_config" | "verify_imports" | "collect_metadata"
    "message": "Installing engine: apps/ade-engine"
  }
}
```

---

#### `build.phase.completed` (**new**)

New in this design; gives per-phase duration and outcome.

```jsonc
{
  "type": "build.phase.completed",
  "payload": {
    "phase": "install_engine",
    "status": "succeeded",            // "succeeded" | "failed" | "skipped"
    "duration_ms": 2450,
    "message": "Engine installed"
  }
}
```

---

#### `build.completed` (kept, payload refined)

```jsonc
{
  "type": "build.completed",
  "payload": {
    "status": "succeeded",            // "succeeded" | "failed" | "reused" | "skipped"
    "exit_code": 0,
    "summary": "Build succeeded",
    "duration_ms": 12238,
    "env": {
      "reason": "force_rebuild",      // "force_rebuild" | "cache_hit" | "cache_miss" | "manual"
      "reused": false
    },
    "error": null                     // or { "code": "PIP_INSTALL_FAILED", "message": "...", "details": {...} }
  }
}
```

---

### 2.2 Run lifecycle

#### `run.queued` (kept, payload refined)

Emitted by ade-api when the run is created and enqueued.

```jsonc
{
  "type": "run.queued",
  "payload": {
    "status": "queued",
    "mode": "execute",                 // "execute" | "validate_only" | "dry_run"
    "options": {
      "document_ids": ["doc_..."],
      "input_sheet_names": ["Sheet1"],
      "force_rebuild": true,
      "dry_run": false,
      "validate_only": false
    },
    "queued_by": {
      "user_id": "usr_123",
      "email": "user@example.com"
    }
  }
}
```

Replaces v1 `run.queued` payload (naming tweaks; extended options).

---

#### `run.started` (kept, unified; engine version folded in)

One canonical event, **emitted by ade-api** when the run is truly starting (build done or skipped).

```jsonc
{
  "type": "run.started",
  "payload": {
    "status": "in_progress",
    "mode": "execute",
    "engine_version": "0.2.0",
    "config_version": "0.2.0",
    "env": {
      "reason": "force_rebuild",
      "reused": false
    }
  }
}
```

* v1 had:

  * `run.started` from API for validate-only paths.
  * `run.started` from engine with `engine_version`.
* In the new system:

  * Only **one** `run.started` per run.
  * Engine no longer emits a public `run.started` event.

---

#### `run.phase.started` (kept)

Emitted by engine to mark logical phases.

```jsonc
{
  "type": "run.phase.started",
  "payload": {
    "phase": "extracting",            // "extracting" | "mapping" | "normalizing" | "validating" | "writing_output" | custom
    "message": "Extracting tables from input"
  }
}
```

---

#### `run.phase.completed` (**new**)

```jsonc
{
  "type": "run.phase.completed",
  "payload": {
    "phase": "extracting",
    "status": "succeeded",            // "succeeded" | "failed" | "skipped"
    "duration_ms": 350,
    "message": "Finished extract phase",
    "metrics": {
      "table_count": 2,
      "row_count": 2646
    }
  }
}
```

---

#### `run.completed` (kept, but **canonicalized**)

Exactly **one** per run, emitted by ade-api when everything is done (including summary).

```jsonc
{
  "type": "run.completed",
  "payload": {
    "status": "succeeded",            // "succeeded" | "failed" | "cancelled"
    "failure": {
      "code": null,                   // e.g. "build_failed", "engine_error"
      "stage": null,                  // "build" | "run" | "validation" | null
      "message": null
    },
    "execution": {
      "exit_code": 0,
      "started_at": "2025-11-28T18:52:57.397955Z",
      "completed_at": "2025-11-28T18:52:58.538808Z",
      "duration_ms": 1141
    },
    "artifacts": {
      "output_paths": [
        "s3://.../runs/run_.../output/normalized.xlsx"
      ],
      "events_path": "s3://.../runs/run_.../logs/events.ndjson"
    },
    "summary": {
      /* See RunSummary in 020-EVENT-TYPES-REFERENCE or RunSummaryBuilder implementation */
    }
  }
}
```

* Replaces:

  * API `run.completed` (v1) with smaller payload.
  * Engine `run.completed` (v1) with `output_paths`, `events_path`.
* New system:

  * Engine may emit an internal "engine finished" indicator, but **only API** emits public `run.completed`.

---

### 2.3 Logging

#### `console.line` (**new; replaces build.console + run.console + engine run.console**)

```jsonc
{
  "type": "console.line",
  "payload": {
    "scope": "run",                    // "build" | "run"
    "stream": "stdout",                // "stdout" | "stderr"
    "level": "info",                   // "debug" | "info" | "warn" | "error"
    "phase": "extracting",             // optional
    "message": "Successfully installed ade-engine-0.2.0",
    "logger": "ade.engine.extract",    // optional
    "engine_timestamp": 1764384774     // optional numeric or ISO ts
  }
}
```

* See `090-CONSOLE-LOGGING.md` for how subprocess stdout/stderr get turned into these events.
* v1 `build.console` and `run.console` are **removed**; fronts ends now just filter `type === "console.line"` and `scope` for build vs run.

---

### 2.4 Table and validation

#### `run.table.summary` (kept; payload refined)

One per logical table per run.

```jsonc
{
  "type": "run.table.summary",
  "payload": {
    "table_id": "tbl_6F12A_0_0",
    "source_file": "s3://.../Ledcor.xlsx",
    "source_sheet": "Sheet1",
    "file_index": 0,
    "sheet_index": 0,
    "table_index": 0,

    "row_count": 1323,
    "column_count": 50,

    "mapping": {
      "mapped_columns": [
        {
          "field": "member_id",
          "header": "",
          "source_column_index": -1,
          "score": 0.0,
          "is_required": true,
          "is_satisfied": false
        },
        {
          "field": "first_name",
          "header": "First Name",
          "source_column_index": 6,
          "score": 0.9,
          "is_required": false,
          "is_satisfied": true
        }
      ],
      "unmapped_columns": [
        {
          "header": "Co.",
          "source_column_index": 0,
          "output_header": "raw_1"
        }
      ]
    },

    "validation": {
      "issues_total": 0,
      "issues_by_severity": {},
      "issues_by_code": {},
      "issues_by_field": {},
      "max_severity": null
    },

    "metadata": {
      "header_row": 4,
      "first_data_row": 5,
      "last_data_row": 1327
    }
  }
}
```

Notes:

* v1 shape is very similar; we are mainly tightening names and guarantees.
* Guarantee: at most one `run.table.summary` per `table_id` per run.

---

#### `run.validation.issue` (kept, clarified)

We keep this as an **optional, high-volume** event for detailed debugging.

```jsonc
{
  "type": "run.validation.issue",
  "payload": {
    // arbitrary validation issue structure:
    "severity": "warning",
    "code": "missing_required_field",
    "field": "member_id",
    "row": 27,
    "message": "member_id is required"
  }
}
```

* These are **not required** for summary computation (we use `run.validation.summary` and `run.table.summary`).
* They are useful for fine-grained debugging, but UI does not have to render them all.

---

#### `run.validation.summary` (kept; payload clarified)

```jsonc
{
  "type": "run.validation.summary",
  "payload": {
    "issues_total": 0,
    "issues_by_severity": {},
    "issues_by_code": {},
    "issues_by_field": {},
    "max_severity": null
  }
}
```

---

### 2.5 Error

#### `run.error` (**new**)

Adds structured context around failures; complements `run.completed`.

```jsonc
{
  "type": "run.error",
  "payload": {
    "stage": "build",                  // "build" | "run" | "validation" | ...
    "phase": "install_engine",         // optional
    "code": "PIP_INSTALL_FAILED",
    "message": "pip exited with code 1 while installing apps/ade-engine",
    "details": {
      "exit_code": 1,
      "last_lines": [
        "ERROR: Could not build wheels..."
      ]
    }
  }
}
```

---

## 3. Migration table (v1 -> new)

| v1 Event                   | New Event / Status                        | Notes                                                                                |
| -------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------ |
| `build.created`            | **Kept**, payload refined                 | Same name; refined `reason` values and `should_build` semantics.                     |
| `build.started`            | **Kept**, payload refined                 | Same name; simplified payload.                                                       |
| `build.phase.started`      | **Kept**                                  | Same semantics; plus we now also emit `build.phase.completed`.                       |
| `build.console`            | **Removed** -> `console.line`              | Use `console.line` with `scope:"build"`; see 090-CONSOLE-LOGGING.                    |
| `build.completed`          | **Kept**, payload refined                 | Adds `env.reused` and normalized `status` values.                                    |
| `run.queued` (api)         | **Kept**, payload refined                 | Mode/option shape simplified; still first run event.                                 |
| `run.started` (api)        | **Merged** into new `run.started`         | API emits the canonical `run.started`.                                               |
| `run.started` (engine)     | **Removed (public)**                      | Engine no longer emits a public `run.started`; info folded into API's `run.started`. |
| `run.console` (api)        | **Removed** -> `console.line`              | Use `console.line` with `scope:"run"`.                                               |
| `run.console` (engine)     | **Removed** -> `console.line`              | Same; engine logs map to `console.line`.                                             |
| `run.completed` (api)      | **Replaced** by canonical `run.completed` | New payload with execution, artifacts, summary.                                      |
| `run.completed` (engine)   | **Removed (public)**                      | Engine may send internal indicator; API-only public `run.completed`.                 |
| `run.phase.started`        | **Kept**                                  | Same; now paired with `run.phase.completed`.                                         |
| `run.table.summary`        | **Kept**, payload refined                 | Slightly standardized across fields.                                                 |
| `run.validation.issue`     | **Kept (optional)**                       | High-volume debug event; not required for summaries.                                 |
| `run.validation.summary`   | **Kept**, payload clarified               | Same concept, better naming.                                                         |
| Envelope `details`/`error` | **Removed**                               | Use event-specific payloads and `run.error`/`run.completed.payload.failure` instead. |
| `console.line`             | **New**                                   | Unified logging event for all logs (build+run, api+engine).                          |
| `build.phase.completed`    | **New**                                   | Per-phase completion; durations and status.                                          |
| `run.phase.completed`      | **New**                                   | Per-phase completion; durations and metrics.                                         |
| `run.error`                | **New**                                   | Standalone error context event.                                                      |

This table is the ground truth when cleaning up v1 code:

* Anything under "Removed" should eventually **not appear anywhere** in ade-api, ade-engine, or ade-web.
