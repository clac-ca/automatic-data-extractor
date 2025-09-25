# Documentation Exposure Hardening Plan

## Goal
Default FastAPI's interactive documentation endpoints to disabled in production
by teaching `Settings` to only enable docs for explicitly allowed environments
(e.g., `local`, `staging`).

## Steps
1. **Settings behaviour**
   - In `backend/api/settings.py`, change `enable_docs` to default to `False` and
     add a computed property or helper that turns it on when
     `environment in {"local", "staging"}` unless an explicit override is
     provided.
   - Update `docs_urls` and related helpers to respect the new default and keep
     `openapi_url` aligned.
2. **App factory**
   - Adjust `backend/api/main.py` to lean on the updated settings helper so the
     FastAPI app hides `/docs`, `/redoc`, and `/openapi.json` unless docs are
     enabled.
3. **Tests**
   - Extend `backend/tests/core/test_settings.py` with coverage for the new
     default and environment-specific toggling.
   - Add or update API factory tests (if present) to confirm docs URLs are
     `None` when disabled.
4. **Docs & tracking**
   - Update `BEST_PRACTICE_VIOLATIONS.md` to mark the always-on docs issue as
     resolved and note the new behaviour in any relevant README sections.

## Verification
- `pytest backend/tests/core/test_settings.py`
- `ruff check backend/api backend/tests/core`
- `mypy backend/api backend/tests/core --follow-imports=skip`
