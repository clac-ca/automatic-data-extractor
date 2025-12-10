# Task 18 – Remove legacy manifest/loader modules

Checklist: F) Delete `ade_engine/config/*` legacy manifest/loader modules.

Objective: Eliminate old TOML manifest/config loader path now replaced by registry + discovery.

Implementation steps:
- [ ] Identify legacy modules under `apps/ade-engine/src/ade_engine/config/` (loader, manifest parsing, module-string wiring) and remove them.
- [ ] Update imports across engine to point to registry/discovery instead; adjust `__init__.py` exports if needed.
- [ ] Ensure deletion does not break CLI/tests by replacing references with registry-based equivalents.
- [ ] Add short migration note in `docs/legacy-removals.md` (see Task 20) summarizing removal.

Definition of done:
- [ ] No code path imports `ade_engine.config.*`; pipeline/CLI still run via registry path; tests green.
