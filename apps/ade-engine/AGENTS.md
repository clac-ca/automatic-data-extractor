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
3. **Registry** (plugin container populated by decorators in config packages)


### How to test run the ADE Engine locally

Use the module entrypoint: `python -m ade_engine run`.

```bash
# Single file (text logs)
python -m ade_engine run \
  --input data/samples/example.xlsx \
  --config-package data/templates/config_packages/default \
  --output-dir ./output --logs-dir ./logs

# Single file (NDJSON + debug)
python -m ade_engine run \
  --input data/samples/example.xlsx \
  --config-package data/templates/config_packages/default \
  --log-format ndjson --debug \
  --output-dir ./output --logs-dir ./logs

# Batch a directory
python -m ade_engine run \
  --input-dir data/samples \
  --include "*.xlsx" \
  --config-package data/templates/config_packages/default \
  --output-dir ./output --logs-dir ./logs
```

Flags you might actually use:
`--include/--exclude` (globs under `--input-dir`), `-s/--input-sheet` (limit worksheets), `--log-level debug|info|warning|error|critical`, `--quiet` / `--debug`.
