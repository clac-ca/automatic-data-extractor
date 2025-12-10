# Task 17 – Settings integration in engine/pipeline

Checklist: E) Update engine + pipeline to read Settings (not manifest/config writer blocks).

Objective: Wire settings into engine startup and pipeline stages, removing manifest-based toggles.

Implementation steps:
- [ ] Update CLI entry (`apps/ade-engine/src/ade_engine/cli/app.py` / runner) to instantiate `Settings()` once and pass through run context.
- [ ] Replace writer behavior flags with `settings.append_unmapped_columns` and `settings.unmapped_prefix` in render step.
- [ ] Use `settings.mapping_tie_resolution` in mapping tie logic.
- [ ] Allow overriding config package path via settings key `config_package`.
- [ ] Remove manifest-driven defaults; ensure docs reflect settings-driven flow.

Definition of done:
- [ ] Engine boots with Settings; pipeline consumes settings for ordering/ties; no manifest reads for these toggles; covered by unit tests (settings precedence) and integration tests.
