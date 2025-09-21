# 🔄 Next Task — Use FastAPI dependency to resolve API key tokens

## Context
`get_authenticated_identity` currently depends on both the bearer Authorization header and the `X-API-Key` header separately, then invokes `_resolve_api_key_token` to figure out which credential was supplied. Wrapping that check in a shared dependency mirrors the new session cookie helper, keeps signatures lean, and relies on FastAPI's injection system instead of manual branching.

## Goals
1. Add a public dependency in `backend/app/services/auth.py` that combines the bearer and header schemes to return the API key token when present (without raising when neither is supplied).
2. Update `get_authenticated_identity` and any other call sites to depend on the new helper instead of passing two security dependencies and calling `_resolve_api_key_token` directly.
3. Ensure existing authentication behaviour is preserved by re-running the auth test suite.

## Definition of done
- Auth dependencies no longer accept raw `HTTPAuthorizationCredentials` or header values just to resolve API key tokens; they use the new helper instead.
- Authentication tests continue to pass without regressions.
