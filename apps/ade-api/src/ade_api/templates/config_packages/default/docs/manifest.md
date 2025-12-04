# Manifest

`manifest.json` is the **entry point** for an ADE workspace.
It defines:

* Which fields your pipeline extracts
* Which detector modules map those fields
* Which hooks are active
* Writer settings for the final Excel output
* The Script API version (must be `3` for this template)

Below is the template manifest used in this example workspace.

```json
{
  "schema": "ade.manifest/v1",
  "version": "1.6.0",
  "name": "Default ADE Workspace Config",
  "description": "Starter config",
  "script_api_version": 3,

  "columns": {
    "order": ["first_name", "last_name", "email"],
    "fields": {
      "first_name": {
        "label": "First Name",
        "module": "column_detectors.first_name",
        "required": false
      },
      "last_name": {
        "label": "Last Name",
        "module": "column_detectors.last_name",
        "required": false
      },
      "email": {
        "label": "Email",
        "module": "column_detectors.email",
        "required": true
      }
    }
  },

  "hooks": {
    "on_run_start": ["hooks.on_run_start"],
    "on_after_extract": ["hooks.on_after_extract"],
    "on_after_mapping": ["hooks.on_after_mapping"],
    "on_before_save": ["hooks.on_before_save"],
    "on_run_end": ["hooks.on_run_end"]
  },

  "writer": {
    "append_unmapped_columns": true,
    "unmapped_prefix": "raw_",
    "output_sheet": "Normalized"
  }
}
```

---

## Key Concepts

### ✔ `script_api_version`

Must be set to **3**.
This determines the function signatures and hook behaviors used by your Python scripts.

---

## Column Configuration

### `columns.order`

Controls the **output order** of columns in the final workbook.

### `columns.fields`

Each field defines:

| Key          | Meaning                                                        |
| ------------ | -------------------------------------------------------------- |
| **label**    | Human-friendly name for the output header.                     |
| **module**   | Path (relative to `ade_config`) to the Python detector module. |
| **required** | Whether this field must be mapped; errors if missing.          |

Example:

```json
"first_name": {
  "label": "First Name",
  "module": "column_detectors.first_name",
  "required": false
}
```

The engine imports the module and calls its `detect_*` and optional `transform` functions.

---

## Hook Configuration

Each hook stage lists one or more modules to load:

```json
"on_after_extract": ["hooks.on_after_extract"]
```

Paths are **relative to the `ade_config` package root**.

Stages correspond to lifecycle callbacks:

1. `on_run_start`
2. `on_after_extract`
3. `on_after_mapping`
4. `on_before_save`
5. `on_run_end`

Each script must implement a keyword-only `run(...)` hook function.

---

## Writer Configuration

Controls how the final Excel workbook is produced.

| Key                         | Function                                          |
| --------------------------- | ------------------------------------------------- |
| **append_unmapped_columns** | Include columns that weren’t mapped.              |
| **unmapped_prefix**         | Prefix applied to unmapped column names.          |
| **output_sheet**            | Name of the worksheet containing normalized data. |

The writer takes care of sheet creation and column output order.

---

## Summary

* The manifest determines the entire pipeline behavior.
* Modules (detectors + hooks) are referenced by string import paths.
* Script API v3 defines the signatures and lifecycle used by your scripts.
* This template keeps things intentionally simple: three fields, five hooks, and a clean Excel writer configuration.
