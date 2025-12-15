# Testing Plan

## What’s covered

- **Registry** — ordering by priority/module/qualname; detector score validation (`tests/unit/test_registry.py`).
- **Pipeline helpers** — materialization guards for empty rows/cols (`tests/unit/test_materialize_rows.py`), row detection heuristics (`tests/unit/test_detect_rows.py`), column transforms contract (`tests/unit/test_transform.py`), validators contract (`tests/unit/test_validate.py`), render ordering/unmapped handling (`tests/unit/test_render.py`).
- **CLI** — input discovery globs and extension filtering (`tests/unit/test_main.py`).
- **End-to-end** — synthetic config package + workbook exercising detection → mapping → transforms → validators → output ordering (`tests/integration/test_integration_e2e.py`).

## How to run

- From repo root: `pytest apps/ade-engine/tests`
- Or via helper: `ade tests` (runs the engine’s test suite inside the repo tooling)

## When adding features

- Add a focused unit test near the feature (e.g., new pipeline guard → `tests/unit`).
- Keep an integration test that exercises the new behavior through `Engine(Settings())` with a tiny config package fixture.
- Prefer deterministic fixtures (small in-memory workbooks) to avoid brittle date/locale differences.
