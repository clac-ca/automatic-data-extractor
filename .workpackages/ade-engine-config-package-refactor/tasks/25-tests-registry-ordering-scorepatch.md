# Task 25 – Tests: registry ordering + score patch normalization

Checklist: H) Unit tests: registry ordering + score patch normalization.

Objective: Add unit coverage for deterministic ordering and normalization helpers in the registry package.

Implementation steps:
- [ ] Under `apps/ade-engine/tests/unit/`, add tests verifying `_sort_key` ordering (priority desc, module asc, qualname asc) for detectors/hooks.
- [ ] Add tests for `normalize_patch` handling float, dict, None/no-op, unknown keys, and non-finite values.
- [ ] Include duplicate field registration error test and unknown field in patch warning/ignore behavior.

Definition of done:
- [ ] Tests pass locally (`ade tests`), cover ordering + normalization edge cases, and align with docs in `docs/testing-plan.md`.
