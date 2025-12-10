# Engine settings (.env / env vars / TOML)

ADE Engine moves “engine behavior knobs” out of the config package (and out of `manifest.toml`) and into **ade-engine settings**. The config package should describe *what to detect/transform/validate/hook*; the engine settings control *how the engine runs and writes output*.

This keeps responsibilities clean and makes the system easier to reason about:
- **ade-config**: detectors/transforms/validators/hooks (code, registry-based)
- **ade-engine**: runtime + output behavior (pydantic-settings)

---

## Goals

- **Standard**: use environment variables + `.env` like most Python services.
- **Optional file-based config**: support a simple `ade_engine.toml` for checked-in defaults.
- **Safe defaults**: if no settings are provided, the engine behaves sensibly.
- **Deterministic precedence**: it’s always clear why a value is what it is.
- **No hidden coupling**: config packages should not silently override engine settings.

---

## Configuration sources

The engine supports four primary sources:

1. **Defaults** (hardcoded in `Settings`)
2. **TOML file** (optional): `ade_engine.toml`
3. **Dotenv file** (optional): `.env`
4. **Environment variables** (recommended for deployments)

Additionally, callers (CLI / API) may provide **programmatic overrides** (kwargs) when constructing Settings.

---

## Precedence (who wins)

Highest → lowest priority:

1) **Programmatic overrides** (kwargs passed by code / CLI)  
2) **Environment variables**  
3) **`.env`** (dotenv)  
4) **`ade_engine.toml`**  
5) **Defaults**

This matches common expectations:
- devs can commit a TOML baseline,
- local overrides go into `.env`,
- prod overrides come from environment variables.

---

## Where files are loaded from

### `.env`
- By default: `./.env` (current working directory)
- Optional override: `ADE_ENGINE_ENV_FILE=/path/to/.env`

### `ade_engine.toml`
- By default: `./ade_engine.toml` (current working directory)
- Optional override: `ADE_ENGINE_TOML_FILE=/path/to/ade_engine.toml`

If a file doesn’t exist, it’s simply skipped.

---

## Settings reference (initial set)

These are the “must-have” settings that replace what used to live under `[writer]` in the TOML manifest.

### Writer / output behavior

- `append_unmapped_columns` (bool, default: `true`)
  - If `true`: output includes any unmapped input columns appended to the far right.
  - If `false`: output includes only mapped fields (plus whatever hooks add).

- `unmapped_prefix` (str, default: `"raw_"`)
  - Prefix applied to appended unmapped columns (e.g., `raw_Employee Notes`).

> ADE Engine default output ordering:
> - mapped columns stay in **input order**
> - unmapped columns (if enabled) are **appended** to the right

If you need business-specific output ordering, do it in a hook (recommended: `HookName.ON_TABLE_MAPPED`).

### Mapping tie resolution

- `mapping_tie_resolution` (str, default: `"leftmost"`)
  - Options:
    - `leftmost`: when multiple columns tie with equal top score for a field, map the leftmost column; others become unmapped.
    - `drop_all`: leave all tied columns unmapped; the field remains unmapped unless a hook patches it.

### Config package import path

- `config_package` (str, default: `"ade_config"`)
  - Import path for the config package to discover and register.
  - Can still be overridden via CLI/API args.

---

## Environment variable names

We use a standard env prefix:

- Prefix: `ADE_ENGINE_`
- Field names become upper snake case.

Examples:
- `append_unmapped_columns` → `ADE_ENGINE_APPEND_UNMAPPED_COLUMNS`
- `unmapped_prefix` → `ADE_ENGINE_UNMAPPED_PREFIX`
- `config_package` → `ADE_ENGINE_CONFIG_PACKAGE`

File location overrides:
- `ADE_ENGINE_ENV_FILE`
- `ADE_ENGINE_TOML_FILE`

---

## Examples

### Example `.env`

```dotenv
# Output behavior
ADE_ENGINE_APPEND_UNMAPPED_COLUMNS=true
ADE_ENGINE_UNMAPPED_PREFIX=raw_

# Where to find the config package (optional override)
ADE_ENGINE_CONFIG_PACKAGE=ade_config
````

### Example `ade_engine.toml`

```toml
# ade_engine.toml
[ade_engine]
append_unmapped_columns = true
unmapped_prefix = "raw_"
config_package = "ade_config"
mapping_tie_resolution = "leftmost" # options: "leftmost" (default) or "drop_all"
```

> TOML is intended as a “baseline defaults file”. `.env` and env vars should override it.

### Example “one-off” override via environment

```bash
export ADE_ENGINE_APPEND_UNMAPPED_COLUMNS=false
export ADE_ENGINE_UNMAPPED_PREFIX="unmapped_"
python -m ade_engine run ./input.xlsx
```

---

## How the engine uses Settings

### At startup

* Construct `Settings` once.
* Log the resolved settings (at DEBUG) so troubleshooting is easy.
* Pass `settings` through the pipeline and writer.

### In render/write

* Determine output ordering and inclusion rules using settings:

  * preserve input order for mapped columns
  * optionally append unmapped with prefix

### In hooks (recommended)

* Settings are available in hook context so hooks can respect them or intentionally override behavior.

---

## Implementation notes (ade-engine)

### Pydantic settings model

We will implement a single settings class:

* `ade_engine/settings.py`

Key points:

* uses `pydantic_settings.BaseSettings`
* defines `env_prefix="ADE_ENGINE_"`
* supports `.env` through `env_file` (path can be overridden)
* supports TOML by loading `ade_engine.toml` (or overridden path) into a dict source

Conceptual sketch:

```py
# ade_engine/settings.py (sketch, not final code)
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    append_unmapped_columns: bool = True
    unmapped_prefix: str = "raw_"
    config_package: str = "ade_config"

    model_config = SettingsConfigDict(
        env_prefix="ADE_ENGINE_",
        env_file=".env",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        # precedence: init > env vars > .env > toml > defaults
        from ._toml import toml_source  # hypothetically loads [ade_engine] if present
        return (init_settings, env_settings, dotenv_settings, toml_source, file_secret_settings)
```

### TOML section naming

For simplicity, TOML uses:

```toml
[ade_engine]
...
```

This avoids collisions and keeps it obvious what owns the settings.

---

## FAQ / gotchas

### “Why not keep writer settings in the config package?”

Because config packages are meant to be reusable logic bundles. Writer behavior is engine policy and usually environment-specific.

### “Can hooks still reorder columns?”

Yes. ADE Engine intentionally makes ordering an advanced behavior handled in hooks (recommended: `HookName.ON_TABLE_MAPPED`).

### “How do booleans parse?”

Use standard forms:

* `true/false` (dotenv / TOML)
* `1/0` also acceptable for env vars (implementation-dependent; we’ll support `true/false/1/0`).

### “What if both `.env` and env vars are set?”

Env vars win.

---

## Change summary from legacy

**Removed:**

* `[writer]` settings from config `manifest.toml`
* “column ordering” requirements in config

**Added:**

* `ade_engine.settings.Settings` as the single place for engine knobs
* `.env`/env/TOML based configuration with deterministic precedence
