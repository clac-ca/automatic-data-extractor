# Config Packages — Click‑Through Reference (Skeleton)

<a id="top"></a>

**What is a config package?**
An ADE **config package** is an installable Python distribution that contains your spreadsheet rules in a runtime package named **`ade_config`**. It’s built into an isolated virtual environment per configuration and reused for every run (**build once, run many**).

**Where does it live?**
On disk, authored sources are under `${ADE_DATA_DIR}/workspaces/<workspace_id>/config_packages/<config_id>/`.
At build time, ADE installs `ade_engine` + your `ade_config` into `${ADE_DATA_DIR}/workspaces/<workspace_id>/venvs/<config_id>/`.

> **Runtime note:** Workers run in standard Python virtual environments. We don’t hard‑block outbound network traffic (not a true sandbox); keep rules deterministic and minimal, and only reach out to the network if your use‑case truly requires it.

---

## Click‑to‑Navigate Folder Tree

* **my-config/**

  * **[pyproject.toml](#pyproject-toml)**
  * **src/**

    * **ade_config/**

      * **[manifest.json](#manifestjson)**
      * **[config.env](#configenv-optional)** *(optional)*
      * **[column_detectors/](#column_detectors)**

        * **[<field>.py](#column-detectors-fieldpy)**
      * **[row_detectors/](#row_detectors)**

        * **[header.py](#headerpy)**
        * **[data.py](#datapy)**
      * **[hooks/](#hooks)**

        * **[on_job_start.py](#on_job_startpy)**
        * **[after_mapping.py](#after_mappingpy)**
        * **[before_save.py](#before_savepy)**
        * **[on_job_end.py](#on_job_endpy)**
      * **[**init**.py](#initpy)** *(empty; marks package)*

---

## pyproject.toml

<a id="pyproject-toml"></a> [↑ back to top](#top)

```toml
# pyproject.toml — defines the installable ADE config distribution
# Uses src/ layout and the package name "ade_config" for runtime import.

[build-system]
# Choose your preferred build backend (setuptools shown here)
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ade-config-<your-config-id>"      # Must be unique per workspace/config
version = "0.1.0"                          # Bump when you publish a new version
description = "ADE configuration package (detectors, hooks, manifest)"
readme = "README.md"
requires-python = ">=3.11"
# dependencies = [
#   "some-lib>=1.2,<2",                    # Add runtime dependencies if needed
# ]

authors = [{ name = "Your Team", email = "team@example.com" }]
license = { text = "Proprietary" }
keywords = ["ade", "etl", "spreadsheets", "validation"]

[project.urls]
Homepage = "https://your-company.example/ade"

[tool.setuptools]
package-dir = {"" = "src"}                 # src/ layout

[tool.setuptools.packages.find]
where = ["src"]
include = ["ade_config*"]                   # Only ship runtime package

[tool.ade]
# Optional metadata for ADE’s backend/build UI:
min_engine = ">=0.4.0"                      # Minimum engine version expected by this config
tags = ["finance", "hr"]                    # Template tags (search/filter in UI)
display_name = "My Config"                  # Human-readable label in the GUI
```

---

## src/ade_config/manifest.json

<a id="manifestjson"></a> [↑ back to top](#top)

> **Note:** Shown below in **JSONC** (JSON with comments) for teaching. Remove comments in your real file.

```jsonc
{
  // Lock the script API contract used by your detectors/hooks
  "config_script_api_version": "1",

  "info": {
    "schema": "ade.config-manifest/v1",
    "title": "Membership Rules",
    "version": "1.2.0"
  },

  "engine": {
    "defaults": {
      "timeout_ms": 120000,
      "memory_mb": 256,
      "mapping_score_threshold": 0.0      // Gate to leave low-confidence columns unmapped
    },
    "writer": {
      "mode": "row_streaming",
      "append_unmapped_columns": true,
      "unmapped_prefix": "raw_"
    }
  },

  // Key/value settings exposed to your scripts via `env`
  "env": {
    "LOCALE": "en-CA"
  },

  // Lifecycle hooks (see hooks/ section). Each entry is a script path under src/ade_config/
  "hooks": {
    "on_job_start":  [{ "script": "hooks/on_job_start.py" }],
    "after_mapping": [{ "script": "hooks/after_mapping.py" }],
    "before_save":   [{ "script": "hooks/before_save.py" }],
    "on_job_end":    [{ "script": "hooks/on_job_end.py" }]
  },

  // Normalized output columns (order and per-field metadata)
  "columns": {
    "order": ["member_id", "first_name", "department"],
    "meta": {
      "member_id": {
        "label": "Member ID",
        "required": true,
        "script": "column_detectors/member_id.py",
        "synonyms": ["member id", "member#", "id (member)"],
        "type_hint": "string"
      },
      "first_name": {
        "label": "First Name",
        "required": true,
        "script": "column_detectors/first_name.py",
        "synonyms": ["first name", "given name"],
        "type_hint": "string"
      },
      "department": {
        "label": "Department",
        "required": false,
        "script": "column_detectors/department.py",
        "synonyms": ["dept", "division"],
        "type_hint": "string"
      }
    }
  }
}
```

---

## src/ade_config/config.env (optional)

<a id="configenv-optional"></a> [↑ back to top](#top)

```dotenv
# config.env — loaded by the engine before importing detectors/hooks
# Use UPPER_CASE keys and simple values; no quoting required unless needed.

LOCALE=en-CA
COUNTRY=CA
DATE_FMT=%Y-%m-%d

# Example feature flags for your scripts:
ENABLE_FUZZY_MATCH=0
STRICT_VALIDATION=1
```

---

## src/ade_config/column_detectors/

<a id="column_detectors"></a> [↑ back to top](#top)

Each file in this folder teaches ADE how to **map → transform (optional) → validate (optional)** one normalized field.

### src/ade_config/column_detectors/<field>.py

<a id="column-detectors-fieldpy"></a>

```python
"""
<field>.py — field-specific logic:
  1) detect_* functions (mapping)
  2) transform(values=...) (optional)
  3) validate(values=...) (optional)
All functions are keyword-only; accept **_ to allow forward-compat kwargs.
"""

# 1) Mapping detectors — return score deltas for THIS field
def detect_header_synonyms(
    *,
    header: str | None,
    values_sample: list,
    field_name: str,
    field_meta: dict,
    manifest: dict,
    env: dict | None = None,
    artifact: dict | None = None,
    **_,
) -> dict:
    """
    Example: boost confidence when header includes known synonyms.
    Return shape: {"scores": {field_name: float}}
    """
    score = 0.0
    if header:
        h = header.lower()
        for word in (field_meta.get("synonyms") or []):
            if word in h:
                score += 0.6
    return {"scores": {field_name: score}}

# 2) Transform — normalize/clean values for this field (optional)
def transform(
    *,
    values: list,          # full column values in row order
    field_name: str,
    field_meta: dict,
    manifest: dict,
    env: dict | None = None,
    artifact: dict | None = None,
    **_,
) -> dict:
    """
    Return shape: {"values": list, "warnings": list[str]}
    Keep it pure and deterministic; match output length to input length.
    """
    def _clean(v):
        return None if v in ("", None) else str(v).strip()
    return {"values": [_clean(v) for v in values], "warnings": []}

# 3) Validate — report issues without changing values (optional)
def validate(
    *,
    values: list,
    field_name: str,
    field_meta: dict,
    manifest: dict,
    env: dict | None = None,
    artifact: dict | None = None,
    **_,
) -> dict:
    """
    Return shape:
      {"issues": [{"row_index": int, "code": "required_missing", "severity": "error", "message": str}, ...]}
    Use stable machine-readable codes so dashboards can aggregate reliably.
    """
    issues = []
    if field_meta.get("required"):
        for i, v in enumerate(values, start=1):
            if v in ("", None):
                issues.append({
                    "row_index": i,
                    "code": "required_missing",
                    "severity": "error",
                    "message": f"{field_name} is required."
                })
    return {"issues": issues}
```

---

## src/ade_config/row_detectors/

<a id="row_detectors"></a> [↑ back to top](#top)

These scripts score each row as header/data so ADE can infer table boundaries and header rows.

### src/ade_config/row_detectors/header.py

<a id="headerpy"></a>

```python
"""
header.py — vote for rows that look like headers (e.g., text density, formatting cues).
Return shape per detector: {"scores": {"header": float}}  (positive increases likelihood)
"""

def detect_text_density(
    *,
    row_values_sample: list,
    manifest: dict,
    env: dict | None = None,
    artifact: dict | None = None,
    **_,
) -> dict:
    non_blank = [c for c in row_values_sample if c not in (None, "")]
    textish   = sum(1 for c in non_blank if isinstance(c, str))
    ratio     = textish / max(1, len(non_blank))
    return {"scores": {"header": +0.6 if ratio >= 0.7 else 0.0}}
```

### src/ade_config/row_detectors/data.py

<a id="datapy"></a>

```python
"""
data.py — vote for rows that look like data.
Return shape per detector: {"scores": {"data": float}}
"""

def detect_numeric_presence(
    *,
    row_values_sample: list,
    **_,
) -> dict:
    nums = sum(str(v).replace(".", "", 1).isdigit() for v in row_values_sample if v not in ("", None))
    return {"scores": {"data": +0.4 if nums >= 1 else 0.0}}
```

---

## src/ade_config/hooks/

<a id="hooks"></a> [↑ back to top](#top)

Hooks run at predictable phases with the same structured context. Return `None` or a small dict
(e.g., `{"notes": "text"}`) to annotate the artifact.

### src/ade_config/hooks/on_job_start.py

<a id="on_job_startpy"></a>

```python
def run(
    *,
    job_id: str,
    manifest: dict,
    env: dict | None = None,
    artifact: dict | None = None,
    **_,
):
    # Initialize shared state, load reference data, or write a note to the audit trail.
    return {"notes": "Job starting"}
```

### src/ade_config/hooks/after_mapping.py

<a id="after_mappingpy"></a>

```python
def run(
    *,
    job_id: str,
    manifest: dict,
    env: dict | None = None,
    artifact: dict | None = None,
    table: dict | None = None,  # current table mapping summary
    **_,
):
    # Inspect/adjust mappings (e.g., fix mislabeled headers, reorder fields).
    return None
```

### src/ade_config/hooks/before_save.py

<a id="before_savepy"></a>

```python
def run(
    *,
    job_id: str,
    manifest: dict,
    env: dict | None = None,
    artifact: dict | None = None,
    book: object | None = None,  # engine-provided workbook handle
    **_,
):
    # Add summary tabs, rename sheets, tweak formatting before output is written.
    return {"notes": "Prepared workbook for saving"}
```

### src/ade_config/hooks/on_job_end.py

<a id="on_job_endpy"></a>

```python
def run(
    *,
    job_id: str,
    manifest: dict,
    env: dict | None = None,
    artifact: dict | None = None,
    **_,
):
    # Clean up temporary resources, aggregate issues, emit final notes.
    return {"notes": "Job complete"}
```

---

## src/ade_config/**init**.py

<a id="initpy"></a> [↑ back to top](#top)

```python
# This file can be empty; it simply marks src/ade_config/ as a Python package.
```

---

### Next

* Build the environment from the UI, then run a sample job with your new config.
* In a second pass, we’ll replace the stubs above with real detectors, transforms, validators, and hook logic.
