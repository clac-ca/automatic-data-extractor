# 🔄 Next Task — Cache authenticated identities on the request

## Context
`get_authenticated_identity` now composes small dependencies for session and API key resolution, but repeated dependency calls within the same request still retrace the lookup flow and reopen database sessions. Routes that combine router-level `Depends(get_current_user)` with additional user-dependent dependencies could perform redundant work, and downstream code still needs to call the dependency explicitly to access the resolved identity.

## Goals
1. Attach the resolved `AuthenticatedIdentity` to `request.state` within the authentication dependency so subsequent dependencies or route handlers can reuse it without repeating database lookups.
2. Ensure repeated calls to `get_authenticated_identity` during a single request return the cached value and do not reopen sessions when the state is already populated.
3. Update FastAPI routes and tests to exercise the cached identity path, including scenarios where both a router dependency and a route-level dependency request the current user.

## Definition of done
- The first resolution of `get_authenticated_identity` stores the identity on the request and later calls for the same request reuse it instead of requerying the database.
- Unit and integration tests cover both the cold path (initial resolution) and the cached path, proving that repeated dependencies return the same identity and still refresh sessions/API keys as expected.
- Documentation or inline notes clarify how request state caching interacts with dependency overrides in tests.
