# Config Runtime & Manifest

This document describes how the **ADE engine** discovers and uses a config
package (`ade_config`) and its `manifest.json`, and how that manifest is
represented as Python models inside `ade_engine`.

Read this if you are:

- implementing `ade_engine.config` modules (legacy package name: `config_runtime`),
- authoring or reviewing a config package,
- or wiring config‑driven behavior into new parts of the engine.

---

## 1. What a config package is

At runtime, the engine expects **one Python package** that defines all
business‑specific behavior:

- which columns exist and in what order,
- how to detect tables and fields,
- how to normalize and validate values,
- which hooks to run at various stages, and
- writer defaults and other engine hints.

By default this package is named **`ade_config`** and is installed into the same
virtual environment as `ade_engine`.

Conceptually:

```text
ade_config/                     # business logic (per customer / per config)
  __init__.py
  manifest.json                 # required manifest file
  row_detectors/                # optional: header/data row detectors
    __init__.py
    header.py
    data.py
  column_detectors/             # detectors + transform + validate per field
    __init__.py
    member_id.py
    email.py
    ...
  hooks/                        # lifecycle hooks
    __init__.py
    on_run_start.py
    on_after_extract.py
    on_after_mapping.py
    on_before_save.py
    on_run_end.py
  _shared.py                    # optional helper code shared across scripts
````

The **engine is generic**. Everything domain‑specific lives in this package and
is defined by the manifest.

## Terminology

| Concept        | Term in code      | Notes                                                     |
| -------------- | ----------------- | --------------------------------------------------------- |
| Run            | `run`             | One call to `Engine.run()` or one CLI invocation          |
| Config package | `config_package`  | Installed `ade_config` package for this run               |
| Config version | `manifest.version`| Version declared by the config package manifest           |
| Build          | build             | Virtual environment built for a specific config version   |
| User data file | `source_file`     | Original spreadsheet on disk                              |
| User sheet     | `source_sheet`    | Worksheet/tab in the spreadsheet                          |
| Canonical col  | `field`           | Defined in manifest; never call this a “column”           |
| Physical col   | column            | B / C / index 0,1,2… in a sheet                           |
| Output workbook| normalized workbook| Written to `output_dir`; includes mapped + normalized data|

Stick to these names in manifest prose and type names to avoid synonyms like
“input file” or “column” when you mean manifest **field**.

---

## 2. The manifest: single source of truth

### 2.1 Location and format

The manifest is a JSON file shipped with the config package:

* Default path: `<config_package>/manifest.json`.
* Optional override: a `--manifest-path` CLI flag or `RunRequest.manifest_path`
  can point to a different file.
* Encoding: UTF‑8 JSON.

Although it is stored as JSON, the **schema is defined in Python** in
`ade_engine.schemas.manifest` (see section 3). The JSON is just data; the
Python models are authoritative.

### 2.2 High‑level structure

The manifest has a small number of top-level sections:

```jsonc
{
  "schema": "ade.manifest/v1",
  "version": "1.2.3",
  "name": "My Config",
  "description": "Optional description",
  "script_api_version": 2,

  "columns": {
    "order": ["member_id", "email", "..."],
    "fields": {
      "member_id": {
        "label": "Member ID",
        "module": "column_detectors.member_id",
        "required": true,
        "synonyms": ["member id", "member#"],
        "type": "string"
      },
      "email": {
        "label": "Email",
        "module": "column_detectors.email",
        "required": true,
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

Key ideas:

- **Top-level fields** describe the config itself and the script API version.
- **Fields vs columns**: use **field** for manifest entries; **column** refers to physical spreadsheet columns. `columns.order` lists field IDs; `columns.fields` maps those IDs to `FieldConfig` objects.
- **Module paths** are relative to `ade_config` and start with `column_detectors.<field_name>` or `hooks.<hook_name>`.
- **Script API version** lives at `script_api_version`; do not shorten it to “API version” in prose.
- **`hooks`** defines lifecycle customizations (as module lists).
- **`writer`** controls writer behavior (unmapped handling, sheet name).

---

## 3. Python schema and `ManifestContext`

### 3.1 `ManifestV1` (Pydantic model)

In `ade_engine/schemas/manifest.py` the manifest is modeled as a Pydantic
class, e.g.:

* `ManifestV1`

  * `schema: str`
  * `version: str`
  * `name: str | None`
  * `description: str | None`
  * `script_api_version: int`
  * `columns: ColumnsConfig`   # field-centric naming; avoid ColumnSection/ColumnField
  * `hooks: HookCollection`
  * `writer: WriterConfig`

Engine code **never** hard‑codes raw JSON keys; it works with these models.

From the models, the engine can optionally emit JSON Schema
(`ManifestV1.model_json_schema()`) for validation in other systems.

Model naming stays **field-first**: prefer `FieldConfig` over `ColumnField` or
`ColumnMeta`, and keep `ColumnsConfig.fields: dict[str, FieldConfig]` keyed by
field ID.

### 3.2 `ManifestContext` helper

At runtime the manifest is wrapped in a lightweight helper:

```python
class ManifestContext:
    raw_json: dict            # original JSON dict
    model: ManifestV1         # validated Pydantic model

    @property
    def columns(self) -> Columns: ...   # provides .order and .fields
    @property
    def writer(self) -> WriterConfig: ...
```

This gives the pipeline and config runtime a clean, typed surface exposed via
`RunContext` and script entrypoints (row detectors, column detectors, hooks):

* `run.manifest.columns.order` to drive output ordering,
* `run.manifest.columns.fields["email"]` to look up script modules and labels,
* `run.manifest.writer.append_unmapped_columns` for output behavior.

The **same `ManifestContext` instance** is stored on `RunContext` and passed to
scripts via the `run` argument (see script API docs).

---

## 4. Loading config at runtime (`config/`, legacy `config_runtime/`)

### 4.1 Responsibilities of `config`

The `config` package is the “glue” between:

* the `ade_config` package and its `manifest.json`, and
* the rest of the engine.

It is responsible for:

1. **Finding and parsing the manifest** into a `ManifestContext` (`manifest_context.py` with `raw_json`, `model`, `columns`, `engine`).
2. **Resolving scripts** (row detectors, column_detectors field modules, hooks) via `loader.py`.
3. **Building registries** that the pipeline can use:

   * `ConfigRuntime.columns` (column registry from `column_registry.py`),
   * `ConfigRuntime.hooks` (hook registry from `hook_registry.py`),
   * plus convenient access to defaults, writer, etc.

A typical public entrypoint looks like:

```python
from ade_engine.config.loader import load_config_runtime  # legacy path: ade_engine.config_runtime.loader

cfg = load_config_runtime(
    package="ade_config",
    manifest_path=None,
)
```

### 4.2 Manifest resolution rules

The manifest is resolved with a simple algorithm:

1. Import the config package:

   ```python
   pkg = importlib.import_module(package)
   ```

2. Determine manifest path:

   * If `manifest_path` is provided:

     * Use that file.
   * Else:

     * Use `importlib.resources.files(pkg) / "manifest.json"`.

3. Read and parse JSON.

4. Validate via `ManifestV1.model_validate(raw)`.

5. Wrap as `ManifestContext`.

Any structural error in `manifest.json` should fail fast here, **before** any
pipeline work starts.

---

## 5. Column metadata and column registry

### 5.1 `columns.order`

`columns.order` defines the **canonical field order** in the normalized
workbook:

* It is a list of canonical field IDs (keys of `columns.fields`).
* It controls:

  * the logical column order in the normalized sheet,
  * tie‑breaking in column mapping (earlier fields win on equal scores),
  * the order in which transforms/validators see fields (if applicable).

If some fields in `columns.fields` are **not** included in `columns.order`, they
are considered defined but not part of the main output ordering. The engine may
still use them if scripts reference them explicitly.

### 5.2 `columns.fields` and `ColumnField`

For each canonical field, `columns.fields[field_name]` describes how to handle it.
Typical keys:

* `label: str`
  Human‑friendly column label for the normalized workbook.
* `module: str`
  Python module path inside the config package, e.g.
  `"column_detectors.email"`.
* `required: bool`
  Whether the field is semantically required (used by validators and reporting).
* `synonyms: list[str]`
  Common alternate header names; often used by detectors.
* `type: str`
  Optional scalar type hint (e.g. `"string"`, `"date"`, `"integer"`).

The `ColumnField` Pydantic model captures this shape and enforces basic typing.

### 5.3 From `ColumnMeta` to `ColumnModule`

At runtime, the config loader builds a **column registry** from the manifest:

1. For each `field_name` in `columns.fields`:

   * Use the `module` string directly (already a Python import path, e.g. `"column_detectors.email"`).
   * Import the module as `ade_config.<module>`.

2. For each module:

   * Collect all `detect_*` callables (column detectors).
   * Optionally record:

     * `transform` function.
     * `validate` function.

3. Wrap this into a `ColumnModule` object, e.g.:

   ```python
   @dataclass
   class ColumnModule:
       field: str
       definition: ColumnMeta
       module: ModuleType
       detectors: list[Callable]
       transformer: Callable | None
       validator: Callable | None
   ```

4. Store in a `ColumnRegistry` keyed by `field` name.

Mapping and normalization code later uses this registry rather than inspecting
modules directly.

### 5.4 Signature validation

When building the registry, the loader validates that:

* Detectors, transformers, and validators are callable.
* Functions support the expected keyword‑only API.

If a function is missing or has an incompatible signature, the engine treats
this as a **config error** and fails loading before processing any input.

---

## 6. Hooks in the manifest and hook registry

### 6.1 Manifest `hooks` section

The `hooks` section describes which scripts to run at each lifecycle stage:

```jsonc
"hooks": {
  "on_run_start": ["hooks.on_run_start"],
  "on_after_extract": ["hooks.on_after_extract"],
  "on_after_mapping": ["hooks.on_after_mapping"],
  "on_before_save": ["hooks.on_before_save"],
  "on_run_end": ["hooks.on_run_end"]
}
```

Each hook entry is a module string inside the config package (Python import path).

### 6.2 Building the hook registry

The loader turns the manifest `hooks` section into a `HookRegistry`:

1. For each stage (e.g. `on_run_start`):

   * For each hook module string:

     * Import the module as `ade_config.<module>`.

     * Select an entrypoint:

       * Prefer a `run` function.
       * Fallback to `main` if `run` is absent.
2. Store the callables in order for each stage.

The engine later invokes hooks by stage name, using a standard keyword‑only
signature. Any import or runtime error is surfaced as a clear hook error and
fails the run.

---

## 7. Config runtime aggregate: `ConfigRuntime`

Putting everything together, the loader exposes a small aggregate object
used by the pipeline:

```python
@dataclass
class ConfigRuntime:
    manifest: ManifestContext
    columns: ColumnRegistry
    hooks: HookRegistry
    # Optional additional views:
    #   defaults, writer, etc., as convenience properties.
```

The engine typically does:

```python
cfg = load_config_runtime(
    package=request.config_package,
    manifest_path=request.manifest_path,
)

run_context.manifest = cfg.manifest
# pass `cfg` into pipeline stages for access to column registry and hooks
```

From this point on, **all config behavior** is driven by:

* the manifest model (`cfg.manifest`),
* the column registry (`cfg.columns`),
* the hook registry (`cfg.hooks`).

---

## 8. Versioning

Two fields in the manifest control how configurations evolve over time:

* `schema` (e.g. `"ade.manifest/v1"`):

  * Identifies the manifest schema version.
  * Used by the engine and tooling to decide which Pydantic model to use.
* `script_api_version` (e.g. `2`):

  * Indicates which **script API contract** the config expects
    (parameters of detectors, transforms, validators, hooks).

Guidelines:

* Adding new optional manifest fields is safe.
* Changing or removing manifest fields, or changing script signatures, should:

  * bump either `schema` or `script_api_version`, and
  * be treated as a breaking change for existing configurations.

The ADE backend is responsible for:

* tying a particular **config version** (`version`) to a specific venv
  build, and
* ensuring that config and engine versions that share a venv agree on
  `schema` and `script_api_version`.

With these rules, you can evolve both the engine and config packages without
mysterious runtime breakage.
