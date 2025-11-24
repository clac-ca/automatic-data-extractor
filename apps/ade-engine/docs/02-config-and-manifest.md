# Config Runtime & Manifest

This document describes how the **ADE engine** discovers and uses a config
package (`ade_config`) and its `manifest.json`, and how that manifest is
represented as Python models inside `ade_engine`.

Read this if you are:

- implementing `ade_engine.config_runtime` modules,
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
- writer / environment defaults.

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

The manifest has a small number of top‑level sections:

```jsonc
{
  "config_script_api_version": "1",
  "info": {
    "schema": "ade.manifest/v1.0",
    "title": "My Config",
    "version": "1.2.3",
    "description": "Optional description"
  },
  "env": {
    "LOCALE": "en-CA",
    "DATE_FMT": "%Y-%m-%d"
  },
  "engine": {
    "defaults": {
      "timeout_ms": 180000,
      "memory_mb": 384,
      "runtime_network_access": false,
      "mapping_score_threshold": 0.35,
      "detector_sample_size": 64
    },
    "writer": {
      "mode": "row_streaming",
      "append_unmapped_columns": true,
      "unmapped_prefix": "raw_",
      "output_sheet": "Normalized"
    }
  },
  "hooks": {
    "on_run_start":     [{ "script": "hooks/on_run_start.py" }],
    "on_after_extract": [{ "script": "hooks/on_after_extract.py" }],
    "on_after_mapping": [{ "script": "hooks/on_after_mapping.py" }],
    "on_before_save":   [{ "script": "hooks/on_before_save.py" }],
    "on_run_end":       [{ "script": "hooks/on_run_end.py" }]
  },
  "columns": {
    "order": ["member_id", "email", "..."],
    "meta": {
      "member_id": {
        "label": "Member ID",
        "script": "column_detectors/member_id.py",
        "required": true,
        "enabled": true,
        "synonyms": ["member id", "member#"],
        "type_hint": "string"
      },
      "email": {
        "label": "Email",
        "script": "column_detectors/email.py",
        "required": true,
        "enabled": true,
        "type_hint": "string"
      }
    }
  }
}
```

Key ideas:

* **`info`** describes the config itself and how to interpret the manifest.
* **`env`** is a small string‑keyed map passed into all scripts.
* **`engine`** controls engine‑side behavior (defaults, writer behavior).
* **`hooks`** defines lifecycle customizations.
* **`columns`** declares what canonical fields exist and how to handle them.

---

## 3. Python schema and `ManifestContext`

### 3.1 `ManifestV1` (Pydantic model)

In `ade_engine/schemas/manifest.py` the manifest is modeled as a Pydantic
class, e.g.:

* `ManifestV1`

  * `config_script_api_version: str`
  * `info: ManifestInfo`
  * `env: dict[str, str]`
  * `engine: EngineConfig` (with `defaults` and `writer`)
  * `hooks: HookCollection`
  * `columns: ColumnSection`

Engine code **never** hard‑codes raw JSON keys; it works with these models.

From the models, the engine can optionally emit JSON Schema
(`ManifestV1.model_json_schema()`) for validation in other systems.

### 3.2 `ManifestContext` helper

At runtime the manifest is wrapped in a lightweight helper:

```python
class ManifestContext:
    raw_json: dict            # original JSON dict
    model: ManifestV1         # validated Pydantic model

    @property
    def columns(self) -> Columns: ...   # provides .order and .meta
    @property
    def engine(self) -> EngineSection: ...  # provides .defaults and .writer
    @property
    def env(self) -> dict[str, str]: ...
```

This gives the pipeline and config runtime a clean, typed surface:

* `ctx.manifest.columns.order` to drive output ordering,
* `ctx.manifest.columns.meta["email"]` to look up script paths and flags,
* `ctx.manifest.engine.defaults.mapping_score_threshold` for mapping,
* `ctx.manifest.engine.writer.append_unmapped_columns` for output behavior,
* `ctx.manifest.env` for script configuration.

The **same `ManifestContext` instance** is stored on `RunContext` and passed to
scripts via the `run` argument (see script API docs).

---

## 4. Loading config at runtime (`config_runtime/`)

### 4.1 Responsibilities of `config_runtime`

The `config_runtime` package is the “glue” between:

* the `ade_config` package and its `manifest.json`, and
* the rest of the engine.

It is responsible for:

1. **Finding and parsing the manifest** into a `ManifestContext` (`manifest_context.py` with `raw_json`, `model`, `columns`, `engine`, `env`).
2. **Resolving scripts** (row detectors, column_detectors field modules, hooks) via `loader.py`.
3. **Building registries** that the pipeline can use:

   * `ConfigRuntime.columns` (column registry from `column_registry.py`),
   * `ConfigRuntime.hooks` (hook registry from `hook_registry.py`),
   * plus convenient access to `env`, defaults, writer, etc.

A typical public entrypoint looks like:

