# Glossary (ADE)

This glossary explains ADE’s concepts in plain language and links to deeper docs when you want details. It’s organized by theme and includes an alphabetical index at the end.

> New to ADE? Start with the **[Developer Guide](./README.md)**, then come back here as needed.

---

## 1) Architecture & Mental Model

**ADE (Automatic Data Extractor)**
The system that converts messy spreadsheets into a clean, normalized workbook using small Python scripts you author in a **config package**. High‑level tour: [Developer Guide](./README.md).

**Passes**
The ordered stages a job runs through: (1) find tables & headers, (2) map columns, (3) transform values (optional), (4) validate values (optional), (5) write the normalized workbook. Overview: [Job Orchestration](./02-job-orchestration.md).

**Artifact (artifact.json)**
A single JSON file each pass appends to. It’s both the job’s shared state and the audit trail of decisions (without raw cell dumps). Spec: [Artifact reference](./14-job_artifact_json.md).

**A1 Ranges**
Spreadsheet coordinates like `"B4"` or `"B4:G159"` used in the artifact to pinpoint headers, tables, and issues. See: [Artifact reference](./14-job_artifact_json.md).

---

## 2) Configuration & Authoring

**Config Package**
A folder (or zip) containing `manifest.json`, `columns/`, `row_types/`, `hooks/`, and optional `requirements.txt`. It teaches ADE how to find tables, map, transform, and validate. Guide: [Config packages](./01-config-packages.md).

**config_id**
The unique identifier for a **single immutable version** of a config package after it is published. In this simplified model, **the config_id *is* the version** (no nested versioning).

