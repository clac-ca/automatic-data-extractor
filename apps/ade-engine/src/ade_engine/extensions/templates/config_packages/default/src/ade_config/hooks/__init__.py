"""Lifecycle hooks.

Hooks let you customize how ADE runs without changing the engine:
- seed state at workbook start
- capture per-sheet info
- reorder/add columns after mapping/transforms/validation
- format the output workbook after writing
- add summary sheets before save

Each hook module defines `register(registry)`.
"""
