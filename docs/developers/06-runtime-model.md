# Runtime Model — How Scripts Run

Scripts are plain functions called with explicit keyword arguments. They run in isolation with a controlled environment and time limits. Secrets are injected when a script runs and are never returned.

## Isolation
Calls may run in a per‑call subprocess or in a per‑job worker. The contract is the same in both cases. Network access is off by default and must be enabled explicitly.

## Environment
The environment is composed in layers: baseline variables, then `manifest.env`, then decrypted `manifest.secrets`, and finally ADE‑provided variables.

## Calls
Hooks export `run(**kwargs)`. Detectors export functions named `detect_*`. Each column module exports a `transform(**kwargs)`, and may optionally expose `transform_row` for special cases.

## Timeouts and limits
Timeouts are enforced per call. Keep detectors fast and pure.

## Security
Secrets are never returned. They are only injected into the child process environment or kwargs.

## What to read next
Read `07-backend-api.md` for routes that manage configs and files.
