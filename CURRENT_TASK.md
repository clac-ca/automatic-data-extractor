# 🔄 Next Task — Align document events with cached identity defaults

## Context
Document endpoints still mix manual actor metadata (for example `deleted_by` or hard-coded labels) with request state lookups. Now that `auth_service.event_actor_from_identity` exists, we can remove the remaining bespoke wiring, ensure `actor_id` is recorded for document events, and reuse the same pattern across the API.

## Goals
1. Update the document update and delete routes to derive event actor defaults via `get_cached_authenticated_identity(request)` and `event_actor_from_identity`, only overriding values when clients explicitly provide them.
2. Ensure document deletion and metadata update events consistently populate `actor_type`, `actor_id`, and `actor_label`, favouring the authenticated user when overrides are absent.
3. Expand tests to cover the new defaults for both update and delete flows so regressions are caught automatically.

## Definition of done
- Document routes no longer hard-code actor labels and instead share the cached identity helper for default metadata.
- Document events emit actor fields for both updates and deletions without breaking existing override behaviour.
- Automated tests assert the recorded actor metadata for update and delete events.
