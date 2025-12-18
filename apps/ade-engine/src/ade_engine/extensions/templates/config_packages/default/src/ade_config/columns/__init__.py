"""ADE config package: column modules (`ade_config.columns`)

Convention (recommended)
------------------------
- One module per canonical field (e.g. `email.py`).
- Each module defines `register(registry) -> None` and typically registers:
  - a `FieldDef` (the canonical field)
  - (enabled by default) a simple header-name detector
  - optional examples (value detectors / transforms / validators), commented out

Pipeline stages (mental model)
------------------------------
- Column detectors run BEFORE mapping and return score patches: `{field: score}`.
- Column transforms/validators run AFTER mapping, operating on canonical field names.

The top-level `ade_config.register()` auto-discovers and registers these modules.
"""
