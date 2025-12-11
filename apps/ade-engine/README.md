# ADE Engine (CLI)

Lightweight, configurable engine for normalizing Excel/CSV workbooks. This README is a fast path to install, scaffold a config package, and run single/batch jobs.

## Install

```bash
# Stable
pip install "git+https://github.com/clac-ca/automatic-data-extractor.git#subdirectory=apps/ade-engine"

# Development branch
pip install "git+https://github.com/clac-ca/automatic-data-extractor@development#subdirectory=apps/ade-engine"
```

## Quickstart

```bash
# 1) Create a starter config package (uses bundled template)
ade-engine config init my-config --package-name ade_config

# 2) Validate the config package
ade-engine config validate --config-package my-config

# 3) Process a single file
ade-engine process file \
  --input data/samples/CaressantWRH_251130__ORIGINAL.xlsx \
  --output-dir output \
  --config-package my-config

# 4) Process an entire directory
ade-engine process batch \
  --input-dir data/samples \
  --output-dir output/batch \
  --config-package my-config
```

Notes:
- `--config-package` can point to your generated folder (e.g., `my-config`) or any config package path; it is required unless set via `ADE_ENGINE_CONFIG_PACKAGE` or `settings.toml`.
- `process batch --include` acts as an allowlist; if provided, only matching files run. `--exclude` patterns always prune recursively.
- `process file` requires either `--output` or `--output-dir` (mutually exclusive).

## Commands

- `ade-engine process file` – run the engine on one input file.
- `ade-engine process batch` – recurse a directory of inputs.
- `ade-engine config init` – scaffold a config package from the bundled template.
- `ade-engine config validate` – import and register a config package to ensure it’s wired correctly.
- `ade-engine version` – print the CLI version.

## Tips

- Logs and outputs default to `./logs` and `./output` when not provided.
- To change defaults globally, set environment variables with the `ADE_ENGINE_` prefix or add a `settings.toml` alongside your runs.
- Need types for the web app? From the repo root, run `ade types` (if working in the full monorepo).
