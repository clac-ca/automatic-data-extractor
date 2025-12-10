# Testing Plan

Unit tests:
- Registry ordering and score patch normalization (`tests/unit/test_registry.py`).
- Discovery imports all modules deterministically (`tests/unit/test_discovery.py`).

Integration:
- Minimal config package + workbook end-to-end (`tests/integration/test_integration_e2e.py`) covering mapping, output ordering, transforms/validators, unmapped append.

Run with `pytest apps/ade-engine/tests` (or `ade tests` in repo).
