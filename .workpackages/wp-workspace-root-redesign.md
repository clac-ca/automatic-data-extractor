> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

* [x] Introduce workspace-aware storage settings (`workspaces_dir`, updated defaults for configs/runs/docs/venvs)
* [x] Implement a centralized “storage layout” helper module for workspace-scoped paths
* [x] Refactor API/engine codepaths that touch configs/runs/documents/venvs to use the new helpers
* [x] Define & implement semantics for ADE_*_DIR overrides (especially `ADE_VENVS_DIR`)
* [x] Update docs (`README`, `AGENTS.md`, Developer Guide, `.env.example`) and add tests for path resolution
* [x] Tests: added storage layout/unit coverage; pytest run blocked locally by missing `asgi_lifespan` in the system environment

> **Agent note:**
> Add more checklist items as needed and update with short notes.

---

# Workspace-rooted Storage Layout & Settings Redesign

(*Clean break edition — no backward compatibility required*)

## 1. Objective

**Goal:**
Move ADE’s runtime storage to a **workspace-first layout** and define **clear, intuitive semantics** for storage environment variables (especially for virtual environments). No migration logic is required; this is a clean cut to the new layout.

You will:

* Introduce a **workspace-rooted storage model** that matches internal documentation and how ADE conceptually works.
* Define & implement **path resolution rules** for defaults and `ADE_*_DIR` overrides.
* Refactor all code to use a centralized path layout API.

The result should:

* Make filesystem structure predictable and workspace-centric.
* Allow operators to override specific storage roots (e.g. put venvs on a separate drive) while maintaining workspace grouping.

---

## 2. Context (What you are starting from)

### Current on-disk model

The code currently defaults to a **type-root structure**:

```text
./data/
├─ config_packages/<config_id>/
├─ .venv/<config_id>/...
├─ runs/<run_id>/...
├─ documents/<doc_id>.<ext>
├─ db/app.sqlite
├─ cache/pip/
└─ logs/
```

### Conceptual model in documentation

Internal docs describe an **idealized workspace-centric** structure:

```text
./data/
└─ workspaces/
   └─ <workspace_id>/
      ├─ config_packages/<config_id>/
      ├─ .venv/<config_id>/<build_id>/
      ├─ runs/<run_id>/
      └─ documents/<document_id>.<ext>
```

### Existing settings

`Settings` has:

* `documents_dir`
* `configs_dir`
* `venvs_dir`
* `runs_dir`

…all based on global roots under `./data`.

### Pain points

* Disk layout does **not** reflect ADE’s workspace model.
* Hard to manage/delete/export a workspace because data is scattered across 4 unrelated top-level directories.
* `ADE_VENVS_DIR` and other overrides do not have clear semantics in a workspace-first world.

### Hard constraints

* We **do not need backward compatibility**.
* We can change defaults and structure directly.
* All env var semantics may be redefined for clarity.

---

## 3. Target architecture / structure (ideal)

### High-level design

1. Introduce **`ADE_WORKSPACES_DIR`** as the primary root.

2. All workspace-owned artifacts go under:

   ```text
   ADE_WORKSPACES_DIR/<workspace_id>/...
   ```

3. Each **type** (configs, documents, runs, venvs) gets its own subdirectory:

   ```text
   <workspace_id>/config_packages/
   <workspace_id>/documents/
   <workspace_id>/runs/
   <workspace_id>/.venv/
   ```

4. If operators want to override storage for a type:

   ```env
   ADE_VENVS_DIR=/mnt/fast-venv
   ADE_DOCUMENTS_DIR=/mnt/share
   ```

   then ADE still nests workspace ID beneath the override:

   ```
   /mnt/fast-venv/<workspace_id>/<config_id>/<build_id>
   /mnt/share/<workspace_id>/documents/<doc_id>.<ext>
   ```

### Final directory structure

```text
./data/
├─ workspaces/
│  └─ <workspace_id>/
│     ├─ config_packages/
│     │  └─ <config_id>/
│     ├─ .venv/
│     │  └─ <config_id>/<build_id>/
│     ├─ runs/
│     │  └─ <run_id>/
│     └─ documents/
│        └─ <document_id>.<ext>
├─ db/app.sqlite
├─ cache/pip/
└─ logs/
```

