# ADE Config Package Template (registry-based, Polars-first)

This template config package defines a target schema (fields) and the plugin logic the ADE engine uses to:

1. Detect header/data rows (Row Detectors)
2. Detect which columns map to which canonical fields (Column Detectors)
3. Transform values using Polars expressions (Column Transforms)
4. Write validation issues inline (Column Validators)
5. Customize the pipeline (Hooks)

## The big idea

- Any module with a top-level `register(registry)` is a plugin module.
- The engine auto-discovers modules and calls `register(registry)` in deterministic order.
- No manifests or central file lists: add a new module → it’s discovered.

## Folder layout (suggested)

```text
src/ade_config/
  columns/                 # one file per canonical field (recommended)
  row_detectors/           # vote header row vs data row
  hooks/                   # lifecycle hooks for customization
```

## One unified settings object

The ADE engine loads runtime settings (with defaults) and can be overridden via `settings.toml`.
That same `settings` object is passed to:

- row detectors
- column detectors
- transforms
- validators
- hooks

See `settings.toml` for the sample-size settings used in detection.

## Polars everywhere (where it matters)

- Row detectors operate on `row_values` lists (pre-table).
- Once a table is detected, the engine materializes a single `table: pl.DataFrame`.
- Everything downstream (column detection → mapping → transforms → validation → hooks) uses that table.

## Column detection (important constraint)

During detection, you do not yet know canonical field column names.
Do not reference fields by `"first_name"` / `"email"` during detection.

Instead:

- Use `header_text` (header label for that column)
- Use `column_index` for position-based heuristics
- Use `table.columns[column_index]` only as an internal handle (not a semantic name)
- If you need another column, access it by index:
  - left neighbor: `column_index - 1`
  - right neighbor: `column_index + 1`

### Common detector patterns (copy/paste)

**Sample sizing (settings-driven)**

```python
row_n = settings.detectors.row_sample_size
text_n = settings.detectors.text_sample_size

# Use only the first row_n rows for detection work (bounded cost).
t = table.head(row_n)

# Current column name (internal, not semantic).
col_name = t.columns[column_index]

# Text view of the column (trimmed).
text = pl.col(col_name).cast(pl.Utf8).str.strip_chars()

# Keep non-empty text and cap to text_n rows.
t = t.filter(text.is_not_null() & (text != "")).head(text_n)
```

**Match-rate scoring with Polars (no Python loops)**

```python
score = (
  t.select(text.str.contains(PATTERN).mean().alias("score"))
   .to_series(0)[0]
)
```

**Cross-column detection (by index, not by name)**

```python
if column_index + 1 < len(table.columns):
    right_name = table.columns[column_index + 1]
    right_text = pl.col(right_name).cast(pl.Utf8).str.strip_chars()
    # apply the same sampling + scoring to right_name
```

## Transforms

Transforms return Polars expressions:

- `pl.Expr` for the output column
- `None` for no change

Transforms run after mapping, so canonical field names exist at that point.
You may reference other fields using `pl.col("other_field")`, but guard with
`if "other_field" in table.columns` when optional.

For derived columns or multi-column edits, use a table hook (e.g., `on_table_mapped` or `on_table_transformed`).

## Validators

Validators return a Polars expression that yields:

- `"Issue message"` when invalid
- `None` when valid

Validators can reference other fields (post-mapping) the same way transforms can.
Validation issues remain row-aligned because they are stored inline.

## Hooks

Hooks receive `table: pl.DataFrame` and can:

- reorder columns
- filter rows
- add summary/diagnostic columns
- change output formatting (post-write hooks)

Because issues are inline, filtering/sorting is safe after validation.
