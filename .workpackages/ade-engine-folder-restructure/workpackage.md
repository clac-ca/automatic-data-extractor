> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan or structure, **update this document first**, then the code.
> * Do **not** add compatibility shims or preserve old import paths unless explicitly instructed.

---

## Work Package Checklist

### Planning & Guardrails

* [x] Finalize target package structure in code (directories + `__init__.py`)
* [x] Add import-layer enforcement (Import Linter) and wire into CI/test suite
* [x] Document architecture rules in `AGENTS.md`

### Code Migration

* [x] Move engine orchestration into `application/engine.py`
* [x] Move pipeline modules into `application/pipeline/`
* [x] Consolidate all contracts/models into `models/`
* [x] Move registry + config loading into `extensions/`
* [x] Split observability into `models/events.py` + `infrastructure/observability/`
* [x] Move IO + settings into `infrastructure/`

### Cleanup & Validation

* [x] Update all imports to new structure (no old paths remain)
* [x] Run full test suite and CLI smoke tests
* [x] Remove dead files/directories from old structure
* [x] Update this workpackage with final notes and decisions

> **Agent note:**
> Add or remove checklist items as needed. Keep brief inline notes if helpful, e.g.
> `- [x] Move pipeline models → models/table.py — commit abc123`

---

# ADE Engine Architectural Refactor

## 1. Objective

**Goal:**
Redesign the internal structure of the ADE Engine so the folder layout reflects the **conceptual architecture of the system**, not the historical order files were added.

This refactor makes responsibilities obvious at a glance:

* contracts and domain models are explicit,
* orchestration logic is clearly separated,
* plugin/extension mechanics are intentional,
* infrastructure concerns (IO, logging) are isolated.

The result should feel **standard, boring, predictable**, and hard to misuse.

---

## 2. Non-goals

This workpackage explicitly does **not** include:

* Feature development
* Behavior changes (beyond what is required to move code)
* Performance optimization
* Backward compatibility shims for old import paths
* Public API redesign beyond necessary renames for clarity

Focus is **structure, boundaries, and intent**.

---

## 3. Target architecture / structure (authoritative)

> **Agent instruction:**
> Keep this section in sync with reality.
> If you change the structure while coding, update this section *before* committing.

```text
apps/ade-engine/src/ade_engine/
├── __init__.py
├── __main__.py
│
├── cli/                         # Presentation layer (Typer CLI)
│   ├── __init__.py
│   ├── app.py
│   ├── common.py
│   ├── config.py
│   └── process.py
│
├── application/                 # Use-cases / orchestration
│   ├── __init__.py
│   ├── engine.py
│   └── pipeline/
│       ├── __init__.py
│       ├── pipeline.py
│       ├── detect_rows.py
│       ├── detect_columns.py
│       ├── transform.py
│       ├── validate.py
│       └── render.py
│
├── models/                      # Domain + contracts (single source of truth)
│   ├── __init__.py
│   ├── errors.py
│   ├── run.py
│   ├── table.py
│   ├── issues.py
│   ├── patches.py
│   ├── extension_contexts.py
│   ├── extension_outputs.py
│   └── events.py
│
├── extensions/                  # Plugin system implementation
│   ├── __init__.py
│   ├── loader.py
│   ├── registry.py
│   ├── invoke.py
│   └── templates/
│       └── config_packages/
│           └── default/
│               └── src/ade_config/...
│
└── infrastructure/              # Frameworks / drivers
    ├── __init__.py
    ├── settings.py
    ├── io/
    │   ├── __init__.py
    │   ├── workbook.py
    │   └── run_plan.py
    │
    └── observability/
        ├── __init__.py
        ├── logger.py
        ├── formatters.py
        └── context.py
```

---

## 4. Design (final, not optional)

### 4.1 Architectural principles

* **Models are pure contracts**

  * No filesystem, logging, registry mutation, or orchestration logic.
* **Application code orchestrates**

  * Coordinates models, extensions, and infrastructure.
* **Extensions are explicit**

  * Config packages interact only through a stable extension API.
