# ADE Manifest Configuration

This document explains how to author and maintain the ADE manifest file.

The manifest is a **JSON configuration** that tells ADE:

* What version/schema of the manifest format is being used
* What columns to detect and how to map them
* Which hook scripts to run at different points in the pipeline
* How to write the final, normalized output

Typical location: `manifest.json` (or similar) at the root of your workspace, referenced by your ADE runner.

---

## Full Example

```json
{
  "schema": "ade.manifest/v1",
  "version": "0.2.0",
  "name": "Default ADE Workspace Config",
  "description": "Starter config that detects a simple person/member schema.",
  "script_api_version": 3,
  "columns": {
    "order": ["member_id", "email", "first_name", "last_name"],
    "fields": {
      "member_id": {
        "label": "Member ID",
        "module": "column_detectors.member_id",
        "required": true,
        "synonyms": ["member id", "member#", "member no", "member number"],
        "type": "string"
      },
      "email": {
        "label": "Email",
        "module": "column_detectors.email",
        "required": true,
        "synonyms": ["email", "email address", "e-mail"],
        "type": "string"
      },
      "first_name": {
        "label": "First Name",
        "module": "column_detectors.first_name",
        "required": false,
        "synonyms": ["first name", "given name", "fname"],
        "type": "string"
      },
      "last_name": {
        "label": "Last Name",
        "module": "column_detectors.last_name",
        "required": false,
        "synonyms": ["last name", "surname", "family name", "lname"],
        "type": "string"
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

## Top-Level Fields

### `schema` (string)

Identifies the manifest schema version understood by ADE.

* Example: `"schema": "ade.manifest/v1"`

Changing this usually corresponds to a breaking change in the manifest structure.

---

### `version` (string)

A free-form version string for **your** configuration (not ADE itself).

* Used for your own tracking, migrations, and debugging
* Example: `"version": "0.2.0"`

---

### `name` (string)

Human-friendly name for this manifest / workspace.

* Example: `"name": "Default ADE Workspace Config"`

Shown in logs, UIs, or other tooling to distinguish between different manifests.

---

### `description` (string)

Short description of what this manifest is for.

* Example:
  `"description": "Starter config that detects a simple person/member schema."`

---

### `script_api_version` (number)

Indicates which **hook/column-detector script API** version this manifest expects.

* Example: `"script_api_version": 3`
* Your detector modules and hook functions must be compatible with this API version (`logger` + `event_emitter` keyword args are required).

---

## Column Configuration (`columns`)

The `columns` object defines **what normalized fields you care about** and how ADE should detect them in incoming data.

```json
"columns": {
  "order": ["member_id", "email", "first_name", "last_name"],
  "fields": {
    "...": { /* column definition */ }
  }
}
```

### `columns.order` (array of strings)

Defines the **output order** of normalized columns.

* Each entry corresponds to a key inside `columns.fields`
* The writer uses this to determine how to order columns when emitting the normalized output

Example:

```json
"order": ["member_id", "email", "first_name", "last_name"]
```

---

### `columns.fields` (object)

A map of **normalized field keys** → **column definition**.

Each key (e.g. `"member_id"`, `"email"`) is a machine name for the field and maps to a configuration object.

Example:

```json
"fields": {
  "member_id": { ... },
  "email": { ... },
  "first_name": { ... },
  "last_name": { ... }
}
```

Each field definition usually supports:

#### `label` (string)

Human-friendly name for the column.

* Used in UIs, logs, and possibly header generation
* Example: `"label": "Member ID"`

#### `module` (string)

Fully-qualified Python module path to a **column detector**.

* Example: `"module": "column_detectors.member_id"`
* ADE will import this module and call its detection logic to:

  * Recognize the column from raw inputs (e.g. based on header names and sample values)
  * Optionally perform validation / normalization per cell

> Note: Exact detector function names are defined by the script API (see `script_api_version`).

#### `required` (boolean)

Whether this field **must** be present in the input/mapping for the run to be considered valid.

* `true` – ADE may fail or mark the run as incomplete if this field cannot be detected/mapped.
* `false` – Optional field; if not found, ADE continues but the column may be omitted or null in the output.

Example:

```json
"required": true
```

#### `synonyms` (array of strings)

Alternative names / phrases that may appear in source data headers referring to this concept.

* Used by detectors to recognize a column from header text
* Examples for `member_id`:

  ```json
  "synonyms": ["member id", "member#", "member no", "member number"]
  ```

The detector may use these plus its own heuristics to match columns.

#### `type` (string)

Logical/semantic data type of the column.

* Common values (example set): `"string"`, `"number"`, `"date"`, etc.
* In the sample, all are `"string"`:

  ```json
  "type": "string"
  ```

Detectors and writers can use this to validate and serialize values.

---

### Example: Column Definitions

```json
"fields": {
  "member_id": {
    "label": "Member ID",
    "module": "column_detectors.member_id",
    "required": true,
    "synonyms": ["member id", "member#", "member no", "member number"],
    "type": "string"
  },
  "email": {
    "label": "Email",
    "module": "column_detectors.email",
    "required": true,
    "synonyms": ["email", "email address", "e-mail"],
    "type": "string"
  },
  "first_name": {
    "label": "First Name",
    "module": "column_detectors.first_name",
    "required": false,
    "synonyms": ["first name", "given name", "fname"],
    "type": "string"
  },
  "last_name": {
    "label": "Last Name",
    "module": "column_detectors.last_name",
    "required": false,
    "synonyms": ["last name", "surname", "family name", "lname"],
    "type": "string"
  }
}
```

---

## Hooks (`hooks`)

Hooks define **custom logic** to run at well-defined points in the ADE pipeline.

```json
"hooks": {
  "on_run_start": ["hooks.on_run_start"],
  "on_after_extract": ["hooks.on_after_extract"],
  "on_after_mapping": ["hooks.on_after_mapping"],
  "on_before_save": ["hooks.on_before_save"],
  "on_run_end": ["hooks.on_run_end"]
}
```

Each hook key maps to an **array of module paths** (strings). Each path should point to a callable defined by the given `script_api_version`.

### Lifecycle Hook Points

* `on_run_start`
  Called at the very beginning of the run.
  Typical uses:

  * Global initialization
  * Reading external configuration
  * Logging metadata about the run

* `on_after_extract`
  Invoked after raw data has been extracted but before mapping.
  Typical uses:

  * Cleaning or filtering raw rows
  * Detecting special conditions in the input

* `on_after_mapping`
  Invoked after column mapping and normalization have occurred.
  Typical uses:

  * Row-level validations
  * Post-processing derived fields

* `on_before_save`
  Invoked right before data is written to the final output.
  Typical uses:

  * Final quality checks
  * Aggregations or summaries
  * Enforcing business constraints

* `on_run_end`
  Called at the very end of the run, regardless of success/failure (depending on implementation).
  Typical uses:

  * Cleanup
  * Notifications
  * Final logging

Each hook entry is an array, so you can chain multiple handlers:

```json
"on_after_mapping": [
  "hooks.audit_mappings",
  "hooks.enforce_business_rules"
]
```

---

## Writer Configuration (`writer`)

The `writer` block configures how ADE emits the final normalized data.

```json
"writer": {
  "append_unmapped_columns": true,
  "unmapped_prefix": "raw_",
  "output_sheet": "Normalized"
}
```

### `append_unmapped_columns` (boolean)

Controls whether **columns that were not mapped** to a known field should still be included in the output.

* `true` – Keep unmapped columns, prefixed by `unmapped_prefix`.
* `false` – Drop unmapped columns entirely.

Example: if the input has a column `"Favorite Color"` that no detector picks up:

* With `append_unmapped_columns: true` and `unmapped_prefix: "raw_"`, you might see a column named `raw_Favorite Color` in the output.

---

### `unmapped_prefix` (string)

Prefix applied to unmapped column names when `append_unmapped_columns` is `true`.

* Example: `"unmapped_prefix": "raw_"`

This helps distinguish raw/unmapped columns from normalized fields.

---

### `output_sheet` (string)

Name of the **output sheet or table** the writer should target.

* How this is used depends on the writer backend (e.g. Excel worksheet name, database table alias, etc.).
* Example: `"output_sheet": "Normalized"`

---

## Extending Your Manifest

To adapt the manifest to your domain:

1. **Add new normalized fields** under `columns.fields`

   * Choose a machine key (e.g. `"date_of_birth"`)
   * Provide `label`, `module`, `required`, `synonyms`, and `type`.

2. **Update the `columns.order` array**

   * Add the new key in the position you want it to appear in the output.

3. **Implement or update detector modules**

   * Make sure the Python modules referenced by `module` exist and follow the `script_api_version` contract.

4. **Add or update hooks**

   * Implement custom logic in your `hooks.*` modules.
   * Register them under the appropriate lifecycle stages in `hooks`.

5. **Tune writer settings**

   * Decide how to handle unmapped data (`append_unmapped_columns`, `unmapped_prefix`).
   * Set `output_sheet` according to your downstream consumer.

This manifest file becomes the single source of truth for how ADE interprets and normalizes your incoming data.
