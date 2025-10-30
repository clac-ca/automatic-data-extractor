# Pass 2 — Map Columns to Target Fields

**Audience:** Engineers reviewing pass 2 output (column mapping) and downstream integrators  
**Goal:** Understand how pass 2 records assignments in the artifact so you can audit and reuse them.

> **At a glance**
>
> - Captures detection outcomes only (no full data): raw → canonical assignments with scores.
> - Includes just enough structure (sheets, tables, bounds, headers) to disambiguate decisions.
> - Serves UI review between detection and transformation; stabilizes integrations with a versioned schema.

## Shape (high‑level)

- `version`: schema identifier (e.g., `mapping.v1`).
- `job`: job/workspace identifiers.
- `config`: config identifiers and column order.
- `sheets[] → tables[] → raw_columns[] → mapping` (assignments / unassigned / extras).
- `bounds`: both 0‑based indices and an A1 range (`a1`).

---

## Minimal example

```json
{
  "version": "mapping.v1",
  "sheets": [
    {
      "name": "Sheet1",
      "tables": [{
        "bounds": { "top": 3, "left": 1, "height": 156, "width": 6, "a1": "B4:G159" },
        "mapping": {
          "assignments": { "member_id": { "raw": "sheet0.t0.c0", "score": 1.78 } },
          "unassigned": ["first_name"],
          "extras": ["sheet0.t0.c2"]
        }
      }]
    }
  ]
}
```

---

## Schema
See `schemas/artifact.v1.1.schema.json` (tables → `mapping`) for the authoritative definition.

## Notes
- Keep the mapping free of full data. Include only samples and decisions.
- Store both A1 and 0‑based bounds to help humans and code.
- `raw_columns[*].samples` should be minimal and representative; never include sensitive values.

## What’s next

- Learn how transforms run in [05-pass-transform-values.md](./05-pass-transform-values.md).
- See how mappings are produced in [02-job-orchestration.md](./02-job-orchestration.md).

---

Previous: [03-pass-find-tables-and-headers.md](./03-pass-find-tables-and-headers.md)  
Next: [05-pass-transform-values.md](./05-pass-transform-values.md)
