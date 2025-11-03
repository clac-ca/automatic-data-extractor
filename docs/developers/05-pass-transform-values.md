## docs/developers/05-pass-transform-values.md

# Pass 3 — Transform Values (Optional)

Transforms normalize values for **mapped** fields. Each field’s module may provide a `transform` function; if absent, values pass through unchanged.

## What it reads

* `tables[].mapping[]` from Pass 2.
* Column modules `columns/<field>.py` (optional `transform`).
* Context: `table`, `header`, `column_index`, `field_meta`, `manifest`, `job_context`, `env`, and a **read‑only** `artifact` snapshot.

## What it appends (artifact)

For each table:

* `transforms[]` — one entry per transformed field:

  ```json
  {
    "target_field": "member_id",
    "transform": "columns.member_id:transform",
    "changed": 120,
    "total": 155,
    "warnings": ["trimmed non-alnum"]
  }
  ```
* A `pass_history[]` entry named **`transform`** with stats:
  `{ changed_cells, fields_with_warnings }`.

## Transform contract

* **Signature (recommended):**

  ```python
  def transform(*, values, header=None, column_index=None, table=None, field_name=None, field_meta=None, manifest=None, job_context=None, env=None, artifact=None, **_):
      # Must return a dict with a 'values' list; 'warnings' is optional.
      cleaned = []
      for v in values:
          if v is None:
              cleaned.append(None)
          else:
              s = "".join(ch for ch in str(v) if ch.isalnum()).upper()
              cleaned.append(s or None)
      return {"values": cleaned, "warnings": []}
  ```
* **Return:** `{"values": list, "warnings": list[str] | []}`.
  ADE computes `changed` by comparing original vs. returned values.
* **Optionality:** If `transform` is not defined, the field is still valid and values are unchanged.

## Performance & Safety

* Functions run inside the job worker with explicit kwargs, not globals.
* Keep them pure and fast; avoid I/O unless required.
* **Network access** is **off by default** and governed by `engine.defaults.allow_net`. Enable only when strictly necessary.

## See also

* [Pass 4 — Validate values](./06-pass-validate-values.md)
* [Artifact schema (tables → transforms)](./schemas/artifact.v1.1.schema.json)