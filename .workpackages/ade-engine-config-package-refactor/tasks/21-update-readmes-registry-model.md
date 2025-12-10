# Task 21 – Update README(s) to registry config model

Checklist: F) Update README(s) to the new “registry config package” model.

Objective: Refresh top-level and engine/config package READMEs to describe registry/discovery, settings, and output ordering defaults.

Implementation steps:
- [ ] Update repo `README.md` (and `apps/ade-engine/README.md` if present) to remove manifest references and explain config package as Python package with decorators.
- [ ] Include quickstart snippet using `python -m ade_engine run --config-package ...` and mention settings keys for ordering.
- [ ] Verify consistency with template README (`config_package_example/README.md`) and docs summary.

Definition of done:
- [ ] READMEs accurately reflect registry-based architecture and settings; no stale manifest instructions remain.
