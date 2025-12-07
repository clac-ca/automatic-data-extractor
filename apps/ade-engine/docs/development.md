# Development guide

This document is aimed at developers working on `ade-engine` or writing `ade_config` packages.

---

## Repo layout (logical)

Within `apps/ade-engine/src/ade_engine`:

- `cli.py`: Typer CLI
- `engine.py`: orchestration and run lifecycle
- `config/`: manifest + plugin loader/runtime
- `pipeline/`: sheet/table stages
- `reporting.py`: structured events + logging
- `io/`: workbook IO and path planning
- `types/`: dataclasses used across the system

---

## Running locally

### Run via module (always works)
```bash
python -m ade_engine run --input ./example.xlsx
```

### Run with NDJSON events
```bash
python -m ade_engine run --input ./example.xlsx --log-format ndjson
```

### Use a local config package by path
```bash
python -m ade_engine run --input ./example.xlsx --config-package ./path/to/config-repo
```

---

## Writing config scripts safely

### Keyword-only + **_ is required
All detectors/hooks/transforms/validators must:
- use keyword-only parameters
- accept `**_` for forward compatibility

Example:

```python
def detect_email(*, header: str, column_values_sample: list[object], **_) -> float:
    ...
```

### Emitting custom events
Config scripts can emit structured events:

```python
def transform(*, row_index: int, field_name: str, value: object, event_emitter, **_):
    event_emitter.emit("config.transform.called", row_index=row_index, field=field_name)
    return None
```

---

## Adding a new pipeline event

Prefer events that:
- are stable and low-cardinality (avoid huge strings/arrays)
- include identifiers (sheet/table) for correlation
- avoid leaking sensitive data by default

---

## Testing

The engine is designed to be testable by injecting dependencies:

- `WorkbookIO` can be swapped
- pipeline stages can be injected
- reporting can be redirected to in-memory sinks

A typical approach is to use `pytest` and build small workbooks in-memory with `openpyxl`.

Suggested test targets:
- config loader validation (bad manifest, missing modules)
- row detector region detection
- column mapping behavior for ties/thresholds
- transform + validation issue plumbing
- reporter/event schema stability

---

## Style and contributions

- Keep modules small and dependency-free where possible.
- Prefer dataclasses for “data” objects.
- Treat config callables as an external API: keep invocation kwargs stable.
- Avoid breaking changes to event schema; add fields rather than renaming.

Recommended workflow:
1. Make a small change.
2. Add/adjust tests where possible.
3. Run a sample normalization with `--log-format ndjson` to validate event output.
