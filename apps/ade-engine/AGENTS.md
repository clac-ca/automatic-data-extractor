# AGENTS.md (apps/ade-engine)

This file is **for AI coding agents** working on the `ade_engine` package.
Your job is to make small, correct, well-scoped changes that match the architecture rules below.

---

## What ADE Engine is (mental model)

ADE Engine is a **plugin-driven spreadsheet normalizer**:

- **Input:** XLSX/CSV + a **config package** (Python) that registers:
  - row detectors (header vs data)
  - column detectors (map source → canonical fields)
  - transforms (normalize vectors)
  - validators (emit issues)
  - hooks (lifecycle customization)
- **Output:** a normalized XLSX + structured logs (text or NDJSON)

This package is intentionally “orchestrator-agnostic”: it processes files and emits structured logs; it does not own queues, databases, or external service state.

---

## Quick commands (don’t guess)

### Install (from repo root)

```bash
# Install ade-engine for development
pip install -e apps/ade-engine[dev]
````

### Discover CLI

```bash
ade-engine --help
python -m ade_engine --help
```

### CLI smoke run (typical workflow)

```bash
# 1) Scaffold a config package from the built-in template
ade-engine config init ./tmp/my-config --package-name ade_config

# 2) Validate the config package imports and registers
ade-engine config validate --config-package ./tmp/my-config

# 3) Process a single file
ade-engine process file \
  --input path/to/input.xlsx \
  --config-package ./tmp/my-config \
  --output-dir ./output \
  --logs-dir ./logs
```

### Tests

```bash
pytest -q
```

If tests fail because you’re not in the right working directory, prefer running them from the repo root.

### Architecture enforcement

Layering rules are enforced by Import Linter (`apps/ade-engine/.importlinter`) and run as part of pytest via `apps/ade-engine/tests/test_architecture.py`.

```bash
lint-imports --config .importlinter
```

---

## Repo layout (new internal structure)

All code for this package lives in: `apps/ade-engine/src/ade_engine/`

```
ade_engine/
  cli/                # Typer CLI (presentation layer)
  application/        # Engine + pipeline orchestration (use-cases)
  models/             # Domain + contracts (run/table/events/extension API)
  extensions/         # Config package loading + registry + invocation
  infrastructure/     # IO + settings + observability (logging impl)
```

---

## Layering + dependency rules (DO NOT VIOLATE)

**Import direction (one-way):**

* `models/` must NOT import from `application/`, `extensions/`, or `infrastructure/`
* `application/` may import from `models/`, `extensions/`, `infrastructure/`
* `extensions/` may import from `models/` (and minimal infra when unavoidable)
* `infrastructure/` may import from `models/` (never the reverse)
* `cli/` should mostly depend on `application/` (+ settings)

If you introduce a circular import, you put code in the wrong layer.

---

## Where things go (hard rules)

### Put it in `models/` if it is:

* a dataclass / pydantic model that defines a **contract**
* run lifecycle types (request/result/status/plan)
* table/mapping/patch/issue types
* extension-facing context objects / enums (FieldDef, HookName, RowKind, contexts)
* **event payload schemas** and event naming rules (the “event model”)

### Put it in `application/` if it:

* orchestrates a run (engine)
* defines pipeline steps and sequencing (detect → map → transform → validate → render)
* coordinates registry usage + IO + logging

### Put it in `extensions/` if it:

* loads/imports config packages
* holds the Registry container and registration logic
* adapts config callables (signature mapping / invocation)

### Put it in `infrastructure/` if it:

* touches the filesystem (workbook IO, run planning)
* manages settings/env loading
* implements logging sinks/formatters/handlers
* talks to external libraries as “drivers” (openpyxl, stdlib logging)

### Do NOT:

* bundle unrelated concerns in one module (e.g., models + logging impl together)
* add “util.py” as a dumping ground
* move fast by making everything import everything

---

## Logging + events (treat as first-class)

* Logging is not a side effect; it’s a **core subsystem**.
* Emit structured events with stable names (`engine.*`, `engine.config.*`, etc.).
* If you add a new engine-emitted event:

  1. define/extend the payload schema in `models/events.py`
  2. register it in the event schema registry (if strict)
  3. emit it via the run-scoped logger in `infrastructure/observability/`

Keep logs:

* deterministic
* compact (don’t dump huge blobs unless you must)
* safe (no secrets, no full file contents)

---

## Editing guidance (how to behave as an agent)

* Prefer **small commits** and **surgical changes**.
* Don’t rename public APIs casually:

  * If you move modules, consider adding a thin re-export in `compat/` (or preserve imports).
* Update docs when behavior/CLI flags change:

  * `apps/ade-engine/docs/` for engine docs
  * work packages when you change the plan/structure

If unsure where something belongs, default to:

* contracts → `models/`
* orchestration → `application/`
* wiring/loading → `extensions/`
* side effects → `infrastructure/`

---

## Common tasks (playbooks)

### Add a pipeline step

* Add logic in `application/pipeline/`
* Add new model types (if needed) in `models/`
* Emit stage events via logger (don’t `print`)

### Add or change the config extension API

* Update `models/extension_api.py` (contexts/enums/contracts)
* Update `extensions/registry.py` and `extensions/invoke.py`
* Keep backwards compatibility for config packages if feasible

### Add a CLI flag

* Update `cli/` parsing
* Update settings wiring (if applicable)
* Update CLI docs and examples

---

## Non-goals / boundaries

* Do not introduce network calls in the engine execution path.
* Do not add heavyweight dependencies without strong justification.
* Do not “refactor everything” unless explicitly requested.
* Do not change output/log defaults without updating docs + tests.
