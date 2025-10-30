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

Deep dive: see **[job orchestration](./02-job-orchestration.md)**

---

## Core concepts (quick glossary)
Here’s a cleaner, more visual and readable version of your glossary section — designed to look nice in Markdown docs and be skimmable at a glance.
It uses indentation, light formatting, and visual rhythm to make each term stand out while keeping the tone consistent with your developer guide.

---

## **Core Concepts**

### **Config package**

A portable folder of Python scripts that tells ADE how to **find tables**, **map columns**, and optionally **transform or validate** values.
You can create and edit configs directly in the **web UI**, then export or import them as a `.zip`.
ADE automatically versions configs so you can track changes over time.
→ Learn more in the [Config Package Guide](./01-config-packages.md).

Perfect — here’s how you can fold that idea into the glossary entry for **Artifact JSON**, keeping the language crisp and readable while clearly explaining its role as both a *log* and a *shared state object*:

### **Artifact JSON**

A single JSON file that ADE builds and updates as it runs.
It serves **two purposes**:

1. **Audit record** – captures every decision ADE makes: which tables were found, how columns were mapped, how values were transformed or validated, and what the final output looks like.
2. **Shared state** – acts as the **central data structure** passed between backend passes during job orchestration.

When a job starts, ADE creates an initial artifact and hands it to **Pass 1**. Each pass reads, updates, and returns it — building up structure, mappings, and results as the pipeline moves forward.
By the end, the artifact contains the full story of how raw input became clean, structured output.

→ See the [Artifact Reference](./14-job_artifact_json.md) for a detailed breakdown.

### **A1 ranges**

ADE uses familiar Excel-style **A1 notation** to pinpoint cells and ranges (for example: `"B4"` or `"B4:G159"`).
All issues, headers, and table locations use this format, so they’re easy to trace in the original spreadsheet.


Reference: **[glossary](./12-glossary.md)**

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

* **Row rules** (`row_types/*.py`) help ADE **find tables & headers**. Learn how they score rows in the **[Pass 1 guide](./03-pass-find-tables-and-headers.md)**.
* **Column rules** (`columns/<field>.py`) **map**, then optionally **transform** and **validate** one **target field** each. Runtime behavior is detailed across the **[mapping](./04-pass-map-columns-to-target-fields.md)**, **[transform](./05-pass-transform-values.md)**, and **[validation](./06-pass-validate-values.md)** pass guides.
* **Hooks** let you run custom logic around stages. Hook timing is described in the **[job orchestration guide](./02-job-orchestration.md)**.

Details & contracts: see the **[config package guide](./01-config-packages.md)**

---

## Performance & safety

* Detectors run on **samples**, not full columns; keep them light and deterministic. You can adjust the sample count in the manifest (see the **[mapping pass guide](./04-pass-map-columns-to-target-fields.md#shape-high-level)**).
* Transforms/validators operate column-wise while ADE writes rows (streaming writer); passes 3–4 are described in the **[transform guide](./05-pass-transform-values.md)** and **[validation guide](./06-pass-validate-values.md)**.
* Runtime is sandboxed with time/memory limits; network is **off** by default (`allow_net: false` in manifest.json). Lifecycle hooks and limits live in the **[job orchestration guide](./02-job-orchestration.md)**.

---

## Where to go next

* **Config anatomy & contracts** → **[Config package guide](./01-config-packages.md)**
* **Pass-by-pass execution** → **[Job orchestration guide](./02-job-orchestration.md)**
* **Artifact spec, schema, and models** → **[Artifact reference](./14-job_artifact_json.md)**
* **Glossary** → **[Shared terminology](./12-glossary.md)**
* **Snippet conventions** → **[Snippet conventions](./templates/snippet-conventions.md)**
