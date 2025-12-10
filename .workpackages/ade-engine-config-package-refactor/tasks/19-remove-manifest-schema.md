# Task 19 – Remove manifest schema plumbing

Checklist: F) Delete `ade_engine/schemas/manifest.py` (and any manifest schema plumbing).

Objective: Remove obsolete Pydantic/dataclass schemas that modeled the TOML manifest.

Implementation steps:
- [ ] Delete `apps/ade-engine/src/ade_engine/schemas/manifest.py` and any related validators/typing alias consumed only by manifest loader.
- [ ] Rip out references from codebase; adjust `__init__.py` exports and test fixtures accordingly.
- [ ] Update docs to reflect removal (see Task 20) and ensure no import errors remain.

Definition of done:
- [ ] Manifest schema file gone; no remaining imports; repository lint/tests pass.
