# Task 27 – Tests: end-to-end pipeline with sample config package

Checklist: H) Integration test: small sample config package → run pipeline end-to-end.

Objective: Exercise full pipeline (settings → registry → discovery → detect → map → transform → validate → render) using a minimal config package and workbook fixture.

Implementation steps:
- [ ] Add tiny config package fixture under `apps/ade-engine/tests/integration/fixtures/config_packages/ade_config_min/` with detectors/transforms/validators/hooks mirroring template.
- [ ] Add small workbook fixture (`simple_people.xlsx`) with header + few rows including an unmapped column.
- [ ] Write integration test that runs `python -m ade_engine run` (or pipeline entry) against the fixture with temp output/log dirs; assert mapping results, output column order (mapped input order + raw appended), validator issues, and hook execution.
- [ ] Optionally add variant that uses ON_TABLE_MAPPED hook to reorder columns.

Definition of done:
- [ ] Integration tests pass and guard the new architecture; referenced in `docs/testing-plan.md`.
