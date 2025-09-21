# ✅ Completed Task — Adopt the cached identity helper across stateful routers

## Context
Routers protected by authentication were still importing `get_current_user` directly and hard-coding event actor metadata. With `get_cached_authenticated_identity` available, we wanted to standardise on the cached identity, remove redundant dependencies, and ensure emitted events always capture who performed a change.

## Outcome
- Updated the configurations, jobs, and events routers to import `auth_service` once, depend on `get_authenticated_identity`, and reuse the cached identity through a new `event_actor_from_identity` helper.
- Defaulted configuration and job events to include `actor_type`, `actor_id`, and `actor_label` derived from the authenticated user while retaining existing API behaviour.
- Added regression tests covering the new event defaults and documented the router pattern with inline comments so future endpoints follow the same approach.
