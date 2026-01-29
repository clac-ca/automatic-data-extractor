# Work Package: ADE Dev Log Performance Analysis

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Analyze the 2-minute ADE dev log capture and produce a focused performance report that lists all observed issues, their likely root causes, and concrete remediation steps (quick wins and longer-term fixes). The report will be stored as a .md artifact under this workpackage.

### Scope

- In:
  - Analyze `/tmp/ade-dev-2min.log` and any subsequent captures the user provides.
  - Identify startup, frontend, API, DB, worker, and logging-related performance issues.
  - Produce a written report with evidence, impact, and fix recommendations.
- Out:
  - Code changes or implementation work.
  - Benchmarking in production environments.

### Work Breakdown Structure (WBS)

1.0 Intake and Baseline Metrics
  1.1 Collect log inputs and timeline
    - [x] Confirm log file path(s), time window, and capture context (debug level, services running).
    - [x] Extract startup readiness times (API ready, Vite ready) and note delays.
  1.2 Build request latency summary
    - [x] Parse request.complete lines for duration_ms by endpoint/method.
    - [x] Identify top 10 slow requests and summarize averages/medians by endpoint.
  1.3 Extract error and warning hotspots
    - [x] Enumerate repeated error patterns (e.g., UniqueViolation, retries, timeouts).
    - [x] Quantify frequency and time windows for each hotspot.

2.0 Root Cause Analysis
  2.1 Frontend startup and reload cost
    - [x] Attribute Vite ready time and identify potential asset or dependency hotspots.
    - [x] Assess impact of hot reload watchers and file count on dev start time.
  2.2 API request latency
    - [x] Identify expensive endpoints (documents list, delta, upload) and correlate with query logs.
    - [x] Flag N+1 or repeated query patterns in the log.
  2.3 DB contention and consistency
    - [x] Analyze doc_no collisions (files_workspace_doc_no_key) and concurrency windows.
    - [x] Determine if SELECT max(doc_no) + 1 is causing retries/rollbacks.
  2.4 Polling vs streaming behavior
    - [x] Verify whether /documents/delta polling runs alongside /documents/stream SSE.
    - [x] Estimate excess load from redundant polling.
  2.5 Logging and instrumentation overhead
    - [x] Measure volume of SQL DEBUG logs and duplicate log streams (api vs api:err).
    - [x] Identify where log verbosity materially affects throughput/latency.

3.0 Remediation Plan and Priorities
  3.1 Quick wins (dev-time improvements)
    - [x] Propose logging level adjustments or log filtering to reduce I/O overhead.
    - [x] Suggest disabling redundant polling when SSE is active.
  3.2 Correctness + concurrency fixes
    - [x] Recommend a doc_no allocation strategy (DB sequence/locking) to prevent collisions.
    - [x] Outline idempotency/transaction improvements for document upload.
  3.3 Performance upgrades
    - [x] Suggest query/index improvements based on slow endpoints.
    - [x] Note frontend bundling or dependency trim steps for faster Vite readiness.

4.0 Deliverables
  4.1 Performance report (.md)
    - [x] Create a report that enumerates issues, evidence from the log, and fix steps.
    - [x] Include a prioritized action list and expected impact.

### Open Questions

- What is the target acceptable startup time for `ade dev` (API and Vite)?
- Is it acceptable to disable polling entirely when SSE is connected, or should we implement a fallback cadence?
- Are we willing to change doc_no semantics (e.g., gaps) by moving to a DB sequence?
- Do we want dev-only logging defaults that differ from production (e.g., SQL echo off)?
- Should the report focus strictly on the dev environment, or include production guidance?

---

## Acceptance Criteria

- A markdown report exists at `workpackages/wp-perf-log-analysis/perf-report.md`.
- The report lists every observed performance issue with log evidence and timestamps.
- Each issue includes a concrete fix recommendation and priority (P0/P1/P2).
- The report highlights at least one root cause for slow document upload and slow delta polling.
- The report includes a section on logging overhead and actionable mitigation steps.

---

## Definition of Done

- WBS tasks are complete and checked.
- Report is clear, actionable, and tied directly to log evidence.
- No code changes are required for completion.
