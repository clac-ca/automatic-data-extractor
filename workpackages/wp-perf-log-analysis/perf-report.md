# ADE Dev Log Performance Report

Source: `/tmp/ade-dev-2min.log` (2-minute capture, debug enabled)

## Executive Summary

The primary performance issues observed are:

1) **Document upload contention** caused by non-atomic `doc_no` allocation, producing a large number of `UniqueViolation` errors and elevated `POST /documents` latencies.
2) **Redundant realtime traffic**: `/documents/delta` polling continues while SSE `/documents/stream` is active, multiplying DB load and request volume.
3) **Excessive log volume / duplicate SQL logging**, which creates significant I/O overhead and likely slows dev responsiveness.
4) **Frontend dev server cold start** takes ~12s: Vite readiness gates the page load even though API is ready almost immediately.

Below are concrete findings, evidence, and fix recommendations.

---

## Timeline Highlights

- **API readiness:** immediate at startup (log timestamp `02:48:12`).
- **Vite readiness:** `02:48:23` with `ready in 12147 ms` (about 11–12s after start). This is the first point the SPA can load.

---

## Performance Issues and Fixes

### P0 — Doc number collisions during uploads (data integrity + latency)

**Evidence**
- 290 occurrences of `psycopg.errors.UniqueViolation` on `files_workspace_doc_no_key` within the 2‑minute window.
- Multiple identical errors clustered around `02:49:58`–`02:50:05` for the same workspace/doc_no.
- `POST /documents` latency spikes: max 1358 ms, median 356 ms, avg 446 ms (21 requests).

**Likely root cause**
- `doc_no` is generated via `SELECT max(doc_no) + 1` without a lock or atomic allocator. Concurrent uploads pick the same value and collide.

**Fix options** (preferred order)
1) **Atomic allocator table**: create a `workspace_doc_no_counters` table and use `UPDATE ... SET next_doc_no = next_doc_no + 1 RETURNING next_doc_no` inside the same transaction.
2) **FOR UPDATE** on a workspace row storing `next_doc_no` (if a workspace metadata table exists).
3) **Per‑workspace sequence** (managed by DB, with `nextval`), allow gaps.
4) **Retry loop** on `IntegrityError` with backoff while re‑reading `max(doc_no)` (quick patch, still suboptimal under load).

**Expected impact**
- Eliminates repeated insert failures and large upload latency spikes.
- Reduces DB churn and retries during concurrent uploads.

---

### P1 — Redundant delta polling while SSE is active

**Evidence**
- 76 `GET /documents/delta` calls in 2 minutes (avg 39 ms, max 893 ms).
- 3 `GET /documents/stream` (SSE) connections opened during same window.
- Indicates **polling + streaming concurrently**, doubling load.

**Likely root cause**
- Frontend keeps polling even when SSE is connected and healthy.

**Fix**
- Use **SSE as the primary** realtime channel. Disable delta polling while SSE is connected.
- Keep delta polling as a **fallback** after SSE errors or disconnect, with exponential backoff.
- Optionally add a “heartbeat” timeout to re‑enable polling if no SSE events arrive.

**Expected impact**
- Immediate reduction in DB/query load and API request volume.
- Less UI latency from a congested API.

---

### P1 — Heavy and duplicated SQL logging

**Evidence**
- ~9,398 SQL log lines tagged `[api]` and ~9,398 duplicated at `[api:err]` in 2 minutes.
- Total log file size ~52k lines in 2 minutes.

**Likely root cause**
- SQLAlchemy INFO logging enabled + duplicate handlers (stdout + stderr), causing each statement to be logged twice.

**Fix**
- **Default dev log level to INFO** and set `ADE_DATABASE_LOG_LEVEL` to `WARNING` (or `ERROR`).
- Remove duplicate handlers or disable SQLAlchemy propagation to both stdout and stderr in dev.
- Consider a feature flag to enable SQL logging only when needed.

**Expected impact**
- Significant reduction in log I/O, improved dev server responsiveness, and easier signal‑to‑noise in logs.

---

### P1 — Frontend cold start time (~12s)

**Evidence**
- `VITE v7.3.1 ready in 12147 ms` at `02:48:23`, while API was ready at `02:48:12`.

**Likely root cause**
- Large dependency graph and prebundle cost on cold start.

**Fix options**
- Pre‑warm Vite deps cache (`optimizeDeps.include` for core deps).
- Reduce large/unused frontend dependencies.
- Ensure `node_modules/.vite` cache persists (avoid clearing between runs).
- Run `pnpm install --frozen-lockfile` only when needed; use incremental installs during dev.

**Expected impact**
- Faster UI availability on `ade dev` startup.

---

### P2 — CORS preflight volume on documents endpoints

**Evidence**
- 70 `OPTIONS /documents/delta` and 47 `OPTIONS /documents` calls in 2 minutes.

**Likely root cause**
- Non‑simple requests (custom headers) causing preflight, with no effective caching.

**Fix**
- Add `Access-Control-Max-Age` to CORS responses to cache preflight.
- Avoid custom headers for simple GETs where possible.

**Expected impact**
- Lower request volume and reduced latency variance.

---

## Endpoint Latency Summary (2 min window)

- `POST /documents`: avg **446 ms**, median **356 ms**, max **1358 ms**
- `GET /documents`: avg **57 ms**, median **41 ms**, max **326 ms**
- `GET /documents/delta`: avg **40 ms**, median **23 ms**, max **893 ms**
- `GET /documents/stream`: avg **115 ms**, median **129 ms**, max **175 ms**

Note: The slowest request spikes correlate with `doc_no` collisions and repeated retry/rollback cycles.

---

## Recommended Priority Order

1) **Fix `doc_no` allocation** (correctness + performance). This is the biggest source of failures and latency spikes.
2) **Disable polling when SSE is live** to cut redundant API load.
3) **Reduce SQL logging volume** in dev to improve responsiveness.
4) **Optimize Vite cold start** if faster dev boot is needed.
5) **Cache CORS preflights** to reduce request noise.

---

## Suggested Next Steps

- Implement a doc_no allocator (sequence or counter table) and re‑run the same 2‑minute capture.
- Update frontend realtime strategy to prefer SSE and backoff polling.
- Adjust logging configuration and compare log size + request latencies.
- Re‑measure Vite startup time after cache tuning.