```python
from ade_engine.config_runtime.loader import load_config_runtime

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

* It is a list of canonical field IDs (keys of `columns.meta`).
* It controls:

  * the logical column order in the normalized sheet,
  * tie‑breaking in column mapping (earlier fields win on equal scores),
  * the order in which transforms/validators see fields (if applicable).

If some fields in `columns.meta` are **not** included in `columns.order`, they
are considered defined but not part of the main output ordering. The engine may
still use them if scripts reference them explicitly.

### 5.2 `columns.meta` and `ColumnMeta`

For each canonical field, `columns.meta[field_name]` describes how to handle it.
Typical keys:

* `label: str`
  Human‑friendly column label for the normalized workbook.
* `script: str`
  Path to the column script inside the config package, e.g.
  `"column_detectors/email.py"`.
* `required: bool`
  Whether the field is semantically required (used by validators and reporting).
* `enabled: bool`
  If `false`, the field is ignored by mapping and normalization.
* `synonyms: list[str]`
  Common alternate header names; often used by detectors.
* `type_hint: str`
  Optional scalar type hint (e.g. `"string"`, `"date"`, `"integer"`).

The `ColumnMeta` Pydantic model captures this shape and enforces basic typing.

### 5.3 From `ColumnMeta` to `ColumnModule`

At runtime, `config_runtime` builds a **column registry** from the manifest:

1. For each `field_name` in `columns.meta`:

   * Resolve `script` to a module name:

     ```text
     "column_detectors/email.py"
       → "ade_config.column_detectors.email"
     ```

   * Import the module.

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

When building the registry, `config_runtime` validates that:

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
  "on_run_start": [
    { "script": "hooks/on_run_start.py", "enabled": true }
  ],
  "on_after_extract": [
    { "script": "hooks/on_after_extract.py" }
  ],
  "on_after_mapping": [
    { "script": "hooks/on_after_mapping.py" }
  ],
  "on_before_save": [
    { "script": "hooks/on_before_save.py" }
  ],
  "on_run_end": [
    { "script": "hooks/on_run_end.py" }
  ]
}
```

Each hook entry is a small object with:

* `script: str` — path inside the config package, e.g. `"hooks/on_run_end.py"`.
* Optional `enabled: bool` — defaults to `true` if omitted.

### 6.2 Building the hook registry

`config_runtime` turns the manifest `hooks` section into a `HookRegistry`:

1. For each stage (e.g. `on_run_start`):

   * For each hook entry:

     * Resolve `script` path to a module name:

       ```text
       "hooks/on_run_start.py"
         → "ade_config.hooks.on_run_start"
       ```

     * Import the module.

     * Select an entrypoint:

       * Prefer a `run` function.
       * Fallback to `main` if `run` is absent.
2. Store the callables in order for each stage.

The engine later invokes hooks by stage name, using a standard keyword‑only
signature. Any import or runtime error is surfaced as a clear hook error and
fails the run.

---

## 7. Config `env` and how scripts see it

### 7.1 Manifest `env` section

`env` is a simple key–value map:

```jsonc
"env": {
  "LOCALE": "en-CA",
  "DATE_FMT": "%Y-%m-%d",
  "MAX_ROWS": "500000"
}
```

Characteristics:

* All keys and values are strings in the manifest.
* It is meant for **config‑level settings**, *not* arbitrary environment
  variables from the OS.

### 7.2 Exposure in runtime and scripts

`env` travels through the system as:

* `RunContext.env` (dict of `str → str`).
* A `env` parameter to:

  * row detectors,
  * column detectors,
  * transforms,
  * validators,
  * hooks.

Scripts can then do:

```python
date_fmt = env.get("DATE_FMT", "%Y-%m-%d")
```

Rather than reading `os.environ` directly. This keeps behavior deterministic for
a given manifest and makes configs easier to reason about.

---

## 8. Config runtime aggregate: `ConfigRuntime`

Putting everything together, `config_runtime` exposes a small aggregate object
used by the pipeline:

```python
@dataclass
class ConfigRuntime:
    manifest: ManifestContext
    columns: ColumnRegistry
    hooks: HookRegistry
    # Optional additional views:
    #   defaults, writer, env, etc., as convenience properties.
```

The engine typically does:

```python
cfg = load_config_runtime(package=request.config_package,
                          manifest_path=request.manifest_path)

ctx.manifest = cfg.manifest
# pass `cfg` into pipeline stages for access to column registry and hooks
```

From this point on, **all config behavior** is driven by:

* the manifest model (`cfg.manifest`),
* the column registry (`cfg.columns`),
* the hook registry (`cfg.hooks`),
* and the shared `env` exposed via `RunContext`.

---

## 9. Versioning

Two fields in the manifest control how configs evolve over time:

* `info.schema` (e.g. `"ade.manifest/v1.0"`):

  * Identifies the manifest schema version.
  * Used by the engine and tooling to decide which Pydantic model to use.
* `config_script_api_version` (e.g. `"1"`):

  * Indicates which **script API contract** the config expects
    (parameters of detectors, transforms, validators, hooks).

Guidelines:

* Adding new optional manifest fields or `env` keys is safe.
* Changing or removing manifest fields, or changing script signatures, should:

  * bump either `info.schema` or `config_script_api_version`, and
  * be treated as a breaking change for existing configs.

The ADE backend is responsible for:

* tying a particular **config version** (`info.version`) to a specific venv
  build, and
* ensuring that config and engine versions that share a venv agree on
  `info.schema` and `config_script_api_version`.

With these rules, you can evolve both the engine and config packages without
mysterious runtime breakage.
