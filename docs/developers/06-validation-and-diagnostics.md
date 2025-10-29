# Validation & Diagnostics

Validation checks the shape of a config and the presence of expected functions before a job runs. It verifies the manifest, module paths, contracts, and timeouts. Diagnostics are concise and carry `{path, level, code, message}` so you can grep and fix quickly.

## Checks
- Structure: manifest schema shape.
- References: file/module paths exist.
- Module contracts: `detect_*` + `transform` presence and callable.
- Dry‑run: sample‑based detector execution.
- Timeouts: per call.

## Diagnostics shape

`{ path, level, code, message }`

## Common errors & fixes
- Missing transform → add `transform` export.
- Plaintext secret → use manifest `secrets` (encrypted).
- Unknown hook path → fix manifest path or file location.

## Workflow
Validate, fix, and validate again. Run validation via the CLI or API.

## What to read next
Read `07-examples-and-recipes.md` for small, copy‑pasteable patterns.
