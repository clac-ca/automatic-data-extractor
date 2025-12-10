# Task 26 – Tests: discovery imports all modules deterministically

Checklist: H) Unit tests: discovery imports all modules deterministically.

Objective: Validate `import_all` imports every module under a package once and in stable order.

Implementation steps:
- [ ] Create test package fixture with nested modules under `tests/unit/fixtures/discovery_pkg/...` that register into a test registry.
- [ ] Write tests to assert all modules imported, registry counts match expected, and order is deterministic (sorted names).
- [ ] Cover single-module package case (no `__path__`) and repeated calls (no duplicate registration or controlled behavior).

Definition of done:
- [ ] Discovery tests run in CI; failures clearly indicate missing/extra imports or ordering drift.
