# Previous Task — Expand audit logging beyond document deletions

## Goal
Instrument additional ADE workflows (configurations and jobs) to use the
shared audit log while keeping the API surface predictable for future UI work.

## Why this matters
- Operators now have deletion history, but configuration activations and job
  lifecycle events still lack immutable tracking.
- Consistent audit entries across domains make it easier to build UI timelines
  and automated alerts.
- Reusing the new audit service keeps instrumentation straightforward and
  reduces duplicated SQL in route handlers.

## Proposed scope
1. **Configurations** – Record `configuration.*` events when
   configurations are created, updated, or activated. Payloads should capture
   title, version, actor, and activation status.
2. **Jobs** – Emit events for job creation, status transitions (`pending →
   running → completed/failed`), and result publication. Include actor (creator
   or system process), source (API vs. scheduler), and key metrics in payloads.
3. **API/query helpers** – Extend `/audit-events` filtering to cover the new
   event types (e.g., by document type or job status) if gaps appear while wiring
   up the additional workflows.
4. **Documentation** – Update the README, glossary, and any workflow docs so
   teams know which events exist and how to interpret their payloads. Capture an
   example entry for each new event type.

## Open questions / follow-ups
- Do we need UI affordances (timeline tabs, export endpoints) before adding more
  events, or can front-end work follow later?
- Should audit payloads reference configuration/job identifiers only, or include
  small summaries (title, document type) for quick inspection?
- Is there appetite for correlating events by request ID across routes (e.g.,
  job creation and subsequent status updates)?
