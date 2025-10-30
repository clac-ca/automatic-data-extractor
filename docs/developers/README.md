# Developer Guide

Welcome to the **ADE (Automatic Data Extractor)** developer guide.
This is your entry point for understanding **how ADE works**, **what you configure**, and **how to extend behavior** with small, testable Python scripts.

ADE turns messy spreadsheets into a clean, **normalized** workbook through a few focused passes. It reads in a **streaming** way (no full‑sheet loads) and records every decision in a single **artifact JSON** so you can audit what happened and why.

---

## The big picture (how ADE runs a file)

ADE processes a spreadsheet in small, ordered passes. Each pass **reads** from and **appends** to the same **artifact JSON** (your audit trail).

```
Input workbook
├─ Pass 1: Find tables & headers (row detection)
├─ Pass 2: Map columns → target fields
├─ Pass 3: Transform values (optional)
├─ Pass 4: Validate values (optional)
└─ Pass 5: Generate normalized workbook (row‑streaming writer)
```

* **Streaming I/O**: reads rows/columns without loading entire sheets.
* **Explainable**: rule scores and contributors show why a decision was made.
* **Safe**: the artifact stores locations and decisions, **not raw cell data**.

Deep dive: **[02‑Job Orchestration](./02-job-orchestration.md)**

---

## Core concepts (quick glossary)

* **Config package** — a portable folder that tells ADE how to find tables, map columns, transform, and validate. You create/edit configs in the **web UI** and can export/import them as a **.zip**. ADE versions configs automatically.
* **Target field** — a normalized column you want in the output (e.g., `member_id`, `sin`, `start_date`).
* **Artifact JSON** — a single file ADE builds as it runs; it records structure, mappings, transforms, validations, and output info. Use it for **audit and troubleshooting**.
* **A1 ranges** — ADE uses Excel A1 notation to reference places (e.g., `"B4"`, `"B4:G159"`).

Reference: **[Glossary](./glossary.md)**

---

## Configure behavior with a config package

A config package is a **folder (or zip)** you manage in the UI:

```text
📁 my-config/
├─ manifest.json          # Central manifest: engine settings, target fields, script paths
├─ 📁 columns/            # Column rules: detect → transform (opt) → validate (opt)
│  ├─ <field>.py          # One file per target field you want in the output
│  ├─ member_id.py        # Example
│  ├─ first_name.py       # Example
│  └─ department.py       # Example
├─ 📁 row_types/          # Row rules for Pass 1: Find Tables & Headers
│  ├─ header.py
│  └─ data.py
├─ 📁 hooks/              # Optional extension points around job stages
│  ├─ on_job_start.py
│  ├─ after_mapping.py
│  ├─ after_transform.py
│  └─ after_validate.py
```

* **Row rules** (`row_types/*.py`) help ADE **find tables & headers**.
* **Column rules** (`columns/<field>.py`) **map**, then optionally **transform** and **validate** one **target field** each.
* **Hooks** let you run custom logic around stages (all receive a **read‑only artifact**).

Details & contracts: **[01‑Config Packages — Behavior as Code](./01-config-packages.md)**

---

## The artifact JSON (why you should care)

**During** a run, the artifact lets rules **consult prior decisions** (read‑only).
**After** a run, it is your **audit log** and **debugging tool**.

What you’ll find inside:

* **`rules` registry** — short IDs → `impl` path + content hash
* **`sheets[].tables[]`** — A1 ranges, header descriptor, source headers
* **`mapping[]`** — raw→target assignments, scores, and rule contributors
* **`transforms[]` / `validation`** — change counts, issues with cell locations
* **`output` + `summary`** — where the normalized file was written and basic stats

Minimal example snippet:

```json
{
  "rules": {
    "col.sin.detect_value_shape": { "impl": "columns/sin.py:detect_value_shape", "version": "af31bc" }
  },
  "sheets": [{
    "id": "sheet_1",
    "tables": [{
      "id": "table_1",
      "mapping": [
        {
          "raw": { "column": "col_3", "header": "SIN Number" },
          "target_field": "sin",
          "score": 1.7,
          "contributors": [{ "rule": "col.sin.detect_value_shape", "delta": 0.9 }]
        }
      ]
    }]
  }]
}
```

Full example, schema, and Pydantic models: **[14‑Job Artifact JSON](./14-job_artifact_json.md)**

---

## Development workflow (UI‑first, versioned)

1. **Create a draft config** in the UI (the UI scaffolds your package).
2. **Edit scripts** and `manifest.json` (tests and sample runs encouraged).
3. **Activate** when ready (ADE archives the previously active config).
4. **Export/import** as a `.zip` to share across workspaces.
5. **Roll back** by cloning an archived config to a new draft and re‑activating.

Validation layers:

* **L1 (client)**: Schema + structure checks for the package and manifest
* **L2 (client)**: Static Python checks (syntax & signatures)
* **L3 (server)**: Sandboxed import + tiny dry‑runs; builds the **rule registry** stored in the artifact

Details: **[01‑Config Packages](./01-config-packages.md)**

---

## Performance & safety

* Detectors run on **samples**, not full columns; keep them light and deterministic.  You can adjust the number of samples that are evaluated in the manifest.json (inside the GUI).
* Transforms/validators operate column‑wise while ADE writes rows (streaming writer).
* Runtime is sandboxed with time/memory limits; network is **off** by default (`allow_net: false` in manifest.json).

---

## Where to go next

* **Config anatomy & contracts** → **[01‑Config Packages](./01-config-packages.md)**
* **Pass‑by‑pass execution** → **[02‑Job Orchestration](./02-job-orchestration.md)**
* **Artifact spec, schema, and models** → **[14‑Job Artifact JSON](./14-job_artifact_json.md)**
* **Glossary** → **[Shared terminology](./glossary.md)**
* **Snippet conventions** → **[templates/snippet-conventions.md](./templates/snippet-conventions.md)**