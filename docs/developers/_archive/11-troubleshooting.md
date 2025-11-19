# Troubleshooting

Quick fixes for the issues we see most often when running ADE. Start here before diving into logs or code.

## Audience & goal
- **Audience:** Config owners and operators watching jobs fail.
- **Goal:** Resolve common problems fast with targeted checks.

## Symptoms & fixes

### Job fails before writing output
- **Check config wiring:** Ensure `manifest.json` points to the right module paths. See the [config package guide](./01-config-packages.md#manifestjson).
- **Missing transforms:** Confirm every mapped column exports `transform(**kwargs)` in its module.
- **Secrets unavailable:** Verify secrets are declared under `manifest.secrets` and stored via the CLI; never hardcode them.

### Mappings look wrong
- **Header mis-detected:** Inspect `tables[].row_classification` in the artifact to confirm the header row. If off, adjust row-type rules or hints.
- **Column assigned to wrong target field:** Review pass 2 scores in `tables[].mapping.assignments`. Tighten detector thresholds or synonyms.

### Validation flood of warnings
- **Rule scope:** Ensure optional validations check for `None` values before flagging.
- **Severity tuning:** Downgrade noisy checks to `warning` in the returned `issues` list, but keep truly blocking problems as `error`.

### Workbook missing unmapped columns
- Confirm `append_unmapped_columns` is `true` in the config writer settings (default). See the [Pass 5 guide](./07-pass-generate-normalized-workbook.md#what-it-reads).

## How to debug deeper
1. Re-run with `ADE_LOG_LEVEL=debug` to surface detector details.
2. Inspect `artifact.json` alongside the original sheet; use the A1 ranges.
3. Use `ade routes` to confirm the active config on the workspace.

---

Previous: [Examples & recipes](./10-examples-and-recipes.md)  
Next: [Shared terminology](./12-glossary.md)
