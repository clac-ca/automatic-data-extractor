# ade-engine (registry refactor)

Lightweight spreadsheet normalization engine using registry-based config packages.

- Config packages are pure Python; pass `--config-package <path>` pointing to the package directory. Importing modules registers fields, detectors, transforms, validators, and hooks via decorators.
- Settings live in `.env` / env vars / optional `ade_engine.toml` (see `apps/ade-engine/docs/ade-engine/settings.md`).
- Output ordering: mapped columns keep input order; unmapped columns optionally appended to the right with prefix.

Quick start:
```
python -m ade_engine run \
  --input data/samples/example.xlsx \
  --config-package data/templates/config_packages/default \
  --output-dir ./output
```

Docs live under `apps/ade-engine/docs/ade-engine/`.