**Draft**
An editable working copy of a config package. You can test a draft by **preparing** it and running jobs that explicitly reference the draft’s temporary id. Publishing a draft creates a new `config_id` (immutable). Details: [Config packages → Drafts](./01-config-packages.md#drafts--file-level-editing-api).

**Clone**
Create a new draft from an existing config (often used to “roll back”: clone a prior `config_id`, tweak, then publish). See: [Config packages](./01-config-packages.md).

**Publish / Active**
Publishing freezes a draft as an immutable `config_id`. Marking a `config_id` as **active** sets it as the workspace default for jobs that don’t specify a config. Jobs may still target any specific `config_id` (past or present). See: [Config packages](./01-config-packages.md).

**Manifest (manifest.json)**
Declares engine defaults, writer options, columns metadata, and script paths. Includes `config_script_api_version`. Example and schema notes: [Config packages](./01-config-packages.md).

**Script API**
Tiny, keyword‑only functions you implement for detectors (`detect_*`), transforms (`transform`), validators (`validate`), and hooks (`run`). Functions accept structured kwargs and return small dicts. Reference: [Config packages](./01-config-packages.md).

**Hooks**
Optional scripts that run around job stages: `on_job_start.py`, `after_mapping.py`, `after_transform.py`, `after_validate.py`. A **prepare‑time hook** can also run after dependencies are installed (preferred name: `on_prepare.py`; legacy: `on_activate.py`). See: [Config packages](./01-config-packages.md).

**requirements.txt**
Optional per‑config dependency list. Hashed as **deps_hash** to decide whether a venv needs to be rebuilt during **prepare**. See: [Config packages → Prepare](./01-config-packages.md).

**Columns / Row Types**

* `columns/<field>.py`: mapping detectors and optional `transform`/`validate` for each target field.
* `row_types/*.py`: row‑level detectors that help find tables and the header row.
  See the pass guides linked from [Config packages](./01-config-packages.md).

---

## 3) Prepare & Runtime Environments

**Prepare (build step)**
A non‑job step that (a) creates or updates `venvs/<config_id>/`, (b) runs `pip install -r requirements.txt` if **deps_hash** changed, (c) writes `packages.txt`, and (d) snapshots your scripts to `venvs/<config_id>/ade-build/snapshot/`. Network is **allowed** here. Overview: [Developer Guide → Virtual environments](./README.md#virtual-environments-prepare-once-run-many).

**Prepared Environment (venv)**
The reusable virtual environment for a config:

```
venvs/<config_id>/
  bin/python
  ade-build/
    snapshot/        # frozen copy of your scripts used by jobs
    packages.txt     # pip freeze
    install.log      # pip output for diagnostics
    build.json       # { content_hash, deps_hash, prepared_at, ... }
```

Jobs symlink `.venv` to this folder, then import from `ade-build/snapshot/`. See: [Developer Guide → Storage map](./README.md#where-things-live-storage-map).

**content_hash**
A hash of the config’s **scripts + manifest**. If it changes, ADE refreshes the code **snapshot**; the venv itself is not rebuilt unless `deps_hash` changed.

**deps_hash**
A hash of **requirements.txt**. If it changes, ADE reinstalls dependencies during the next prepare.

**Pip Cache / Wheelhouse**

* `ADE_PIP_CACHE_DIR`: pip’s cache directory; enables fast, network‑efficient prepares.
* `ADE_WHEELHOUSE`: a local directory of prebuilt wheels for **offline** or air‑gapped prepares.
  See: [Developer Guide → Env vars](./README.md#environment-variables-knobs-that-matter).

**Prepare Hook (on_prepare.py / on_activate.py)**
Optional script run after dependencies are installed (e.g., download a model file to the venv). Results and logs land under `ade-build/`. Legacy name `on_activate.py` is accepted; prefer `on_prepare.py`. See: [Config packages](./01-config-packages.md).

---

## 4) Jobs, Queue, and Worker

**Job**
One execution of ADE on one input file using one `config_id` (or an explicitly prepared draft). Produces `artifact.json`, `normalized.xlsx`, and `events.ndjson`. End‑to‑end: [Job Orchestration](./02-job-orchestration.md).

**In‑Process Queue**
A bounded `asyncio` queue inside the FastAPI app. `POST /jobs` returns **202 Accepted** with `Location` to poll; saturation returns **429 Too Many Requests** with `Retry‑After`. On startup the manager requeues pending jobs. Details: [Job Orchestration](./02-job-orchestration.md).

**Worker (subprocess)**
Each job runs in its own Python subprocess with OS resource limits (CPU, memory, file size). The worker uses the prepared venv and imports only the snapshot; **network is off by default**. Details: [Job Orchestration](./02-job-orchestration.md).

**Runtime Network Policy (`runtime_network_access`)**
A boolean resolved from the manifest (or job override). If `false` (default), socket creation fails in the worker. If `true`, networking is allowed during that job. Policy is separate from prepare‑time network.

**events.ndjson**
An append‑only log of structured lifecycle events per job (e.g., `enqueue`, `start`, `finish`, `error`) with timestamps and minimal details for debugging. See: [Job Orchestration](./02-job-orchestration.md).

**run-request.json**
A small JSON record placed in the job directory capturing the parameters handed to the worker (paths, chosen `config_id`, interpreter used, toggles).

**normalized.xlsx**
The final output workbook written by the streaming writer in Pass 5.

**Safe Mode (`ADE_SAFE_MODE`)**
When enabled, the API stays up but refuses to execute configs. Useful for incident recovery (ship a fix, then disable safe mode). See: [Job Orchestration](./02-job-orchestration.md#safe-mode-ade_safe_mode).

---

## 5) Files & Storage Layout

**Data Root (`ADE_DATA_DIR`)**
The base directory under which ADE stores configs, venvs, and jobs. Defaults to `./data`. The major subtrees:

* `configs/<config_id>/…` — what you **author** (scripts + manifest + optional requirements).
* `venvs/<config_id>/…` — what ADE **prepares** (interpreter + snapshot + freeze/logs).
* `jobs/<job_id>/…` — what each job **produces** (artifact, output, events, symlink to venv).

Full annotated map: [Developer Guide → Storage map](./README.md#where-things-live-storage-map).

**.venv (symlink)**
A symlink inside each job’s folder pointing to `venvs/<config_id>/`. Keeps jobs fast and avoids copying large folders.

**Snapshot (ade-build/snapshot/)**
A read‑only copy of your config’s scripts taken at prepare time. Jobs import **from the snapshot** to guarantee deterministic code during the run.

---

## 6) Mapping, Transforms, Validation (Script Concepts)

**Detector (`detect_*`)**
A function that returns score deltas indicating how well a raw column matches a **target field** (or, for row detectors, how likely a row is a header/data). Keep values in roughly `[-1.0, +1.0]`. See: [Pass 2 guide](./04-pass-map-columns-to-target-fields.md) and [Pass 1 guide](./03-pass-find-tables-and-headers.md).

**Transform (`transform`)**
An optional function that returns cleaned values for a mapped field (and optional warnings). Runs as rows stream to the writer. See: [Transform guide](./05-pass-transform-values.md).

**Validate (`validate`)**
An optional function that returns a list of issues (row‑indexed, with stable codes). ADE merges issues into the artifact. See: [Validation guide](./06-pass-validate-values.md).

**Mapping Score Threshold (`engine.defaults.mapping_score_threshold`)**
A global confidence gate: if the top mapping score for a column is below this threshold, ADE leaves the column **unmapped** (safer than guessing). See: [Config packages](./01-config-packages.md).

---

## 7) HTTP & API Semantics

**202 Accepted + Location**
Response from `POST /jobs` when a job is enqueued successfully. The `Location` header points to the job resource for polling. See: [Job Orchestration](./02-job-orchestration.md).

**429 Too Many Requests + Retry‑After**
Back‑pressure signal when the in‑process queue is saturated. Clients should respect `Retry‑After`. See: [Job Orchestration](./02-job-orchestration.md).

**Active Config Resolution**
If a submit request omits a `config_id`, ADE uses the workspace’s **active** `config_id`. If none exists, the API returns `400 { "code": "no_active_config" }`. See: [Config packages](./01-config-packages.md).

---

## 8) Environment Variables (Behavior Knobs)

See the full table in the **[Developer Guide](./README.md#environment-variables-knobs-that-matter)**. Key ones:

* `ADE_DATA_DIR`, `ADE_CONFIGS_DIR`, `ADE_VENVS_DIR`, `ADE_JOBS_DIR` — storage roots
* `ADE_PIP_CACHE_DIR`, `ADE_WHEELHOUSE` — prepare‑time pip performance / offline support
* `ADE_MAX_CONCURRENCY`, `ADE_QUEUE_SIZE` — manager capacity and back‑pressure
* `ADE_JOB_TIMEOUT_SECONDS`, `ADE_WORKER_CPU_SECONDS`, `ADE_WORKER_MEM_MB`, `ADE_WORKER_FSIZE_MB` — safety limits
* `ADE_RUNTIME_NETWORK_ACCESS_DEFAULT` — default runtime policy (override per job/manifest)
* `ADE_SAFE_MODE` — refuse execution but keep the API responsive

---

## 9) Terms for Data & Tables

**Sheet**
One tab of the input workbook.

**Table**
A contiguous region of data within a sheet, identified after ADE finds headers. Stored in the artifact with an A1 range.

**Header Row**
The row identified as the header for a table. Detected in Pass 1 by row rules.

**Target Field**
A normalized column in the output workbook (e.g., `member_id`, `first_name`). Each has a script in `columns/<field>.py` and metadata in `manifest.json`.

---

## 10) Alphabetical Index

A1 Ranges • Active • ADE • Artifact • Build.json • Clone • Config Package • config_id • content_hash • deps_hash • Detector • Draft • events.ndjson • Header Row • Hook • In‑Process Queue • Job • Mapping Score Threshold • Manifest • Normalized Workbook • Passes • Pip Cache • Prepare • Prepared Environment • Prepare Hook • requirements.txt • run-request.json • Safe Mode • Sheet • Snapshot • Target Field • Validator • venvs

---

### Pointers

* Big picture & storage map: **[Developer Guide](./README.md)**
* Authoring & script contracts: **[Config packages](./01-config-packages.md)**
* Execution lifecycle & queue: **[Job orchestration](./02-job-orchestration.md)**
* Audit structure: **[Artifact reference](./14-job_artifact_json.md)**