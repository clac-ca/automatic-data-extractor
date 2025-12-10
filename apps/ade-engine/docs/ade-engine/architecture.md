# ADE Engine Architecture (Registry + Settings)

**Why**
- Manifest wiring was brittle and duplicated filesystem state; registry simplifies wiring and discovery.

**Big picture**
- Config package registers fields/detectors/transforms/validators/hooks via decorators when imported.
- Engine loads settings, imports config package (discovery), then runs pipeline stages against workbooks.

**Components**
- *Settings* (`ade_engine.settings.Settings`) via pydantic-settings.
- *Registry* (`ade_engine.registry.Registry`) holds FieldDefs and registered callables with deterministic ordering.
- *Discovery* (`ade_engine.registry.import_all`) imports all modules under the config package.
- *Pipeline* (detect rows → detect/map columns → hooks → transform → validate → render) with hook points.

**Non-goals**
- No backwards compatibility with TOML manifests or module-string wiring.
- Not intended to sandbox untrusted config code.
