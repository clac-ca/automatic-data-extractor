"""Column detectors/transforms/validators.

Convention (recommended):
- One module per canonical field (e.g. `email.py`)
- Each module defines `register(registry)` and registers:
  - a FieldDef (the canonical field)
  - (enabled by default) a simple header-name detector
  - optional examples (value detectors / transforms / validators), commented out

The top-level `ade_config.register()` auto-discovers these modules.
"""
