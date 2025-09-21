# 🔄 Next Task — Inject shared Settings dependency into auth routes

## Context
`backend/app/routes/auth.py` calls `config.get_settings()` inside every handler, which hides the dependency chain FastAPI already provides. Surfacing the configuration as a dependency will cut duplication and make it obvious which endpoints rely on the runtime settings.

## Goals
1. Update the `/auth` route handlers to receive `config.Settings` via FastAPI dependency injection instead of calling `config.get_settings()` inline.
2. Thread the injected settings through helper functions where needed so responses, cookie handling, and available auth modes continue to use the central configuration.
3. Keep the HTTP responses and audit logging identical by refreshing or extending tests only if the new signatures require it.

## Definition of done
- All functions in `backend/app/routes/auth.py` use an injected `Settings` object rather than calling `config.get_settings()` manually.
- Authentication tests (`backend/tests/test_auth.py`) still pass without behavioural changes.
