## Context
Delivered the refreshed results workflow so the rewritten services expose
extracted tables for succeeded jobs while guarding unavailable artefacts.

## Outcome
- Hardened `ExtractionResultsService` to validate job status, emit "viewed"
  events, and surface tables only when the run succeeded.
- Updated the results router to return structured 409 responses for pending or
  failed jobs and to bubble up not-found errors for missing tables/documents.
- Added integration coverage chaining upload → job → results alongside failure
  and deletion scenarios to verify the new API behaviour.
- Refreshed documentation (`BACKEND_REWRITE_PLAN.md`, README) to describe the
  job/results review flow and captured new follow-up milestones.

## Next steps
- Implement retention/cleanup policies for job records, logs, and extracted
  tables now that synchronous execution is in place.
- Seed sensible default permissions so workspace owners automatically gain job
  and results access.
- Revisit the event/timeline story once the new workflows are wired into the UI
  and automation clients.
