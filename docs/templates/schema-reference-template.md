# Schema Reference Template

Overview: Describe the schema and its purpose. Include versioning notes.

---

## Manifest schema (vX.Y)

Top‑level fields:

- `version` (string, required) — Schema version
- `info` (object, required) — Title, description
- `engine` (object, optional) — Execution defaults
- `columns` (object, required) — Canonical columns and metadata

Example (YAML):

```yaml
version: "0.5"
info:
  title: Example Config
  description: Column rules and defaults
engine:
  defaults:
    timeout_ms: 120000
    memory_mb: 256
columns:
  order: [member_id, member_full_name]
  meta:
    member_id:
      label: Member ID
      required: true
      script: columns/member_id.py
    member_full_name:
      label: Member Full Name
      required: true
      script: columns/member_full_name.py
```

Validation notes:

- Keys in `columns.meta` must appear in `columns.order`.
- Unknown top‑level keys should be ignored with a warning.

---

## Change log

- v0.5 — Added `engine.defaults` and `columns.meta.script`
- v0.4 — Previous version

