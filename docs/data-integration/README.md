---
Audience: Data teams
Goal: Describe how downstream systems integrate with ADE via APIs today and highlight upcoming analytics surfaces.
Prerequisites: API credentials with read access, familiarity with HTTP tooling, and awareness of ADE retention policies.
When to use: Reference when building automation around ADE outputs or planning data synchronization jobs.
Validation: Confirm the API overview renders and note TODOs for SQL/reporting guidance.
Escalate to: Data platform owner when API coverage or retention guarantees change.
---

# Data integration

This section focuses on the interfaces that power automation and downstream analytics. ADE exposes a REST API today, with SQL and reporting surfaces planned for later iterations.

## Core guide

- [API overview](./api-overview.md) — endpoints, authentication requirements, and example requests.

## Planned follow-ups (TODO)

- `sql-access.md` — query ADE's SQLite database or read replicas safely.
- `data-export.md` — retrieve processed outputs and reconcile checksums.
- `event-stream.md` — subscribe to event notifications once streaming support lands.
