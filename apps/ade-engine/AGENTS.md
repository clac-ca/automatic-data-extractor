## Mental model: what the ADE engine fundamentally is

At its core, this repo is a **plugin-driven spreadsheet normalizer**:

* **Input**: an XLSX/CSV (workbook), plus a **config package** (Python code) that defines:

  * how to find the **header row** (row detectors),
  * how to map **source columns → canonical fields** (column detectors),
  * how to normalize values (transforms),
  * how to validate values (validators),
  * and optional lifecycle hooks (workbook/sheet/table).
* **Output**: a new XLSX

There are three main moving parts:

1. **Engine** (orchestration + IO + config loading)
2. **Pipeline** (sheet/table processing logic)
3. **Registry** (plugin container populated by imperative `registry.register_*` calls in config packages)


### How to test run the ADE Engine locally

Use the module entrypoint: `python -m ade_engine process`.

```bash
# Scaffold a fresh config package from the built-in template
ade-engine config init ./tmp/my-config --package-name ade_config
ade-engine config validate --config-package ./tmp/my-config

# Single file (NDJSON logs + debug)
python -m ade_engine process file \
  --input data/samples/example.xlsx \
  --config-package apps/ade-engine/src/ade_engine/templates/config_packages/default \
  --log-format ndjson --debug \
  --output-dir ./output \
  --logs-dir ./logs

# Batch a directory
python -m ade_engine process batch \
  --input-dir data/samples \
  --include \"*.xlsx\" \
  --config-package ./tmp/my-config \
  --output-dir ./output/batch \
  --logs-dir ./logs
```

Flags you might actually use:
`--include/--exclude` (globs under `--input-dir`), `-s/--input-sheet` (limit worksheets), `--log-level debug|info|warning|error|critical`, `--quiet` / `--debug`.
