# 🔎 Code Review Prompt — Focus on What to Look For

When doing a code review, examine it critically with these lenses:

## Core lenses

* **Correctness** – Is the code reliable in how it handles data and logic? Pay attention to edge cases (empty inputs, nulls, uniqueness rules, timezones, ID formats, race conditions). The goal is to avoid silent failures and data corruption.

* **Simplicity & Clarity** – Is the code more complicated than necessary? Look for unnecessary abstractions, duplicate logic, or confusing flow. Simple, direct solutions reduce the chance of bugs and make the code easier to maintain.

* **Maintainability** – Would another developer be able to quickly understand and extend this file? Clear naming, well-structured functions, and explicit invariants make long-term upkeep less costly.

* **Consistency** – Does this file align with established patterns in the stack (e.g., SQLAlchemy sessions, FastAPI responses, error handling)? Inconsistencies increase learning overhead and create long-term friction.

* **Performance (within context)** – Given modest data volumes, is performance adequate? Watch for common pitfalls (N+1 queries, repeated serialization, unindexed lookups) that could create unnecessary slowness even at small scale.

* **Security & Safety** – Are inputs validated and normalized at the boundaries? Exceptions should not leak sensitive details. Identify risks like injection points, unsafe defaults, or trusting unverified client data.

* **Operational Concerns** – How would this behave in production? Consider logging (signal vs noise), observability, database constraints, and migration implications. Hidden assumptions can fail in live environments.

* **Testability** – What parts of this code are hard to test? Favor designs with clear seams (dependency injection, return values instead of side effects). Note missing or weak test coverage that could let regressions slip through.

## Additional review habits

* **Trace data flow end to end.** Confirm that new inputs or fields are validated, persisted, and returned consistently across routes, services, and schemas.
* **Cross-check documentation and migrations.** If behaviour changes, ensure accompanying docs/tests/migrations reflect the update.
* **Run the right checks.** Encourage authors to execute the commands listed in `AGENTS.md` (pytest, ruff, mypy, frontend tooling) when their diff touches the relevant areas.
* **Flag follow-up work.** Capture TODOs or deferred cleanup explicitly so they are not lost once the PR lands.