* **Infrastructure is replaceable**

  * IO and logging are drivers, not domain logic.
* **Observability is first-class**

  * Event schemas are models; logging mechanics are infrastructure.

---

### 4.2 Import layering rules (hard constraints)

These rules are **mandatory** and enforced automatically.

| Layer            | May import                               |
| ---------------- | ---------------------------------------- |
| `models`         | stdlib only                              |
| `infrastructure` | `models`                                 |
| `extensions`     | `models`, `infrastructure`               |
| `application`    | `models`, `extensions`, `infrastructure` |
| `cli`            | everything below                         |

Any violation is a bug.

---

### 4.3 Enforcement mechanism (chosen design)

**We will enforce architecture boundaries using Import Linter with a layers contract.**

This is the single source of truth for dependency rules.

Create `apps/ade-engine/.importlinter`:

```ini
[importlinter]
root_package = ade_engine

[importlinter:contract:layers]
name = ADE Engine layered architecture
type = layers
layers =
    ade_engine.cli
    ade_engine.application
    ade_engine.extensions
    ade_engine.infrastructure
    ade_engine.models
```

#### Test enforcement

Add a pytest guard so architecture violations fail CI:

```python
# tests/test_architecture.py
import subprocess
from pathlib import Path

def test_import_layers():
    root = Path(__file__).resolve().parents[1]
    subprocess.run(["lint-imports", "--config", str(root / ".importlinter")], cwd=root, check=True)
```

This ensures:

* architecture rules are enforced everywhere pytest runs,
* no developer or agent can accidentally bypass them.

---

## 5. Practical migration mapping

This mapping is **authoritative**. If a file doesn’t fit, update this section.

* `ade_engine/engine.py` → `application/engine.py`
* `ade_engine/pipeline/*` → `application/pipeline/*`
* `ade_engine/pipeline/models.py` → `models/table.py`
* `ade_engine/pipeline/patches.py` → `models/patches.py` + `models/issues.py`
* `ade_engine/pipeline/table_view.py` → `models/extension_contexts.py`
* `ade_engine/types/run.py` → `models/run.py`
* `ade_engine/exceptions.py` → `models/errors.py`
* `ade_engine/models/results.py` → `models/extension_outputs.py`
* `ade_engine/logging.py` →

  * `models/events.py`
  * `infrastructure/observability/logger.py`
  * `infrastructure/observability/formatters.py`
  * `infrastructure/observability/context.py`
* `ade_engine/io/workbook.py` → `infrastructure/io/workbook.py`
* `ade_engine/io/paths.py` → `infrastructure/io/run_plan.py`
* `ade_engine/config_package.py` → `extensions/loader.py`
* `ade_engine/registry/*` → `extensions/registry.py`, `extensions/invoke.py`
* `ade_engine/settings.py` → `infrastructure/settings.py`
* `ade_engine/main.py` → `cli/app.py`

---

## 6. Definition of done

This workpackage is complete when:

* The directory structure matches Section 3 exactly.
* All imports use the new structure; no legacy paths remain.
* Import Linter passes locally and in CI.
* Test suite and CLI smoke runs pass.
* Logging/events are cleanly split:

  * schemas in `models/events.py`
  * emission + formatting in `infrastructure/observability/`
* This workpackage reflects final reality (no stale sections).

---

## 7. Final notes (what changed)

- Old top-level modules (`engine.py`, `pipeline/`, `registry/`, `io/`, `logging.py`, `settings.py`, `types/`, `config_package.py`, `main.py`) were removed after moving to the target layered layout (no shims kept).
- CLI entrypoint updated to `ade_engine.cli.app:app` and template resources now live under `ade_engine.extensions.templates.*`.
- Import Linter is enforced via `apps/ade-engine/.importlinter` and `apps/ade-engine/tests/test_architecture.py` (uses `lint-imports`, not `python -m importlinter`).
- Validation run:
  - `pytest -q` (apps/ade-engine): **pass**
  - `ade-engine --help` / `python -m ade_engine --help`: **pass**
  - `ade-engine config init` + `ade-engine config validate`: **pass**
