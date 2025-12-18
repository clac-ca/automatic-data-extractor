"""Column detectors/transforms/validators.

Convention (recommended):
- One module per canonical field (e.g. `email.py`)
- Each module defines `register(registry)` and registers:
  - a FieldDef (the canonical field)
  - 1+ column detectors (header and/or values)
  - optional transforms and validators

The top-level `ade_config.register()` auto-discovers these modules.
"""
