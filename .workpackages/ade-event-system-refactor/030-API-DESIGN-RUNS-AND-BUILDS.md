# API Design - Runs and Builds (Streaming Included)

This doc answers: "What is the most intuitive way for developers to create a run and stream its events?"

We standardize on:

- **Runs** as the primary unit.
- **One event stream per run** (including build and run).
- **SSE** for live streaming (`text/event-stream`).
- **NDJSON** for storage/offline replay.

There is **no `/v2`**; these semantics **replace** the existing v1 endpoints.

---

## 1. Endpoints - Overview

### 1.1 Create a run (with optional streaming)

```http
POST /workspaces/{workspace_id}/configurations/{configuration_id}/runs?stream={true|false}
Content-Type: application/json
```

* `stream=false` (default):

  * Returns JSON with `run_id` and status; client can poll or attach later.
* `stream=true`:

  * Starts the run and streams events via **SSE**:

    * `Content-Type: text/event-stream`
    * Each SSE message has `id: <sequence>`, `event: ade.event`, `data: {<AdeEvent>}`.

---

### 1.2 Get run metadata and summary

```http
GET /workspaces/{workspace_id}/configurations/{configuration_id}/runs/{run_id}
Accept: application/json
```

Returns:

```jsonc
{
  "run": {
    "id": "run_...",
    "workspace_id": "01KB4X3NBV07JBJS92MA5A1TSC",
    "configuration_id": "01KB4X3XK9GTZCVJ2E8DQRY910",
    "status": "succeeded",
    "created_at": "2025-11-28T18:52:57.397955Z",
    "updated_at": "2025-11-28T18:52:58.538808Z"
  },
  "summary": { /* RunSummary (see event spec) */ }
}
```

---

### 1.3 Stream events for an existing run

```http
GET /workspaces/{workspace_id}/configurations/{configuration_id}/runs/{run_id}/events?stream=true&after_sequence={n}
Accept: text/event-stream
```

* `after_sequence` (optional):

  * If provided, server replays events with `sequence > after_sequence`, then streams new ones.

* Server uses SSE semantics:

  ```text
  id: 23
  event: ade.event
  data: {"type":"run.phase.started",...}

  id: 24
  event: ade.event
  data: {"type":"console.line",...}
  ```

* If client reconnects with `Last-Event-ID: 24`, server resumes from `sequence = 25` (or respects an explicit `after_sequence` if provided).
  * Prefer `after_sequence` query; `Last-Event-ID` is fallback.

---

### 1.4 Fetch event log (offline / NDJSON)

```http
GET /workspaces/{workspace_id}/configurations/{configuration_id}/runs/{run_id}/events
Accept: application/x-ndjson
```

Returns `events.ndjson` as-is:

```text
{"type":"run.queued",...}
{"type":"build.created",...}
...
{"type":"run.completed",...}
```

Alternative JSON mode (paged):

```http
GET /.../runs/{run_id}/events?after_sequence=0&limit=500
Accept: application/json
```

```jsonc
{
  "events": [ { /* AdeEvent */ }, ... ],
  "next_after_sequence": 500
}
```

---

### 1.5 Build endpoint (secondary)

We **keep** a dedicated build endpoint for advanced use but align it to the new system.

```http
POST /workspaces/{workspace_id}/configurations/{configuration_id}/builds?stream={true|false}
Content-Type: application/json
```

**Key behaviors:**

* `stream=false`:

  * Returns a `build_id` and basic build info.
* `stream=true`:

  * Returns SSE of **build-only** events (`build.*`, `console.line` with `scope:"build"`).
* Internally:

  * Still uses the same event dispatcher and NDJSON logging.
  * This is effectively a "run in build-only mode," but we do not expose an artificial run concept in the API.

---

## 2. Request and response examples

### 2.1 Create and stream run (primary UX)

**Request**

```http
POST /workspaces/w_123/configurations/c_456/runs?stream=true
Content-Type: application/json
Accept: text/event-stream

{
  "mode": "execute",
  "document_ids": ["doc_001"],
  "input_sheet_names": ["Sheet1"],
  "force_rebuild": true
}
```

**Response (SSE)**

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
```

Body:

```text
id: 1
event: ade.event
data: {"type":"run.queued", ...}

id: 2
event: ade.event
data: {"type":"build.created", ...}

id: 3
event: ade.event
data: {"type":"build.started", ...}

id: 4
event: ade.event
data: {"type":"build.phase.started","payload":{"phase":"create_venv","message":"Creating venv..."}}

...

id: 9
event: ade.event
data: {"type":"build.completed", ...}

id: 10
event: ade.event
data: {"type":"console.line","payload":{"scope":"run","message":"Configuration build completed; starting ADE run.", ...}}

...

id: 25
event: ade.event
data: {"type":"run.table.summary", ...}

...

id: 42
event: ade.event
data: {"type":"run.completed", ...}
```

---

### 2.2 Create run without streaming

```http
POST /workspaces/w_123/configurations/c_456/runs
Content-Type: application/json
Accept: application/json
```

Response:

```jsonc
{
  "run_id": "run_01JK3HXPQKZ4P6RZ3BET8ESZ1T",
  "status": "queued"
}
```

Client can then either:

* Attach SSE: `GET /.../runs/{run_id}/events?stream=true`
* Poll: `GET /.../runs/{run_id}` until `status` is terminal.

---

## 3. Developer experience (inspired by OpenAI-style APIs)

* **Single primary entry point**:

  * "I want to run this configuration" -> `POST /runs` with `stream: true/false`.
* **Background job feel**:

  * Non-streaming `POST /runs` is akin to "create job"; you later `GET /runs/{run_id}` or `GET /runs/{run_id}/events`.
* **Streaming is a flag, not a different resource**:

  * Exactly like `stream: true` in modern LLM APIs.
* **Events as the API's lingua franca**:

  * Everything, including build, is just AdeEvents.
  * Clients can choose how deep they want to go (e.g. just watch `run.completed` or show full `console.line`).

This API design is what everything else in the work package builds on.
