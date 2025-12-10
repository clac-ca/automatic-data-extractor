# Config package anatomy

A config package is just a Python package that registers plugins.

## Plugin types

- **Row Detectors**: vote `header` vs `data` while scanning rows to locate header row(s).
- **Column Detectors**: vote which canonical field a column represents (can also downvote other fields).
- **Column Transforms**: normalize values (return new list).
- **Column Validators**: return per-cell booleans (for reporting only).
- **Hooks**: run during the pipeline lifecycle to customize behavior.

## Discovery

The engine imports all submodules under `ade_config` and looks for decorators that registered plugins.
So adding a new `.py` file is enough.

## Keep imports lightweight

Avoid doing any network or heavy computation at import time.
Only *register* callables at import time. Do heavy work inside functions (detectors/hooks/etc.).
