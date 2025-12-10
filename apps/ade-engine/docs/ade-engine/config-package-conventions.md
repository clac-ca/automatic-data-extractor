# Config Package Conventions (ade_config)

A config package is a normal Python package imported by the engine. Decorators register capabilities on import; no manifest required.

**Recommended layout**
```
ade_config/
  __init__.py
  columns/
    email.py
    first_name.py
  rows/
    header.py
    data.py
  hooks/
    on_table_mapped.py
    on_workbook_before_save.py
```

**One file per column** keeps detectors, transforms, and validators together.

Naming: keep function names descriptive; registry ordering uses module/qualname only for tie-breaking.

Add new logic by creating a `.py` file, importing decorators, and defining functions—no manifest edits.
