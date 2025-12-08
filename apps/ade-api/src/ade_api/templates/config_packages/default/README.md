# Default ADE Config (Script API v3)

This starter `ade_config` is intentionally small so you can see exactly how Script API v3 works. It maps three fields (`first_name`, `last_name`, `email`) and uses simple heuristics you can tweak immediately.

## What’s inside

```
ade_config/
  manifest.toml                # script_api_version: 3
  row_detectors/               # decide header/data rows
    header.py
    data.py
  column_detectors/            # score columns for each field
    first_name.py
    last_name.py
    email.py
  hooks/                       # optional lifecycle customization
    on_workbook_start.py
    on_sheet_start.py
    on_table_detected.py
    on_table_mapped.py
    on_table_written.py
    on_workbook_before_save.py
```

All script functions are keyword-only and accept `**_` for future args. ADE always passes a `logger` (standard `logging.Logger`) and an `event_emitter` (structured run events via `event_emitter.custom("type", **payload)`).

## How scoring works (readable heuristics)

- `first_name.py`: header keywords (“first”/“given”) return `{"first_name": 1.0, "last_name": -0.5}`; short single-token values matching common first names push the score up, while full names push it down.
- `last_name.py`: header keywords (“last”/“surname”) return `{"last_name": 1.0, "first_name": -0.5}`; tidy single-token values or common surnames boost the score, while emails/full names reduce it.
- `email.py`: headers or values that clearly look like emails return a strong positive for `email` and a negative nudge for the name fields so you can see cross-field intent.

Detectors return either a float or a direct dict of deltas (no `"scores"` wrapper) to keep examples first-class and obvious.

## Quick start to customize

1. Edit `manifest.toml` to list your fields and point to matching detector modules.
2. Open the detectors in `column_detectors/` and adjust the simple rules to match your headers/values.
3. Tweak row detectors (`row_detectors/`) if your headers/data appear in different patterns.
4. (Optional) Use hooks to log extra info, patch mappings, or style the workbook after tables are written.

For a deeper walkthrough of Script API v3, see the docs in `docs/` next to this file.***
