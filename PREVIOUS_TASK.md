# ✅ Completed Task — Expose RequestAuthContext from Request State

## Context
`RequestAuthContext` now centralises how request metadata is built, but FastAPI routes still reach into `request.state.auth_context` as an untyped dictionary. Each consumer has to guard against missing keys and manually extract values such as `mode`, `session_id`, or `subject`. Providing a typed accessor keeps the calling code simple while retaining backwards compatibility for callers that still expect the dictionary.

## Goals
1. Update `set_request_auth_context` so the constructed `RequestAuthContext` instance is stored on the request (for example `request.state.auth_context_model`) alongside the existing dictionary.
2. Add a lightweight helper in `services/auth.py` that returns the `RequestAuthContext` for a request, falling back to reconstructing it from the dictionary when necessary.
3. Refactor `/auth` routes (especially `current_user_profile`) and any other call sites to rely on the new helper instead of manually digging through the dictionary.
4. Preserve behaviour for existing consumers that read `request.state.auth_context`, `request.state.auth_session`, or `request.state.api_key` directly.

## Implementation notes
- Keep the helper free of FastAPI dependencies beyond `Request` and avoid changing response schemas.
- The accessor should return `None` when no context has been set and should tolerate partially populated dictionaries to remain robust with older tests.
- Extend or adjust unit tests to cover the helper and ensure the dataclass is attached to the request state.

## Definition of done
- `set_request_auth_context` stores both the dictionary and dataclass on the request state.
- A helper exists to retrieve the `RequestAuthContext` instance from a FastAPI request.
- `/auth` routes consume the helper instead of raw dictionary access.
- `pytest backend/tests/test_auth.py` passes.
