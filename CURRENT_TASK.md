# Task: Eliminate backend test suite deprecation warnings

## Context
- Running `pytest` now prints dozens of `DeprecationWarning` messages because Starlette deprecated the `HTTP_422_UNPROCESSABLE_ENTITY`
  and `HTTP_413_REQUEST_ENTITY_TOO_LARGE` constants. The backend still imports those names in routes and tests, so every request
  that triggers validation errors emits a warning.
- Alembic logs another `DeprecationWarning` during migrations because `prepend_sys_path` is configured without the new
  `path_separator` option. The warning fires on every migration run, including during tests.
- The warnings make it harder to spot real regressions in CI, so we should clean them up before the noise becomes normalised.

## Goals
1. Replace deprecated HTTP status constants with their modern equivalents across the backend and tests (e.g.
   `HTTP_422_UNPROCESSABLE_CONTENT`, `HTTP_413_CONTENT_TOO_LARGE`). Keep behaviour and response codes unchanged.
2. Update any assertions, docs, or OpenAPI metadata that mention the old constant names so everything stays consistent.
3. Configure Alembic so migration runs no longer emit the `path_separator` warning when loading `alembic.ini`.
4. Leave the pytest run free of these deprecation warnings so the suite surfaces only actionable noise.

## Implementation plan
- Search for `HTTP_422_UNPROCESSABLE_ENTITY` and `HTTP_413_REQUEST_ENTITY_TOO_LARGE` usages in routes, services, and tests. Replace
  them with the new names provided by Starlette/FastAPI.
- Re-run affected tests to confirm behaviour and payload expectations are unchanged (status codes remain 422 and 413).
- Update docstrings or docs if they mention the old constant names explicitly.
- Add `path_separator = os` (or equivalent) to `alembic.ini` under the `[alembic]` section to silence the migration warning. Verify
  Alembic still loads correctly via the helper module.
- Execute `pytest` and ensure the previous warnings disappear without introducing new ones. If other unrelated warnings remain,
  note them explicitly in the PR for future follow-up.

## Acceptance criteria
- No `DeprecationWarning` output appears when running `pytest` (specifically from HTTP status constants or Alembic path handling).
- Response status codes and test expectations remain consistent.
- Alembic migrations run without warning messages.
- Changes are covered by existing or updated tests.

## Testing
- `pytest`
