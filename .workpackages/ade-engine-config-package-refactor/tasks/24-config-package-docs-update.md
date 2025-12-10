# Task 24 – Config package docs/README refresh

Checklist: G) Update config package README/docs to new approach.

Objective: Align config package docs with registry/discovery and hook-based ordering.

Implementation steps:
- [ ] Update `config_package_example/README.md` and docs under `config_package_example/docs/` to remove manifest references and highlight decorator registration and hook-based reordering.
- [ ] Include short how-to for adding a new column file and where to configure settings (`ade_engine.toml` / `.env`).
- [ ] Sync terminology with engine docs (Row Detectors, Column Detectors, Column Transforms, Column Validators, Hooks).

Definition of done:
- [ ] Template docs describe registry-based workflow, per-field modules, settings file; examples compile with new engine API.
