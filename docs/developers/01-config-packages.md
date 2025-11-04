# Config Packages — Behavior as Code

A **config package** is ADE’s source of truth for how to interpret a spreadsheet. Each package is a folder of
Python scripts plus a manifest that lives under `${ADE_DATA_DIR}/config_packages/<config_id>/`. Once a version
is published it becomes immutable; new edits always produce a new published folder.

Config packages keep ADE explainable and deterministic:

- small, human-readable scripts,
- reproducible builds (`prepare once, run many`),
- isolated execution with network disabled by default.

---

## Layout inside `${ADE_DATA_DIR}`

During development `ADE_DATA_DIR` defaults to `./data`. In production it is usually mounted to shared storage
(for example, Azure Files) so prepares and job artifacts persist across deploys. All package versions live under
`config_packages/` and line up with their prepared runtime under `venvs/`.

```text
${ADE_DATA_DIR}/
├─ config_packages/
│  └─ <config_id>/
│     ├─ manifest.json           # Engine defaults, target fields, script paths
│     ├─ columns/                # Field logic: detect → transform? → validate?
│     │  └─ <field>.py           # e.g., member_id.py, first_name.py
│     ├─ row_types/              # Row detectors for headers and data rows
│     │  ├─ header.py
│     │  └─ data.py
│     ├─ hooks/                  # Optional lifecycle hooks
│     │  ├─ on_job_start.py
│     │  ├─ after_mapping.py
│     │  ├─ after_transform.py
│     │  └─ after_validate.py
│     └─ requirements.txt?       # Optional Python dependencies (pip installed)
│
├─ venvs/
│  └─ <config_id>/               # Prepared virtualenv reused by every job
│     ├─ bin/python
│     └─ ade-build/
│        ├─ snapshot/            # Frozen copy of the package recorded at prepare time
│        ├─ packages.txt         # Exact dependency lock (pip freeze output)
│        ├─ install.log          # Build/install log for troubleshooting
│        └─ build.json           # Metadata (content hash, deps hash, prepared_at)
│
├─ jobs/
│  └─ <job_id>/
│     ├─ inputs/
│     ├─ artifact.json
│     ├─ normalized.xlsx
│     ├─ events.ndjson
│     ├─ run-request.json
│     └─ .venv → ../../venvs/<config_id>/
│
├─ documents/                    # Shared uploads referenced by multiple jobs
│  └─ <document_id>/
│     └─ <filename>.xlsx         # Original file as received
│
├─ db/                           # Application database (SQLite by default)
│  └─ backend.app.sqlite         # Metadata for configs, jobs, documents, etc.
│
└─ cache/
   └─ pip/                       # pip download/build cache (safe to delete)
```

The files under `config_packages/` are the scripts you author. ADE never mutates them after publish. Every job
imports the **snapshot** inside `venvs/<config_id>/ade-build/` to guarantee determinism even if the package is
edited later. Pip download/build caches sit alongside this tree in `${ADE_DATA_DIR}/cache/pip/` and can be wiped
without touching published packages.

---

## Author → Prepare → Run

1. **Author** a package in the UI (or via draft APIs). You edit `manifest.json`, add column detectors, row
   detectors, and optional hooks. Once ready, you publish — creating `config_packages/<config_id>/`.
2. **Prepare** the package (see below). ADE builds a virtual environment under `venvs/<config_id>/`, installs
   dependencies from `requirements.txt`, and snapshots the scripts into `ade-build/snapshot/`.
3. **Run** jobs. Workers mount `.venv` from `jobs/<job_id>/.venv`, import the frozen snapshot, execute the five
   passes, and write `artifact.json` plus `normalized.xlsx`. No re-install or rebuild happens during run.

Preparing once and reusing the result keeps runtime predictable and safe — **prepare once, run many**.

---

## Prepare

`prepare` is the bridge between authoring and execution. It performs three checks before a package can run:

1. **Manifest validation** — schema + semantic validation against
   `docs/developers/schemas/manifest.v1.0.schema.json`.
2. **Dependency install** — creates `venvs/<config_id>/` and runs `pip install -r requirements.txt` (if present).
3. **Snapshot build** — copies the exact scripts into `ade-build/snapshot/` and records metadata in
   `ade-build/build.json`.

`prepare` is idempotent: ADE skips work when the manifest hash and dependency hash match what was previously
recorded. When either changes, ADE rebuilds and refreshes the snapshot. Jobs scheduled before a new prepare
continue to use their previous snapshot; new runs pick up the latest prepared version.

---

## Scripts and the five passes

Each file in `columns/` describes how to recognize and clean a single target field. ADE executes the following
passes for every table that survives detection:

1. **Find tables & headers** (`row_types/header.py`, `row_types/data.py`)  
   Functions named `detect_*` vote for whether a row looks like a header or data row. Scores combine to identify
   table boundaries and the header row. See [Pass 1](./03-pass-find-tables-and-headers.md).
2. **Map columns to target fields** (`columns/<field>.py`)  
   `detect_*` functions assign scores to candidate columns. Highest score wins the mapping.
   See [Pass 2](./04-pass-map-columns-to-target-fields.md).
3. **Transform values (optional)** (`transform(...)`)  
   Pure functions that receive the extracted values and return normalized data.
   See [Pass 3](./05-pass-transform-values.md).
4. **Validate values (optional)** (`validate(...)`)  
   Emit structured issues for rows that violate your rules. ADE augments them with coordinates and identifiers.
   See [Pass 4](./06-pass-validate-values.md).
5. **Generate normalized workbook**  
   ADE writes the output workbook using your manifest’s field ordering and labels. See
   [Pass 5](./07-pass-generate-normalized-workbook.md).

Each handler receives structured keyword arguments (job metadata, manifest, environment variables) as described
in the pass-specific guides.

---

## Hooks

Hooks live under `hooks/` and execute around major stages. Each file exposes a `run(...)` function with the same
structured context as detectors and transforms. Hooks can append notes to the artifact or short metadata objects;
they must never mutate raw inputs or bypass ADE’s sandboxing.

- `on_job_start.py` — called before any passes run.
- `after_mapping.py` — executes once columns are mapped.
- `after_transform.py` — executes after transforms finish.
- `after_validate.py` — executes after validations finish.

Hook code runs inside the same prepared virtualenv and inherits the same safety rules (no network unless the job
explicitly enables it, resource limits enforced by the worker).

---

## Safety and determinism

- Published packages are immutable; jobs always run against the snapshot captured during prepare.
- Workers execute packages inside sandboxed subprocesses with network disabled unless
  `runtime_network_access` is set on the job.
- Structured logging only: `artifact.json` captures decisions, not raw cell values.
- Dependencies are pinned per package via `venvs/<config_id>/ade-build/packages.txt`, so replaying a job is
  deterministic.

---

## Related reading

- [Developer Guide](./README.md) — conceptual overview and storage layout.
- [Job Orchestration](./02-job-orchestration.md) — queue, workers, and runtime isolation.
- [Artifact Reference](./14-job_artifact_json.md) — understanding the per-job audit trail.
