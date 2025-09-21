# 🔄 Next Task — Inline RequestAuthContext into AuthenticatedIdentity

## Context
With request state mirrors removed, the standalone `RequestAuthContext` dataclass no longer serves a unique purpose: its fields duplicate information available on the `AuthenticatedIdentity`, the resolved `User`, and optional session or API key models. Dropping the extra wrapper would further simplify how downstream dependencies access authentication metadata.

## Goals
1. Remove the `RequestAuthContext` dataclass and move its fields onto `AuthenticatedIdentity` (e.g. `mode`, `session_id`, `api_key_id`, `subject`).
2. Update authentication helpers, routes, and tests to rely on the flattened identity object instead of a nested context attribute.
3. Ensure serialised responses (like `/auth/me` and session refresh) continue to expose the same payloads.

## Implementation notes
- Grep for `RequestAuthContext` to identify constructor and attribute usage before deleting the dataclass.
- Adjust any helper functions that previously called `RequestAuthContext.from_user` to populate the new identity fields directly.
- Refresh fixtures or helper stubs in tests so they build `AuthenticatedIdentity` instances without the nested context wrapper.

## Definition of done
- `RequestAuthContext` is removed from the codebase and all dependencies compile without referencing it.
- `AuthenticatedIdentity` directly exposes the metadata needed by routes and services (mode, session/api key identifiers, SSO subject).
- `pytest backend/tests/test_auth.py` passes.
