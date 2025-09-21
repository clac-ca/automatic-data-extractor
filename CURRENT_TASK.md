# 🔄 Next Task — Inject settings dependency into auth routes

## Context
Auth route handlers still reach for `config.get_settings()` inside each function, hiding their configuration dependency and repeating boilerplate. FastAPI can supply the settings object directly via dependency injection, letting the framework manage overrides and reducing manual calls.

## Goals
1. Accept `settings: config.Settings = Depends(config.get_settings)` in each auth route instead of calling `config.get_settings()` manually.
2. Update helper usage so settings come from the injected object without re-fetching inside helper calls.
3. Keep behaviour and response shapes unchanged while ensuring tests cover the updated dependency wiring.

## Definition of done
- Every handler in `backend/app/routes/auth.py` relies on an injected settings dependency.
- Tests continue to pass with the new dependency signatures.
- `pytest backend/tests/test_auth.py` succeeds.
