# ADE — Multi‑Pass Overview

**Audience:** New contributors and integrators  
**Goal:** Grasp ADE’s multi‑pass model and how configs and jobs produce a normalized sheet

> **At a glance**
>
> - ADE reads a file a few times: structure → meaning → transform → validate.
> - Rules live in a portable [config](./02-glossary.md); a [job](./02-glossary.md) applies them to one file.
> - Column‑wise processing keeps memory flat and decisions explainable.

## Concept
At its core, ADE is a multi‑pass spreadsheet parser that learns what’s in a file by reading it a few times — once to understand the structure, once to identify what each column means, and once to transform and validate the data. It separates configuration (rules and scripts) from execution (jobs). Exactly one [config](./02-glossary.md) is active per [workspace](./02-glossary.md); every [job](./02-glossary.md) records the config it used for determinism and auditability.

---

## Pass 1 — row analysis (finding tables)

ADE starts with an Excel file and streams rows one by one. For each row it calculates simple signals:

- Does it look like a header row (lots of text, few blanks)?
- A data row (numbers, repeating patterns)?
- A separator (mostly empty)?

A small scoring model decides how likely each row is to be a header or data. From those scores ADE infers the start and end of every table on every sheet.

The result of this first pass is a JSON map of structure, not data:

```json
{
  "sheets": [
    {
      "name": "Employees",
      "tables": [
        {
          "bounds": { "a1": "B4:G159" },
          "headers": ["Employee ID", "Name", "Dept", "Start Date"],
          "rows": { "start": 5, "end": 159 }
        }
      ]
    }
  ]
}
```

This describes where tables live and which rows are likely headers. It’s the structural skeleton the later passes build on.

---

## Pass 2 — column analysis (detection and mapping)

Next ADE figures out what each column actually contains. It switches from row‑wise to column‑wise reading.

For each table:

1. Take each column in turn.
2. Pass that column’s values through every detect script defined in the config.
3. Each detect script looks for one pattern — for example, a SIN number, a name, a date — and returns a score adjustment.

After all detectors run on all columns, ADE has a matrix of scores:

```
           Raw Col 1   Raw Col 2   Raw Col 3
member_id     1.8        0.1        0.0
first_name    0.2        1.2        0.0
sin_number    0.9        0.0        0.0
```

The highest score wins. ADE assigns each raw column to the most likely canonical column. It then updates the [mapping](./02-glossary.md) JSON, now enriched with semantics:

```json
{
  "tables": [
    {
      "bounds": { "a1": "B4:G159" },
      "mapping": {
        "member_id":   { "raw": "sheet0.t0.c0", "score": 1.8 },
        "first_name":  { "raw": "sheet0.t0.c1", "score": 1.2 },
        "department":  { "raw": "sheet0.t0.c2", "score": 0.9 }
      }
    }
  ]
}
```

If shown in a GUI, this is the moment the user could manually fix unmatched or incorrect mappings.

---

## Pass 3 — transformation

Once every column is mapped, ADE performs the transform pass. It goes column by column again. For each canonical column:

- If the config defines a `transform` script, ADE calls it with the entire column’s values.
- The script can clean, normalize, or reformat the data (for example, uppercase IDs or parse dates).
- If no transform script exists, the values are copied as‑is.

Because it operates on one full column at a time, scripts can vectorize efficiently, and ADE never loads the entire sheet into memory.

---

## Pass 4 — validation

Finally ADE validates the normalized data. Each column can define optional validation logic. Validation doesn’t delete values; it flags problems such as bad formats or missing requireds.

```json
{
  "column": "member_id",
  "row": 20,
  "valid": false,
  "reason": "Value does not match expected pattern"
}
```

These results are stored alongside the mapping for transparency. A last optional hook can run after validation to adjust or summarize the final dataset.

---

## What’s stored where

- Configs are file‑based. They live under `data/configs/<config_id>/` and look like this:

  ```
  manifest.json
  on_job_start.py
  after_detection.py
  after_transformation.py
  after_validation.py
  columns/
    member_id.py
    first_name.py
  ```

  The manifest records metadata (version, canonical columns, order, engine settings). Each column script may contain three sections:

  - `detect_*` functions for scoring
  - an optional `transform` function
  - an optional `validate` function

- Database (SQLite) tracks metadata:

  - which config is active for each workspace
  - timestamps
  - user and version info

Because configs are just folders, they can be zipped, exported, or imported easily — nothing special is required.

---

## Why this design works

The pipeline is simple but powerful:

1. Streaming first pass — understand the structure without loading everything.
2. Compute‑heavy second pass — classify columns with detectors.
3. Column‑wise transformation — clean data efficiently.
4. Validation and hooks — ensure quality and allow customization.

It separates configuration (rules and scripts) from execution (jobs on data). That separation makes configs portable, jobs deterministic, and the whole system easy to reason about.

---

## Minimal example
Small mapping excerpt that assigns raw columns to canonical columns with scores.

```json
{
  "tables": [
    {
      "bounds": { "a1": "B4:G159" },
      "mapping": {
        "member_id":   { "raw": "sheet0.t0.c0", "score": 1.8 },
        "first_name":  { "raw": "sheet0.t0.c1", "score": 1.2 },
        "department":  { "raw": "sheet0.t0.c2", "score": 0.9 }
      }
    }
  ]
}
```

---

## What’s next

- Learn the terms in [02-glossary.md](./02-glossary.md)
- Explore folder structure in [03-config-packages.md](./03-config-packages.md)
- Read the pass‑by‑pass flow in [04-jobs-pipeline.md](./04-jobs-pipeline.md)

---

Previous: [README.md](./README.md)  
Next: [02-glossary.md](./02-glossary.md)