### Repository layout for code

```text
automatic-data-extractor/
  apps/
    ade-api/
      src/ade_api/
        settings.py
        storage_layout.py          # NEW
        ...
  tests/
    test_storage_layout.py         # NEW
  docs/
    updated_files.md
  .env.example
```

---

## 4. Design (for this workpackage)

### 4.1 Design goals

* **Clarity** — Only one correct mental model: “Everything lives under a workspace.”
* **Maintainability** — All path logic centralized.
* **Flexibility** — Simple override rules for placing certain data types on different filesystems.

### 4.2 Key components

* **Settings updates**
  Add `workspaces_dir` + redefine defaults for configs, runs, venvs, documents.

* **`storage_layout.py`**
  Centralized resolver for all workspace-related paths.

* **Refactor build/run/config flows**
  All places where ADE touches disk routes through the new layout.

### 4.3 Key flows

#### Default flow: no overrides

```python
workspace_root(settings, ws) → ./data/workspaces/<ws>

workspace_config_root → ./data/workspaces/<ws>/config_packages/<config_id>/
workspace_run_root    → ./data/workspaces/<ws>/runs/<run_id>/
workspace_docs_root   → ./data/workspaces/<ws>/documents/
workspace_venv_root   → ./data/workspaces/<ws>/.venv/<config_id>/<build_id>/
```

#### Override flow (e.g. venvs)

```env
ADE_VENVS_DIR=/mnt/fast-venv
```

Venvs go to:

```
/mnt/fast-venv/<workspace_id>/<config_id>/<build_id>/
```

Other types unchanged.

#### Override flow (docs, runs, configs)

Same pattern:

```
ADE_DOCUMENTS_DIR=/mnt/share
→ /mnt/share/<ws>/documents/<doc_id>
```

### 4.4 Open decisions

(*all finalized; modify only if needed during implementation*)

1. `ADE_WORKSPACES_DIR` = `./data/workspaces` is the new canonical root.
2. All `ADE_*_DIR` overrides keep workspace grouping.
3. Default venv location is inside `<workspace_id>/.venv/`.
4. No backward compatibility, no migration logic, no fallback detection.

---

## 5. Implementation & notes for agents

### 5.1 Settings changes

* Add:

  ```python
  workspaces_dir: Path = Field(default=DEFAULT_WORKSPACES_DIR)
  ```

* Change defaults for:

  ```python
  DEFAULT_DOCUMENTS_DIR = DEFAULT_WORKSPACES_DIR
  DEFAULT_CONFIGS_DIR   = DEFAULT_WORKSPACES_DIR
  DEFAULT_RUNS_DIR      = DEFAULT_WORKSPACES_DIR
  DEFAULT_VENVS_DIR     = DEFAULT_WORKSPACES_DIR  # or DATA/.venv; choose and document
  ```

* All resolution happens through `storage_layout.py`, not directly via `settings.*_dir`.

### 5.2 New helper module

`apps/ade-api/src/ade_api/storage_layout.py`:

```python
def workspace_root(settings, workspace_id): ...
def workspace_config_root(settings, workspace_id, config_id): ...
def workspace_run_root(settings, workspace_id, run_id): ...
def workspace_documents_root(settings, workspace_id): ...
def workspace_venv_root(settings, workspace_id, config_id, build_id=None): ...
```

### 5.3 Code refactor

Replace all occurrences of:

```python
settings.configs_dir / config_id
settings.runs_dir / run_id
settings.documents_dir / doc_id
settings.venvs_dir / config_id
```

with calls to the correct helper.

### 5.4 Docs

Update:

* `AGENTS.md`
* Developer Guide
* README storage section
* `.env.example`

Add examples for override semantics.

### 5.5 Tests

Add `test_storage_layout.py` covering:

* Default paths.
* Override paths.
* Workspace grouping logic.
* Build/run/config flows using helpers.
