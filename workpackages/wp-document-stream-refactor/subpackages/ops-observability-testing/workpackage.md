# Work Package: Realtime Ops, Observability, and Testing

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Add observability and tests for the realtime documents pipeline, validate retention behavior, and document operational considerations (SSE limits, backpressure, and delta resync).

### Research References (read first)

- `workpackages/wp-document-stream-refactor/research.md` lines 843-899 (performance/scaling/NOTIFY/SSE/WS notes)
- `workpackages/wp-document-stream-refactor/research.md` lines 903-929 (testing plan + load guidance)
- `workpackages/wp-document-stream-refactor/research.md` lines 933-947 (observability metrics + logs)

### Scope

- In: metrics/logging, integration tests, load test guidance, retention validation.
- Out: full perf benchmarking suite, production infra changes.

### Work Breakdown Structure (WBS)

0.1 Research review
  - [x] Read `workpackages/wp-document-stream-refactor/research.md` lines 843-899 (perf, failure modes, SSE/WS, NOTIFY limits)
  - [x] Read `workpackages/wp-document-stream-refactor/research.md` lines 903-929 (testing + load guidance)
  - [x] Read `workpackages/wp-document-stream-refactor/research.md` lines 933-947 (observability metrics + logs)
1.0 Metrics and logging
  1.1 Metrics
    - [ ] Add counters for SSE connections and broadcast totals (Research: lines 937-939)
    - [ ] Add delta latency / lag metrics (Research: lines 939-940)
    - [ ] Track NOTIFY queue usage if available (pg_notification_queue_usage) (Research: lines 941, 853-854)
  1.2 Logs
    - [x] Log 410 resync events (Research: lines 945-946)
    - [x] Log when SSE clients are dropped for slow consumption (Research: lines 946-947, 881-882)
2.0 Backend tests
  2.1 Unit tests
    - [x] Token encode/decode roundtrip (Research: lines 905-912)
    - [x] Delta ordering and 410 behavior (Research: lines 907-913)
2.2 Integration tests
    - [ ] SSE notify -> delta -> list(id filter) flow (Research: lines 918-921)
3.0 Operational guidance
  3.1 Docs
    - [x] Document retention maintenance steps (Research: lines 347-367, 859-863)
    - [x] Document SSE connection limits and HTTP/2 guidance (Research: lines 867-874)
    - [x] Document NOTIFY payload size constraints and keepalive strategy (Research: lines 845-857, 576-633)
3.2 Load guidance
    - [ ] Capture load test guidance for bursty runs (Research: lines 923-929)

### Open Questions

- Metrics backend choice (Prometheus/OpenTelemetry/etc.) is still open.

---

## Acceptance Criteria

- Core metrics and logs are present for realtime operations. (Research: lines 933-947)
- Basic tests validate token and delta correctness. (Research: lines 903-913)
- Docs include retention and SSE operational notes. (Research: lines 347-367, 859-874)

---

## Definition of Done

- Observability hooks are implemented and documented. (Research: lines 933-947)
- Tests cover the core realtime flow and resync behavior. (Research: lines 903-921)
