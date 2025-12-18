"""ADE config package: row detector modules (`ade_config.row_detectors`)

Row detectors vote on what each row represents (`header`, `data`, etc.). ADE runs
them early to find table regions in messy spreadsheets.

Convention (recommended)
------------------------
- Each module defines `register(registry) -> None`.
- Register one or more detectors with `registry.register_row_detector(...)`.

The top-level `ade_config.register()` auto-discovers and registers these modules.
"""
