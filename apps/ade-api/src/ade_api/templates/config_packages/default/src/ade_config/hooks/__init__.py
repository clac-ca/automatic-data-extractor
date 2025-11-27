"""Hook modules that extend the engine at well-defined stages.

Each file here is referenced by the `hooks` section of `manifest.json`
and exposes a single `run(...)` function that receives keyword arguments
mirroring the HookContext fields (`run`, `state`, `manifest`, `tables`,
`workbook`, `result`, `logger`, `stage`). The engine also passes the
full context object via the `context` keyword for backward compatibility.

Transform hooks (after-extract, after-mapping, before-save) should return
the table list/workbook you want the pipeline to continue with; returning
`None` leaves the original object untouched.
"""

__all__ = []
