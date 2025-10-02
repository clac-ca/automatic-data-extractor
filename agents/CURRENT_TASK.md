## Context
Settings now expose consistent names and types, but the configuration surface
still lives in a single `Settings` object. `agents/BEST_PRACTICE_VIOLATIONS.md`
calls out this monolith as a FastAPI anti-pattern: services import the entire
settings payload even when they only need a narrow slice, making tests and
future overrides harder to reason about.

## Goals
- Introduce focused config models (for example `ServerSettings`,
  `DatabaseSettings`, `JwtSettings`, `StorageSettings`) and compose them within a
  slim orchestration object.
- Update dependencies, services, and routers to consume the scoped configs they
  need rather than the top-level `Settings` bag of values.
- Preserve the existing `ADE_` environment variables and documentation so the
  frontend team and operators continue to see a predictable configuration API.

## Non-goals
- Changing default values or environment names for existing settings.
- Reworking CLI surfaces beyond swapping their imports to the new config
  structure.
- Introducing dynamic loading or plugin systems; this task is purely structural.

## Tasks
1. Extract domain-specific settings models, wiring them into a root `Settings`
   container that mirrors today’s environment handling.
2. Update modules to depend on the appropriate slice (e.g. request middleware
   uses `ServerSettings`, repositories use `DatabaseSettings`).
3. Adjust tests and fixtures to access the new config structure and extend docs
   with a short note about the nested layout.
4. Run `mypy app` and `pytest` to prove the refactor holds.

## Acceptance criteria
- Settings consumers import the scoped config objects they need rather than the
  monolithic class.
- Environment variables and defaults remain unchanged for operators.
- Documentation and regression tests reflect the new structure without loss of
  coverage.
