# Current Task — Allow opting out of entity summaries in the audit feed

## Goal
Add an `include_entity` query flag to `GET /audit-events` so callers can explicitly skip resolving the entity summary block even when `entity_type` and `entity_id` filters are provided.

## Why this matters
- Some CLI and batch consumers only need event rows and would benefit from avoiding the extra entity lookup that now happens automatically.
- Making the behaviour explicit in the contract avoids surprises if future entity types lack timeline summaries.
- An opt-out flag keeps the default ergonomic for UI usage while allowing high-volume integrations to trim payload size.

## Proposed scope
1. **Request handling** – Accept an `include_entity` boolean query parameter that defaults to `true`. When `false`, bypass the entity lookup and omit the summary in the response.
2. **Documentation** – Update API docs and glossary entries to describe the flag and its defaults so consumers know how to disable the summary.
3. **Validation** – Extend the audit feed tests to cover the opt-out path, ensuring pagination and filtering continue to work when the summary is suppressed.

## Open questions / follow-ups
- Should we log whenever `include_entity=false` is used to understand client adoption?
- Do we need rate metrics around entity lookups to see if the flag materially reduces load?
- Should entity-type specific endpoints also honour an opt-out flag for consistency?
