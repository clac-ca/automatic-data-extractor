# Current Task — Surface entity summaries in the global events feed

## Goal
Teach `GET /events` to embed the same `entity` summary block when callers filter to a single entity (`entity_type` + `entity_id`).

## Why this matters
- Operators using the global feed today must hit both `/events` and the resource-specific endpoint to see context; inlining the summary avoids redundant round-trips.
- CLI tooling that tails the shared feed can render document filenames or configuration titles without bespoke lookups per entity type.
- Reusing the summary union keeps downstream consumers aligned across entity-specific and global timelines.

## Proposed scope
1. **Schema + plumbing** – Allow `EventListResponse` emitted by `/events` to populate `entity` when both `entity_type` and `entity_id` filters are supplied.
2. **Data loading** – Resolve the matching entity (document/configuration/job) once per request, reuse existing timeline summaries, and continue returning 404 when the entity does not exist.
3. **Validation** – Add API tests that cover each entity type, ensure pagination still works, and assert the endpoint stays summary-free when filters are absent or incomplete. Update the README/glossary to mention the behaviour.

## Open questions / follow-ups
- Should the endpoint reject requests that pass only one of `entity_type` or `entity_id` now that a summary is expected?
- Do we need to cap which entity types support summaries to prevent future breakage when new types are added to the events feed?
- Would a query flag (`include_entity=false`) be useful for clients that prefer the lean payload?
