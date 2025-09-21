# ✅ Completed Task — Inject shared Settings dependency into auth routes

## Context
Every `/auth` handler fetched configuration via `config.get_settings()` inside the function body, hiding the dependency chain and duplicating setup logic. Surfacing the `Settings` object as an explicit dependency makes it obvious when handlers rely on runtime configuration and keeps FastAPI's injection model consistent across the service.

## Outcome
- Added a `config.Settings` dependency parameter to each auth route so FastAPI injects the cached configuration instead of recreating it per-call.
- Removed the inline `config.get_settings()` lookups and threaded the injected settings through existing helper calls for cookie management and response shaping.
- Verified the behaviour stays identical by running the authentication test suite (`pytest backend/tests/test_auth.py`).
