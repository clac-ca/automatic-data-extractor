Below is the research compiled by using an advanced AI research agent (GPT-5.2 Pro with web search)

---

# Real-time Documents Library Updates (SSE/WebSocket + Delta Feed)

> **Status:** Research/design doc (intended for planning + implementation)  
> **Audience:** Backend + Frontend engineers, and AI agents generating/implementing work packages  
> **Repo file:** `research.md`  
> **Primary goal:** Make the Documents table update “near real time” while keeping **filtering + pagination server-side**, handling **deletes**, and staying **efficient** under high churn.

---

## Table of contents

1. [Context: current system](#context-current-system)
2. [Problem statement](#problem-statement)
3. [What “big systems” usually do](#what-big-systems-usually-do)
4. [Recommended target architecture](#recommended-target-architecture)
5. [API design](#api-design)
6. [Event model](#event-model)
7. [Database design](#database-design)
8. [Event emission: where changes come from](#event-emission-where-changes-come-from)
9. [Backend implementation (FastAPI)](#backend-implementation-fastapi)
10. [Frontend implementation (React/Vite)](#frontend-implementation-reactvite)
11. [Pagination + real-time: UX rules that don’t feel haunted](#pagination--real-time-ux-rules-that-dont-feel-haunted)
12. [Performance, scaling, and failure modes](#performance-scaling-and-failure-modes)
13. [Testing plan](#testing-plan)
14. [Observability](#observability)
15. [Implementation checklist](#implementation-checklist)
16. [References](#references)

---

## Context: current system

### Canonical data model (pre-refactor)

- **Documents are `files` rows where `kind='document'`**. That row is the canonical record (metadata, tags, assignee, version, etc.).
- Document bytes live in `file_versions`. `files.current_version_id` points to the active version.
- `runs` reference `file_versions` as input/output and can update document state. Run inserts/updates currently trigger document change notifications.

### Current Documents screen behavior

Frontend route:

- `http://localhost:5173/workspaces/{workspace_id}/documents`

Behavior:

- A **server-driven, cursor-paginated** list of document rows.
- All **filters/sort/search** are persisted in the URL (shareable/reload-safe).
- Changing filters updates the URL and triggers a new server query.
- The UI renders **only the current page**.

### Current List API (important constraints)

You already have a rich server-side filter/sort system:

- Cursor pagination: `limit`, `cursor`
- `sort` = JSON array of `{id, desc}`
- `filters` = JSON array of `{id, operator, value}`
- `joinOperator` = `and` | `or`
- `q` = free-text search (tokenized)
- Optional extras: totals, facets, run metrics, run fields, run table columns

This design is good and should remain the source of truth for “what’s in the list”.

---

## Problem statement

We want the Documents table to **update in near real time** when:

- A document row changes (name, tags, assignee, size, version, etc.)
- A run changes the displayed state (e.g., `lastRunPhase`, `activityAt`, `hasOutput`, metrics)
- A document is **deleted** (it should be removed from the UI)
- A document is updated such that it **enters** the current filter (it should appear) or **leaves** the filter (it should disappear)

Constraints:

- Filtering must remain **server-side**.
- Pagination must remain **cursor-based** and stable.
- There may be **lots of documents changing** (run processing bursts).
- Must be efficient: avoid refetching the entire page on every tiny update.

---

## What “big systems” usually do

### The core pattern: **push says “something changed”, pull gets “what changed”**

At scale, systems avoid maintaining each client’s “exact query results” on the server. Instead, they do:

1. **Push notifications** (low payload): “something changed”
2. **Delta change feed** (durable pull): “give me changes since token X”

Microsoft Graph documents exactly this idea: **delta query** is a pull model for changes, while **change notifications** are push alerts. Delta queries reduce repeated full reads/polling, and change notifications tell you when to pull again.  
See: Graph delta query overview and change notifications overview.

Also: deletions are usually represented as **tombstones** (e.g., “deleted facet” in Graph drive delta feeds), and clients remove them from local state. Graph also documents resync behavior (HTTP 410) if a token is too old / server can’t provide changes.

### Why this matters for *paginated & filtered lists*

A list is not a single object; it’s a **query**. Keeping “page 7 of query X” perfectly up to date in real time is expensive and often a bad UX (rows jump around).

So typical UX patterns are:

- **Live update what’s visible** (especially page 1 / “recent” view)
- For other pages, show “Results changed — refresh” instead of shifting under the user

---

## Recommended target architecture

### High-level goals

- **Minimal server work per change**
- **No missed changes** after reconnect
- **Efficient UI update**: patch only affected rows when possible
- **Graceful fallback**: if too many changes, refresh the page

### Components

1. **Durable change feed** in Postgres (delta source of truth)
2. **Lightweight fanout** from Postgres to app instances (LISTEN/NOTIFY or Redis Pub/Sub)
3. **SSE endpoint** per workspace (or per user+workspace) to notify clients quickly
4. **Delta endpoint** to fetch changes since token
5. **List endpoint with `id` filter** to fetch row snapshots using the same filters/sort as the current view

### Architecture diagram

```text
  ┌───────────────┐         (1) mutate docs/runs/etc
  │  API / Worker │───────────────────────────────────────┐
  └───────┬───────┘                                       │
          │                                               │
          │  INSERT change row + pg_notify                │
          ▼                                               │
  ┌──────────────────────┐      LISTEN/NOTIFY             │
  │   Postgres DB         │──────────────┐                │
  │ - files               │              │                │
  │ - file_versions       │              │                │
  │ - runs, metrics...    │              │                │
  │ - document_changes(*) │              │                │
  └───────────────────────┘              │                │
                                         ▼                │
                               ┌────────────────────┐     │
                               │ FastAPI instance   │     │
                               │ - notify listener  │     │
                               │ - SSE conn mgr     │     │
                               └──────┬─────────────┘     │
                                      │ SSE event: "changed"
                                      ▼
                                 ┌────────────┐
                                 │ Browser UI │
                                 │ - calls    │
                                 │   /delta   │
                                 │ - calls    │
                                 │   /documents (id filter) │
                                 └────────────┘
```

(*) `document_changes` is the durable delta feed.

---

## API design

We’ll keep the existing list API as-is, **add 2 new endpoints**, and **extend the list API with an `id` filter** so clients can validate membership + fetch rows using the same server-side filter logic.

### 1) Existing list endpoint (source of truth)

```http
GET /workspaces/{workspaceId}/documents
  ?limit=50
  &cursor=...
  &sort=[{"id":"activityAt","desc":true}]
  &filters=[{"id":"assigneeId","operator":"eq","value":"..."}]
  &joinOperator=and
  &q=invoice
  &includeTotal=true
  &includeFacets=true
  &includeRunMetrics=true
```

### 2) SSE stream: “something changed” (low payload)

```http
GET /workspaces/{workspaceId}/documents/stream
Accept: text/event-stream
```

- The stream should be **workspace-scoped**
- Data should be tiny (just a **token hint** / “latest seq”)
- SSE supports an `id:` field; browsers send `Last-Event-ID` on reconnect.
- Use comment-line keepalives `: keepalive` to prevent proxy timeouts.

### 3) Delta endpoint: “what changed since token X” (durable)

```http
GET /workspaces/{workspaceId}/documents/delta?since=<token>&limit=500
```

Response:

```json
{
  "changes": [
    { "token": "....", "op": "upsert", "documentId": "uuid" },
    { "token": "....", "op": "delete", "documentId": "uuid" }
  ],
  "nextSince": "....",
  "hasMore": false
}
```

Notes:

- `since` is opaque to clients (base64 JSON), but server can decode it.
- If the server can’t serve changes for the token (too old / data pruned), return **HTTP 410 Gone** and require a full refresh. This mirrors Graph delta behavior (410 resync).  

### 4) Use the list endpoint with an `id` filter (server decides membership)

Instead of a bespoke lookup endpoint, reuse the **list endpoint** with the **same filters/sort/q** plus an `id` filter. This keeps server-side semantics consistent and avoids duplicating filter logic in the client.

```http
GET /workspaces/{workspaceId}/documents
  ?filters=[
      {"id":"assigneeId","operator":"eq","value":"<me>"},
      {"id":"id","operator":"in","value":["uuid1","uuid2"]}
    ]
  &sort=[{"id":"activityAt","desc":true}]
  &limit=50
```

Response:

```json
{
  "items": [ /* DocumentListRow[] that match the full filter */ ],
  "meta": { /* normal cursor meta */ }
}
```

Notes:

- This requires adding `id` to the document filter registry.
- The list endpoint remains the **source of truth** for membership.
- Clients can use `id in [...]` to batch checks for multiple changes.

---

## Event model

### Semantics: what an event means

We want **two operations**:

- `upsert`: “this document may have new state; fetch latest and reconcile”
- `delete`: “remove from UI state (tombstone)”

We intentionally do **not** encode “entered filter” vs “left filter” on the server.
Those are derived from the client’s current view state (filters/sort/page rules).

### Delivery guarantees

Target semantics:

- **At-least-once** delivery to clients (SSE reconnects; clients dedupe)
- **Ordered** within a workspace based on a monotonic token/sequence
- Clients must treat events as **invalidation hints**, not a transactional feed of intermediate states

### Token design

We recommend an opaque token containing:

- `ts`: timestamp (partition pruning + debugging)
- `seq`: monotonic bigint

Example token JSON:

```json
{ "ts": "2026-01-28T19:27:03.123Z", "seq": 123456 }
```

Encode it with base64url and use it as:

- SSE `id:` (optional but recommended)
- `/delta?since=` parameter
- Persist it in client state (e.g., in-memory + sessionStorage)

---

## Database design

You asked: “Do we need a change table? How do we auto-clean stale items? Optimize for speed.”

There are **two good Postgres-native options**. Pick based on expected write volume + ops tolerance.

### Option A (recommended): **Append-only change log** + retention via **partition dropping**

This is the most “standard” delta-feed approach: a durable, ordered log of changes.

#### Why it’s good

- Inserts are fast (append-only).
- You can guarantee ordering, replay, reconnect.
- Retention is clean: drop old partitions (fast, avoids vacuum bloat).

Postgres docs explicitly note that **dropping/detaching a partition is far faster than bulk DELETE and avoids VACUUM overhead**.

#### DDL: partitioned change log

```sql
-- Parent table
CREATE TABLE document_changes (
  changed_at   timestamptz NOT NULL DEFAULT now(),
  seq          bigint GENERATED ALWAYS AS IDENTITY,

  workspace_id uuid NOT NULL,
  document_id  uuid NOT NULL,

  op           text NOT NULL CHECK (op IN ('upsert', 'delete')),
  source       text NULL,          -- 'api' | 'run' | 'system'
  actor_user_id uuid NULL,
  payload      jsonb NULL,         -- keep SMALL; optional

  PRIMARY KEY (changed_at, seq)
) PARTITION BY RANGE (changed_at);

-- Fast delta lookup by workspace + ordering
CREATE INDEX ON document_changes (workspace_id, changed_at, seq);

-- Optional: for debugging / doc-specific queries
CREATE INDEX ON document_changes (document_id, changed_at, seq);
```

#### Creating daily partitions (example)

```sql
CREATE TABLE document_changes_2026_01_28
  PARTITION OF document_changes
  FOR VALUES FROM ('2026-01-28') TO ('2026-01-29');
```

#### Retention: drop old partitions

**Do not** `DELETE FROM document_changes WHERE changed_at < ...` at scale.
Instead, schedule:

- Create partitions ahead of time (e.g., next 7 days)
- Drop partitions older than retention (e.g., keep 7 or 14 days)

You can schedule this via:
- app-managed cron (preferred if DB doesn’t allow extensions), or
- `pg_cron` inside Postgres if available.

Example pg_cron usage:

```sql
-- Runs every day at 03:30
SELECT cron.schedule(
  'drop-old-doc-changes',
  '30 3 * * *',
  $$CALL drop_old_document_change_partitions('14 days')$$
);
```

##### Notes about `pg_cron`

`pg_cron` is a cron-based job scheduler extension that runs inside Postgres and can schedule SQL commands / stored procedures.

#### Handling “token too old” (410)

When partitions older than retention are gone, a client may send a `since` token earlier than the earliest available partition. In that case:

- return **HTTP 410 Gone**
- include a response telling the client to do a full refresh

This mirrors how Graph delta feeds behave when old tokens can’t be used.

---

### Option B (alternative): **Coalesced change state table** (bounded size, minimal cleanup)

Instead of storing every event, store only the **latest change per document** (upsert row each time).

Pros:
- Table size is bounded (roughly number of docs).
- Minimal retention/cleanup needs.
- Can be faster operationally (no partition mgmt).

Cons:
- You lose intermediate events (usually fine for UI).
- Updates write to indexes (still typically fine).

Example schema:

```sql
CREATE SEQUENCE document_change_seq;

CREATE TABLE document_change_state (
  workspace_id uuid NOT NULL,
  document_id  uuid NOT NULL,

  seq          bigint NOT NULL,
  changed_at   timestamptz NOT NULL DEFAULT now(),
  op           text NOT NULL CHECK (op IN ('upsert', 'delete')),

  payload      jsonb NULL,

  PRIMARY KEY (workspace_id, document_id)
);

-- Enables delta queries: "what docs changed since seq?"
CREATE INDEX ON document_change_state (workspace_id, seq);
```

Emit function would:

- `seq := nextval('document_change_seq')`
- upsert row (update seq/op/changed_at/payload)
- `pg_notify` with `{workspace_id, seq}`

Cleanup is optional; you may want to remove rows for deleted docs after N days, but it’s not required.

---

## Event emission: where changes come from

We need to emit document change events when the **list row** could change.

Given your schema, relevant sources include:

- `files` (documents): name, assignee, attributes, current_version_id, deleted_at, last_run_id, etc.
- `file_versions`: version changes can affect size/content_type/byte_size fields in list row (through current_version_id)
- `file_tags`: tags affect filtering and row display
- `runs`: status/phase changes, output creation, etc.
- `run_metrics`, `run_fields`, `run_table_columns`: only if the Documents list view includes these expansions and expects them live

### Important: avoid event storms

- Don’t emit per-row events from “wide” tables like `run_table_columns` if inserts are huge.
- Prefer emitting when the **run completes** or when **files.last_run_id** is updated, and ensure all relevant derived inserts happen in the same transaction before emitting.

### Recommended emission strategy: application/service-layer “document touch”

Best practice (and easiest to reason about):

- In the same transaction where you mutate doc/run state, call a single helper:

```python
await emit_document_change(workspace_id, doc_id, op="upsert", source="run")
```

If you still want guardrails, add DB triggers for “someone updated tables without calling the helper” — but keep triggers **statement-level** where possible.

### Postgres NOTIFY key facts (why we keep payload tiny)

- NOTIFY events are delivered only **after commit** (and only between transactions); keep transactions short.
- Payload must be **< 8000 bytes** by default.
- The docs explicitly recommend using tables for structured payloads and sending a key.

This is why we send “workspace_id + token/seq” in NOTIFY, and store everything durable in the change table.

---

## Backend implementation (FastAPI)

### Recommended backend module layout

```text
app/
  documents/
    router.py            # /documents endpoints
    schemas.py           # Pydantic models
    service.py           # list query + change helpers
    changes.py           # delta query + emit helpers
  realtime/
    sse.py               # SSE endpoint helper + connection manager
    pg_notify.py         # async LISTEN/NOTIFY listener
  db/
    session.py           # SQLAlchemy session / async engine
    migrations/          # Alembic
```

### Token encode/decode (Python)

```python
import base64, json
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass(frozen=True)
class ChangeToken:
    ts: datetime
    seq: int

def encode_token(tok: ChangeToken) -> str:
    payload = {"ts": tok.ts.astimezone(timezone.utc).isoformat(), "seq": tok.seq}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")

def decode_token(s: str) -> ChangeToken:
    raw = base64.urlsafe_b64decode(s.encode("ascii"))
    payload = json.loads(raw.decode("utf-8"))
    return ChangeToken(ts=datetime.fromisoformat(payload["ts"]), seq=int(payload["seq"]))
```

### SSE connection manager (per-workspace fanout)

Key goals:
- Don’t block the event loop
- Handle slow clients (bounded queues)
- Cleanup on disconnect

```python
import asyncio
from collections import defaultdict
from typing import DefaultDict, Set

class SSEConnectionManager:
    def __init__(self) -> None:
        self._workspace_queues: DefaultDict[str, Set[asyncio.Queue[str]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, workspace_id: str) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=100)  # backpressure: drop/close if too slow
        async with self._lock:
            self._workspace_queues[workspace_id].add(q)
        return q

    async def disconnect(self, workspace_id: str, q: asyncio.Queue[str]) -> None:
        async with self._lock:
            self._workspace_queues[workspace_id].discard(q)

    async def broadcast(self, workspace_id: str, msg: str) -> None:
        async with self._lock:
            queues = list(self._workspace_queues.get(workspace_id, set()))
        # Do not hold lock while putting
        for q in queues:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                # Strategy choice:
                # - drop newest (ignore)
                # - or drop connection (disconnect)
                pass
```

### Postgres LISTEN/NOTIFY listener (asyncpg)

Each FastAPI process should maintain a dedicated connection to Postgres for LISTEN.

```python
import asyncpg
import json
import asyncio

async def start_pg_notify_listener(dsn: str, mgr: SSEConnectionManager) -> asyncpg.Connection:
    conn = await asyncpg.connect(dsn)

    async def _handler(connection, pid, channel, payload):
        # payload should be small JSON: {"workspace_id":"...","token":"..."} or {"workspace_id":"...","seq":123}
        msg = json.loads(payload)
        workspace_id = msg["workspace_id"]
        # Broadcast a single "changed" ping; clients call /delta
        await mgr.broadcast(workspace_id, json.dumps(msg))

    await conn.add_listener("document_changes", _handler)
    await conn.execute("LISTEN document_changes;")
    return conn
```

### SSE endpoint (FastAPI)

Implementation notes:
- Must return `text/event-stream`
- Must regularly send keepalive comment lines
- Should set `X-Accel-Buffering: no` for Nginx
- Consider HTTP/2 in prod to avoid per-domain connection limits (see MDN warning)

```python
from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
import asyncio, json, time

router = APIRouter()

@router.get("/workspaces/{workspace_id}/documents/stream")
async def documents_stream(workspace_id: str, request: Request):
    # TODO: authz check: ensure user can access workspace_id

    q = await sse_manager.connect(workspace_id)

    async def gen():
        # initial keepalive to establish stream
        yield b": connected\n\n"

        last_keepalive = time.monotonic()
        try:
            while True:
                if await request.is_disconnected():
                    break

                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15)
                    payload = json.loads(msg)

                    # If using token, set SSE id to token so Last-Event-ID works on reconnect
                    token = payload.get("token")
                    if token:
                        yield f"id: {token}\n".encode()

                    yield b"event: documents.changed\n"
                    yield f"data: {msg}\n\n".encode()
                except asyncio.TimeoutError:
                    # keepalive comment line
                    yield b": keepalive\n\n"
        finally:
            await sse_manager.disconnect(workspace_id, q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

### Delta endpoint (FastAPI) - append-only table variant

```python
from fastapi import HTTPException

@router.get("/workspaces/{workspace_id}/documents/delta")
async def documents_delta(workspace_id: str, since: str, limit: int = 500):
    # TODO: authz check

    tok = decode_token(since)

    # If tok.ts is older than your retention window, return 410
    # (you can compare tok.ts to now() - retention)
    if tok.ts < get_oldest_available_partition_ts():
        raise HTTPException(status_code=410, detail="delta token expired; full resync required")

    # Query: WHERE workspace_id=? AND (changed_at, seq) > (tok.ts, tok.seq)
    rows = await fetch_changes(workspace_id, tok, limit)

    changes = []
    next_tok = tok
    for r in rows:
        next_tok = ChangeToken(ts=r.changed_at, seq=r.seq)
        changes.append({
            "token": encode_token(next_tok),
            "op": r.op,
            "documentId": str(r.document_id),
        })

    return {
        "changes": changes,
        "nextSince": encode_token(next_tok),
        "hasMore": len(rows) == limit,
    }
```

### List endpoint filter support (id filter for membership checks)

Instead of a bespoke lookup endpoint, add an `id` filter to the list filter registry so clients can call the existing list route with `id in [...]` plus the current filters/sort. This ensures consistent server-side semantics.

```python
# In documents filter registry
FilterField(
    id="id",
    column=File.id,
    operators={FilterOperator.EQ, FilterOperator.IN},
    value_type=FilterValueType.UUID,
)
```

---

## Frontend implementation (React/Vite)

### Client state to maintain

- Current list query state from URL: `filters`, `joinOperator`, `sort`, `q`, `cursor`, `limit`
- Current page rows (array) + map by `id`
- Current delta token `since` (store in memory; optionally sessionStorage)

### Subscribe to SSE

Notes:
- `EventSource` supports `withCredentials: true` for cookies.
- If your auth uses `Authorization: Bearer ...`, standard EventSource cannot set custom headers. Options:
  - use cookie-based auth for SSE endpoints, or
  - use a polyfill that supports headers, or
  - use WebSockets (token in query/headers depending on library)

Example:

```ts
const es = new EventSource(
  `/workspaces/${workspaceId}/documents/stream`,
  { withCredentials: true }
);

es.addEventListener("documents.changed", () => {
  scheduleDeltaPull();
});
```

### Debounced delta pull

Key idea: **batch** updates.

```ts
let pulling = false;
let scheduled = false;

function scheduleDeltaPull() {
  if (scheduled) return;
  scheduled = true;
  setTimeout(() => {
    scheduled = false;
    void pullDelta();
  }, 250);
}

async function pullDelta() {
  if (pulling) return;
  pulling = true;
  try {
    const res = await fetch(
      `/workspaces/${workspaceId}/documents/delta?since=${encodeURIComponent(since)}&limit=500`,
      { credentials: "include" }
    );

    if (res.status === 410) {
      // Token expired: full refresh of current page
      await refetchCurrentPage();
      return;
    }

    const data = await res.json();
    since = data.nextSince;

    const upsertIds = data.changes
      .filter((c: any) => c.op === "upsert")
      .map((c: any) => c.documentId);

    const deleteIds = data.changes
      .filter((c: any) => c.op === "delete")
      .map((c: any) => c.documentId);

    applyDeletes(deleteIds);

    if (upsertIds.length) {
      const filters = [
        ...currentFilters,
        { id: "id", operator: "in", value: upsertIds },
      ];
      const params = new URLSearchParams({
        filters: JSON.stringify(filters),
        sort: JSON.stringify(currentSort),
        joinOperator: currentJoinOperator,
        q: currentQuery ?? "",
        limit: String(Math.min(upsertIds.length, 200)),
        includeRunMetrics: "true",
      });
      const resp = await fetch(
        `/workspaces/${workspaceId}/documents?${params.toString()}`,
        { credentials: "include" }
      );
      const { items } = await resp.json();
      applyUpserts(items);
    }
  } finally {
    pulling = false;
  }
}
```

### Reconciliation: patch rows without full refresh

For page 1 / “live view”:

- If a changed doc is currently displayed → patch it
- If it now matches filters and should be in the page window → insert it
- If it no longer matches filters → remove it
- Keep page size at `limit`

For pages > 1 (recommended default):

- Patch visible rows (status changes, etc.)
- If an update would insert/remove rows beyond visible set, show a “Results changed” badge and offer refresh

See the dedicated UX section below.

---

## Pagination + real-time: UX rules that don’t feel haunted

This is the “tricky part” and the key to a sane implementation.

### Rule 1: treat your current page as a **window**, not a globally-correct slice

With cursor-based pagination, pages are anchored. New items “above” the cursor shouldn’t suddenly appear on page N unless you want page shifting.

Recommended UX behavior:

- **Page 1:** live insert new matching items at top
- **Page N>1:** do not shift membership automatically; show an “updates available” indicator

### Rule 2: mutable sort keys cause reordering

If sorting by a mutable field (e.g., `activityAt`), updates can move items across pages.

Options:

- **A)** allow shifting only on page 1; for page >1 show “refresh” indicator  
- **B)** freeze view by snapshot token (“as of”) — more complex  
- **C)** encourage stable sorts (e.g., `createdAt desc`) for live views

### Rule 3: totals & facets are eventually consistent

Unless you want to build a full real-time analytics pipeline, do not try to update:

- `includeTotal`
- `includeFacets`

…in real time for every change. Instead:
- refresh totals/facets when the user changes filters, or
- refresh periodically (e.g., every 30–60 seconds), or
- refresh on demand (button)

---

## Performance, scaling, and failure modes

### Postgres NOTIFY

Key facts from official docs:

- Notifications are delivered **only if the transaction commits**, and only between transactions; keep transactions short.
- Default payload limit is **< 8000 bytes**.
- Postgres explicitly suggests storing structured data in tables and using NOTIFY for signaling.

Also note:
- There is an internal notification queue; very long-lived transactions can block cleanup and cause failures at commit.

**Design implication:**  
Use NOTIFY as a “wake up / changed” hint and keep payload small (workspace_id + token/seq).

### Partition retention (append-only log)

Postgres docs: dropping/detaching partitions is far faster than bulk deletes and avoids vacuum overhead.

This is the “right way” to auto-clean a time-bounded change log.

### SSE vs WebSocket

**SSE** advantages:
- Simple server → client stream
- Browser auto-reconnect
- Event IDs + `Last-Event-ID`
- HTTP-friendly (proxies, observability)

SSE caveat:
- Without HTTP/2, browsers limit concurrent connections per domain (notable in multiple tabs).

**WebSocket** advantages:
- Full duplex
- Can carry auth headers in upgrade request (depending on client/lib)
- Good for bi-directional interactions

WebSocket caveat:
- Browser WS API does not provide built-in backpressure; if messages arrive too fast, you can buffer and blow memory (MDN notes this). You must implement backpressure/flow control server-side and throttle/batch.

### Consider Redis if NOTIFY becomes hot

LISTEN/NOTIFY is often fine for moderate scale, but if you see DB contention or heavy writer concurrency, consider:

- Redis Pub/Sub for fanout
- A proper message broker (NATS/Kafka) for high churn

The key idea stays the same:
- **Durable delta** in Postgres
- **Fast notification** via broker

### Unlogged tables?

Postgres allows `UNLOGGED` tables for speed, but they are **not crash-safe**: they are truncated after crash/unclean shutdown, and not replicated. Also, Postgres does not support `UNLOGGED` for partitioned tables.

For a delta/change feed, this usually isn’t worth it unless you can tolerate resync-after-crash behavior.

---

## Testing plan

### Backend tests

1. **Delta ordering**
   - Insert N changes; ensure delta returns in token order
2. **Token decode/encode**
   - Roundtrip tests; reject invalid tokens
3. **Retention behavior**
   - If token older than retention, return 410
4. **Delete behavior**
   - Ensure delete events emitted and list queries exclude deleted docs

### Integration tests

- Start SSE connection
- Create doc → receive SSE → delta → list(id filter) → UI row appears
- Update doc status/tags → row updates / enters/leaves filter
- Delete doc → row removed

### Load testing (important)

- Simulate run bursts (hundreds/thousands updates)
- Ensure:
  - SSE connection count stable
  - CPU/memory stable
  - client updates remain batched/debounced

---

## Observability

Recommended metrics:

- `realtime_sse_connections{workspace_id}` (cardinality carefully)
- `realtime_events_broadcast_total`
- `delta_requests_total` + latency histogram
- `delta_lag_seconds` (now - token.ts) at client and/or server
- `notify_queue_usage` (Postgres has pg_notification_queue_usage)

Logs:

- When a client gets 410 and must resync
- When SSE clients are dropped due to slow consumption (queue full)
- Partition maintenance job logs (created/dropped partitions)

---

## Implementation checklist

### DB

- [ ] Decide: append-only partitioned log (recommended) vs coalesced state table
- [ ] Add migration for change table + indexes
- [ ] Implement `emit_document_change(...)` function or service-layer helper
- [ ] Add partition maintenance (app cron or pg_cron)
- [ ] Decide retention window (start with 7–14 days)

### Backend

- [ ] SSE connection manager (per workspace)
- [ ] Postgres listener task (LISTEN document_changes)
- [ ] SSE endpoint: `/workspaces/{id}/documents/stream`
- [ ] Delta endpoint: `/workspaces/{id}/documents/delta`
- [ ] Add `id` filter support to `/workspaces/{id}/documents`
- [ ] AuthZ on all new endpoints
- [ ] Coalesce/batch events (server broadcast and client pull)

### Frontend

- [ ] Add SSE subscription (one per workspace tab)
- [ ] Store `since` token (in-memory + sessionStorage)
- [ ] Debounce delta pulls
- [ ] Apply deletes + list(id filter) reconcile
- [ ] UX: page 1 live, page N “refresh” indicator
- [ ] Handle 410: full refresh

---

## References

Below are the key primary sources used in this design.

- PostgreSQL NOTIFY docs (transactions, payload limit, design guidance):  
  https://www.postgresql.org/docs/current/sql-notify.html

- PostgreSQL partitioning docs (dropping partitions is faster than DELETE and avoids VACUUM overhead):  
  https://www.postgresql.org/docs/current/ddl-partitioning.html

- PostgreSQL CREATE TABLE docs (UNLOGGED truncation after crash; not supported for partitioned tables):  
  https://www.postgresql.org/docs/current/sql-createtable.html

- MDN: Using Server-Sent Events (format, keepalive comments, id/retry fields, connection limits):  
  https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events

- WHATWG HTML Standard: Server-Sent Events (Last-Event-ID behavior):  
  https://html.spec.whatwg.org/multipage/server-sent-events.html

- MDN: WebSocket API overview (two-way session; backpressure caveats):  
  https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API

- Microsoft Graph: delta query overview (change tracking; pull model; combine with push):  
  https://learn.microsoft.com/en-us/graph/delta-query-overview

- Microsoft Graph: change notifications overview (push delivery mechanisms):  
  https://learn.microsoft.com/en-us/graph/api/resources/change-notifications-api-overview?view=graph-rest-1.0

- Microsoft Graph: driveItem delta (deleted items returned as tombstones; 410 resync semantics):  
  https://learn.microsoft.com/en-us/graph/api/driveitem-delta?view=graph-rest-1.0

- pg_cron (in-DB scheduler; examples):  
  https://github.com/citusdata/pg_cron  
  https://access.crunchydata.com/documentation/pg_cron/latest/
