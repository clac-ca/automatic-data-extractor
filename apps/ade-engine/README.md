# ade-engine (registry refactor)

Lightweight spreadsheet normalization engine using registry-based config packages.

- Config packages are pure Python; pass `--config-package <path>` pointing to the package directory. Importing modules registers fields, detectors, transforms, validators, and hooks via decorators.
- Settings live in `.env` / env vars / optional `ade_engine.toml` (see `apps/ade-engine/docs/ade-engine/settings.md`).
- Output ordering: mapped columns keep input order; unmapped columns optionally appended to the right with prefix.

Install (pip):
```
# Main
pip install "git+https://github.com/clac-ca/automatic-data-extractor.git#subdirectory=apps/ade-engine"

# Development branch
pip install "git+https://github.com/clac-ca/automatic-data-extractor@development#subdirectory=apps/ade-engine"
```

Quick start:
```
python -m ade_engine run \
  --input data/samples/example.xlsx \
  --config-package data/templates/config_packages/default \
  --output-dir ./output
```

Tip: the CLI is also exposed as `ade-engine`, so `ade-engine run ...` is equivalent to `python -m ade_engine run ...`.

CLI help:
```
python -m ade_engine run --help
ade-engine run --help  # shorthand

 Usage: python -m ade_engine run [OPTIONS]

 Execute the engine for one or more inputs.

Options:
  -i, --input FILE                Input file(s). Repeatable; can mix with --input-dir.
      --input-dir DIRECTORY       Recurse a directory for inputs; can mix with --input.
      --include TEXT              Extra glob(s) for --input-dir (defaults already cover xlsx/csv).
      --exclude TEXT              Glob(s) under --input-dir to skip.
  -s, --input-sheet TEXT          Sheet(s) to ingest; defaults to all visible sheets.
      --output-dir DIRECTORY      Output directory (default: ./output).
      --logs-dir DIRECTORY        Log directory (default: ./logs).
      --log-format [text|ndjson]  Log output format (default: text).
      --log-level TEXT            Log level: debug, info, warning, error, critical.
      --debug                     Enable debug logging and verbose diagnostics.
      --quiet                     Reduce output to warnings/errors.
      --config-package DIRECTORY  Path to the config package (required).
      --help                      Show this message and exit.
```

Examples:
```
# Default text logs (writes to ./output and ./logs)
python -m ade_engine run \
  --input data/samples/CaressantWRH_251130__ORIGINAL.xlsx \
  --config-package data/templates/config_packages/default \
  --output-dir ./output --logs-dir ./logs

# NDJSON event stream (good for API validation)
python -m ade_engine run \
  --input data/samples/CaressantWRH_251130__ORIGINAL.xlsx \
  --config-package data/templates/config_packages/default \
  --log-format ndjson \
  --output-dir /tmp/ade-engine/ndjson --logs-dir /tmp/ade-engine/ndjson

# Batch a directory with include/exclude globs
python -m ade_engine run \
  --input-dir data/samples \
  --config-package data/templates/config_packages/default \
  --include "*.xlsx" --exclude "detector-pass*" \
  --output-dir /tmp/ade-engine/batch --logs-dir /tmp/ade-engine/batch
```

Docs live under `apps/ade-engine/docs/ade-engine/`.
