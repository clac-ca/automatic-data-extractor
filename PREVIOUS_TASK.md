## Context
`/auth/token` was leaking uncaught `ValueError`s from `AuthService.authenticate`
when form submissions arrived with blank or malformed credentials. The plan in
`CURRENT_TASK.md` called for a Pydantic schema and dependency to surface those
issues as FastAPI 422 responses.

## Outcome
- Added `TokenRequest` to validate and normalise credentials coming from the
  OAuth2 form, trimming whitespace and tolerating `.local`-style domains used
  by service accounts.
- Introduced `parse_token_request` dependency and updated the `/auth/token`
  route to consume the new schema so `AuthService` always receives cleaned
  inputs.
- Extended auth endpoint tests to assert 422 responses for blank, whitespace
  only, and malformed credentials and refreshed best-practice documentation.

## Next steps
- Roll this schema-first pattern out to other manual parsing hotspots (e.g.
  API key issuance, job submission, workspace membership) so every endpoint
  benefits from consistent 422 responses.
- Keep verifying auth flows with `pytest backend/tests/modules/auth/test_auth.py`
  after related changes to guard against regressions.
