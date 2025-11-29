# Event Log Storage - DB vs Files

This doc answers:

- **Where** we persist event logs (DB or files?).
- **What** the frontend actually needs from storage.
- **How** we keep performance and footprint sane over time.

This builds on the event model in `020-EVENT-TYPES-REFERENCE.md` and the API surface in `030-API-DESIGN-RUNS-AND-BUILDS.md`.

---

## 1. Requirements

### 1.1 Functional

We need to:

- Stream events live to the frontend while a run is in progress.
- Later:
  - Rebuild the **run summary** for auditing/debugging.
  - Replay the event stream (e.g., on reload or from a run details page).
- Keep a **compact representation** of run status in the DB for:
  - "Runs list" views.
  - Simple filters (status, time, workspace/config).

### 1.2 Non-functional

- Writes should be **append-only** and cheap.
- Reads for replay should be **streaming**, not load-the-whole-world.
- DB size must remain **bounded** even as we accumulate many runs.
- The solution should feel like a **standard practice**:
  - Similar to how job systems, CI pipelines, and LLM providers handle logs.

---

## 2. Standard pattern: DB for metadata, files for logs

We follow the conventional split:

1. **Database** (Postgres, etc.):
   - Store **run metadata and summary**:
     - `run_id`, `workspace_id`, `configuration_id`, status, timestamps, exit code, etc.
     - `summary_json` (RunSummary snapshot from `run.completed`).
     - Pointers to artifacts:
       - `events_path` (where NDJSON lives).
       - `output_paths` (normalized workbook, etc.).
   - Possibly a **few small derived fields** for fast filtering:
     - total rows, total tables, max severity, etc.

2. **File/object storage** (local disk, S3, GCS, etc.):
   - Store **full event logs** as **NDJSON**:
     - One file per run: `events.ndjson`.
     - One JSON object per line: each is an `AdeEvent` envelope.
   - Optional rotation/compression for long-term retention.

This is the same pattern used by most serious systems (CI/CD, log systems, LLM introspection APIs): DB for **index/summary**, files for **logs and streams**.

---

## 3. Why not store events in the DB?

Storing every event as a DB row has issues:

- **Volume**:
  - A single run could easily produce thousands of events:
    - `console.line` for each line.
    - `run.validation.issue` for each issue.
  - Multiply by many runs -> millions of rows.
- **Write path**:
  - Every console line becomes an INSERT.
  - Adds lock contention and overhead on the main DB.
- **Query pattern**:
  - UI almost always needs a **simple, sequential replay** (streaming).
  - We rarely need "search logs across all runs" in the DB itself.
  - If we want full-text log search, a dedicated log index (e.g., ES, OpenSearch) would be a separate concern.

Conclusion: DB is **not** a good fit for full event history. Use it for **summaries and pointers**, not raw event lines.

---

## 4. Final storage design

### 4.1 Event log layout

For each run:

- NDJSON file:
  - Path pattern (example):

    ```text
    {storage_root}/workspaces/{workspace_id}/runs/{run_id}/logs/events.ndjson
    ```

  - Contents:

    ```text
    {"type":"run.queued",...}
    {"type":"build.created",...}
    {"type":"build.started",...}
    {"type":"console.line",...}
    ...
    {"type":"run.completed",...}
    ```

- Optional compression:
  - We can:
    - Keep it as plain text while the run is "recent".
    - Move old logs to compressed storage (e.g., `events.ndjson.gz`) after N days.
  - API code for replay should be written to:
    - Handle plain NDJSON first.
    - Later, we can add decompression without changing the envelope or frontend.

### 4.2 DB schema (conceptual)

In the `runs` table, add/ensure:

- Core fields:
  - `id` (`run_id`)
  - `workspace_id`
  - `configuration_id`
  - `status` (`queued|building|running|succeeded|failed|cancelled`)
  - `exit_code` (nullable)
  - `created_at`, `started_at`, `completed_at`
- Summary:
  - `summary_json` (JSON or JSONB) - the snapshot from `run.completed.payload.summary`.
- Artifact pointers:
  - `events_path` - string (e.g., S3 URI or local path to `events.ndjson`).
  - `output_paths` - JSON array of artifact paths.
- Light derived fields (optional, for fast filters):
  - `input_file_count`
  - `table_count`
  - `row_count`
  - `max_validation_severity` (enum / small int)

We do **not** store the full event stream in the DB. At most, we might store a **truncated tail** of console output as a convenience field (e.g. `last_console_snippet`) but that is optional.

---

## 5. How frontend uses stored logs

### 5.1 Live runs

For live runs:

- Frontend uses **SSE** from:
  - `POST /.../runs?stream=true` (advanced) or
  - `GET /.../runs/{run_id}/events?stream=true` (recommended for UI; see `070-FRONTEND-STREAMING.md`).
- SSE is backed by:
  - An in-memory subscriber queue.
  - The same **NDJSON append** that writes `events.ndjson`.

So:

- Write path: `emit_event` -> append to NDJSON + fan-out to subscribers.
- Read path (live): subscribers get events as they are emitted.

### 5.2 Replays / non-live views

For non-live views (e.g., run details screen opened later):

- Frontend typically does:

  1. `GET /.../runs/{run_id}` -> summary + metadata.
  2. Optionally, `GET /.../runs/{run_id}/events?stream=true`:
     - With `from_sequence=1` to get a replay in SSE form.
     - Or `GET /.../events` with `Accept: application/x-ndjson` to download the log.

- Under the hood, API:
  - Reads `events.ndjson` sequentially.
  - Streams them as AdeEvents back over SSE or NDJSON.

This keeps the DB out of the hot path for log replay and uses cheap streaming from file/object storage.

---

## 6. Performance considerations

### 6.1 Writes

- Append-only NDJSON:
  - No random I/O.
  - Easy to buffer (e.g., flush every N events or every X ms).
- `emit_event` does not block on heavy operations:
  - Append to file.
  - Push to in-memory queues.
  - If writes fail:
    - Run can still continue but we log/metric and possibly mark run as "logging degraded".

### 6.2 Reads

- SSE and NDJSON responses are **streamed**:
  - API reads chunks of the file and pushes them out.
  - It does not need to load entire logs into memory.
- Summary building (`RunSummaryBuilder`):
  - Iterates over the same NDJSON file.
  - Typically only needs to run once per completed run.

### 6.3 Retention and DB size

- DB size stays bounded because:
  - Only summaries and metadata are stored.
  - Event logs accumulate in object/file storage where:
    - We can define **retention policies** (delete after N days).
    - We can compress or archive old logs.
- If we later want:
  - Log search index (Elasticsearch, etc.), we can ingest NDJSON offline.
  - That is a separate concern from the DB.

---

## 7. Final decision

- **Events are persisted as NDJSON files** per run (append-only).
- **DB holds run metadata, summary, and pointers**, not the full event stream.
- Frontend:
  - Uses SSE for **live** consumption.
  - Uses replay SSE/NDJSON for **historical** runs.
- This aligns with common, battle-tested patterns and keeps the core DB lean and performant.
