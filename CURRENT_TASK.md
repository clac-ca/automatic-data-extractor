# 🔄 Next Task — Remove Legacy Request Auth Context Fallback

## Context
`AuthenticatedIdentity` is now the primary entry point for FastAPI routes, and `set_request_auth_context` writes the dataclass version of the context onto each request. We still duplicate that data into the legacy `request.state.auth_context` dictionary to support earlier patterns that are no longer used anywhere in the codebase. Keeping both formats increases surface area without providing value.

## Goals
1. Update `set_request_auth_context` and `get_request_auth_context` so they work exclusively with the dataclass representation instead of juggling both the dataclass and dictionary forms.
2. Remove the compatibility code and tests that exercise the dictionary-based fallback.
3. Adjust any remaining call sites (if found) to consume the dataclass directly.
4. Ensure `pytest backend/tests/test_auth.py` passes after the cleanup.

## Implementation notes
- Confirm no routes or services rely on `request.state.auth_context` being a plain dictionary before removing the fallback.
- Keep `request.state.auth_context_model` as the single source of truth to avoid breaking existing middleware hooks.
- If the dictionary form is required for serialization in responses, expose it via a deliberate helper rather than state mutation.

## Definition of done
- Request authentication context only exists as a `RequestAuthContext` dataclass on `request.state`.
- Tests reflect the simplified storage and still cover key behaviours.
- `pytest backend/tests/test_auth.py` passes.
