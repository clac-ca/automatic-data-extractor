# Jobs — Multi‑Pass Pipeline

**Audience:** Engineers implementing or debugging extraction runs  
**Goal:** Understand the four passes and the artifacts a job produces

> **At a glance**
>
> - Pass 1: find tables (structure only).
> - Pass 2: detect and map raw → canonical using small samples.
> - Pass 3: transform column‑wise over full data; assemble normalized rows.
> - Pass 4: validate; optional final hook can adjust after seeing the whole table.

A [job](./02-glossary.md) turns an input file into a normalized spreadsheet using the active [config](./02-glossary.md). The flow is simple and explainable: decide what each [raw column](./02-glossary.md) means (mapping), apply column‑wise transforms, and validate the result. You can pause after mapping if a user needs to adjust assignments.

```
Input file
├─ Pass 1: Row analysis (find tables, capture header text)
├─ Pass 2: Detection & mapping (sample values; raw → canonical)
├─ Pass 3: Transformation (column‑wise; assemble normalized rows)
└─ Pass 4: Validation (types, requireds, ranges; optional final hook)
```

---

## Before you begin

- Ensure exactly one active [config](./02-glossary.md) is set for the target [workspace](./02-glossary.md).
- Skim the [Glossary](./02-glossary.md) for raw vs. canonical columns and mapping.
- Large files are fine: jobs operate column‑wise and avoid loading full sheets in memory.

---

## Pass 1 — row analysis (finding tables)

ADE streams rows one by one and computes simple signals per row:

- Header‑like (lots of text, few blanks)
- Data‑like (numbers, repeating patterns)
- Separator‑like (mostly empty)

A small scoring model estimates header vs. data likelihood; ADE infers table starts/ends on each sheet and records bounds and header cells. The output is a JSON map of structure, not data:

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

---

## Pass 2 — column analysis (detection and mapping)

ADE switches to column‑wise reading. For each table:

1. Take each column in turn.
2. Run every detect script from the config’s column modules.
3. Each detector looks for one pattern (for example, SIN, name, date) and returns a score adjustment.

Scores form a matrix; the highest score wins and yields the assignment:

```
           Raw Col 1   Raw Col 2   Raw Col 3
member_id     1.8        0.1        0.0
first_name    0.2        1.2        0.0
sin_number    0.9        0.0        0.0
```

ADE writes a [mapping](./02-glossary.md) with semantic assignments:

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

Optionally, present this to a user for manual fixes before transformation.

---

## Pass 3 — transformation (column by column)

Transforms run once per [canonical column](./02-glossary.md) over the entire assigned raw column:

- If a `transform` exists, ADE calls it with the full column’s values.
- Scripts clean or normalize values (for example, uppercase IDs or parse dates).
- If no transform exists, values are copied as‑is.

Because ADE works per column, scripts can vectorize efficiently and memory stays flat.

---

## Pass 4 — validation

ADE validates the normalized result. Each column may define optional checks. Validation flags problems instead of deleting values:

```json
{ "column": "member_id", "row": 20, "valid": false, "reason": "Value does not match expected pattern" }
```

An optional final hook can run after validation to adjust or summarize.

---

## Artifacts

- `work/mapping.json` — Headers, raw columns, and raw→canonical assignments with scores and notes.
- `out/normalized.xlsx` — One clean sheet with canonical headers in fixed order.
- `out/validation.json` — Warnings/errors and where they occurred.
- Logs — Execution timings and decisions.

Typical layout under `data/jobs/<job_id>/`:

```
data/jobs/<job_id>/
├─ work/
│  └─ mapping.json
└─ out/
   ├─ normalized.xlsx
   └─ validation.json
```

---

## Minimal example
Small mapping excerpt with assignments and scores.

```json
{
  "version": "mapping.v1",
  "sheets": [{
    "name": "Sheet1",
    "tables": [{
      "bounds": { "a1": "B4:G159" },
      "mapping": {
        "assignments": {
          "member_id":     { "raw": "sheet0.t0.c0", "score": 1.78 },
          "invoice_total": { "raw": "sheet0.t0.c4", "score": 1.27 }
        }
      }
    }]
  }]
}
```

---

## Notes & pitfalls
- Keep detectors pure and cheap; never scan full sheets during detection.
- Column‑wise transforms keep contracts simple and fast.
- One active config per workspace; jobs record the config used.
 - The “final hook” runs after validation (see `after_validation` in manifests).

## What’s next

- See the mapping schema in [05-mapping-format.md](./05-mapping-format.md)
- Review script invocation details in [06-runtime-model.md](./06-runtime-model.md)
- Troubleshoot validations in [08-validation-and-diagnostics.md](./08-validation-and-diagnostics.md)

---

Previous: [03-config-packages.md](./03-config-packages.md)  
Next: [05-mapping-format.md](./05-mapping-format.md)
