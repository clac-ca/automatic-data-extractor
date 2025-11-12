## docs/developers/04-pass-map-columns-to-target-fields.md

# Pass 2 — Map Columns to Target Fields

ADE decides which **target field** (from the manifest) each source column represents. Detectors attached to each field contribute score deltas; ties are broken deterministically.

## What it reads

* `sheets[].tables[]` from Pass 1 (bounds, header text, column count).
* Config package **column modules** in `columns/<field>.py` exposing `detect_*`.
* Manifest `columns.order` and `columns.meta[*].label/synonyms`.
* `engine.defaults.min_mapping_confidence` (**score threshold**; default `0.0`).

## What it appends (artifact)

For each table:

* `mapping[]` — one entry per source column:

  ```json
  {
    "raw": { "column": "Employees-table-1.col.1", "header": "Employee ID" },
    "target_field": "member_id",
    "score": 1.8,
    "contributors": [
      { "rule": "columns.member_id:detect_pattern", "delta": 0.9 }
    ]
  }
  ```
* A `pass_history[]` entry named **`mapping`** with stats:
  `{ mapped, unmapped }`.

## Detector contract (columns)

Column detector functions return deltas keyed by **target field ids**:

```python
# columns/member_id.py
def detect_pattern(*, header, values_sample, column_index, table, job_context, env, manifest, field_name, field_meta, **_):
    # Example: boost when header or sample matches an ID-like pattern
    deltas = {}
    if header and "id" in header.lower():
        deltas[field_name] = deltas.get(field_name, 0.0) + 0.6
    return {"scores": deltas}
```

**Guidelines**

* Keep per‑detector deltas in roughly **[-1.0, +1.0]**.
* Use a workspace‑wide threshold via `engine.defaults.min_mapping_confidence`. A column only maps if the best score **≥ threshold**; otherwise it is left **unmapped**.

## Selection algorithm (deterministic)

1. Sum deltas per target field across all detectors.
2. Take the field(s) with the **highest** total.
3. Break ties by:

   * Exact match on `columns.meta[*].label` against the source header (case‑insensitive).
   * Then presence in `columns.meta[*].synonyms`.
   * Then **first** in `columns.order`.

Only minimal evidence is stored: source header text, rule traces, scores. **No full column data** is persisted.

## See also

* [Artifact schema (tables → mapping)](./schemas/artifact.v1.1.schema.json)
* [Pass 3 — Transform values](./05-pass-transform-values.md)