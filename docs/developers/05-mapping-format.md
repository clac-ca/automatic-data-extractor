# Mapping Format — Reference

**Audience:** Engineers and integrators consuming or inspecting mappings  
**Goal:** Understand the shape of `mapping.v1` and how to use it for review and downstream integrations

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
See `01-schemas/mapping.v1.schema.json` for the authoritative definition.

## Notes
- Keep the mapping free of full data. Include only samples and decisions.
- Store both A1 and 0‑based bounds to help humans and code.
- `raw_columns[*].samples` should be minimal and representative; never include sensitive values.

## What’s next

- Learn how scripts run in [06-runtime-model.md](./06-runtime-model.md)
- See how mappings are produced in [04-jobs-pipeline.md](./04-jobs-pipeline.md)

---

Previous: [04-jobs-pipeline.md](./04-jobs-pipeline.md)  
Next: [06-runtime-model.md](./06-runtime-model.md)
