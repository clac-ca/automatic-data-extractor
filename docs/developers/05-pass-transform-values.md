# Pass 3 — Transform Values (Optional)

Scripts are plain functions called with explicit keyword arguments. They run in isolation with controlled environments and time limits. Secrets are injected when a script runs and are never returned.

## Isolation
Calls may run in a per‑call subprocess or in a per‑job worker. The contract is the same in both cases. Network access is off by default and must be enabled explicitly.

## Environment
The environment is composed in layers: baseline variables, then `manifest.env`, then decrypted `manifest.secrets`, and finally ADE‑provided variables.

## Calls
[Hooks](./12-glossary.md#scripts-and-hooks) export `run(**kwargs)`. [Detectors](./12-glossary.md#scripts-and-hooks) export functions named `detect_*`. Each column module exports a `transform(**kwargs)`, and may optionally expose `transform_row` for special cases.

## Timeouts and limits
Timeouts are enforced per call. Keep detectors fast and pure.

## Security
Secrets are never returned. They are only injected into the child process environment or kwargs.

## What it reads
- `tables[].mapping[]` and `target_fields[]`
- Config package column modules (`transform`, optional `transform_row`)
- Shared transforms registered under `rules.transform`

## What it appends (artifact)
- `tables[].transform[]` traces per column
- `pass_history[]` entry recording transformed rows and warnings

## What’s next
- Validate results in [06-pass-validate-values.md](./06-pass-validate-values.md).

---

Previous: [04-pass-map-columns-to-target-fields.md](./04-pass-map-columns-to-target-fields.md)  
Next: [06-pass-validate-values.md](./06-pass-validate-values.md)
