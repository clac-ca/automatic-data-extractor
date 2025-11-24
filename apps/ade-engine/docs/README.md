# ADE Engine – Detailed Documentation Index

This folder contains deeper “chapters” that expand on the high-level overview
in `ade_engine/README.md`. Read that first, then use this folder as a reference
while building or extending the engine and configs.

Recommended reading order (mirrors the pipeline flow):

1. [`01-engine-runtime.md`](./01-engine-runtime.md)  
   How the `Engine` is constructed, how `RunRequest` and `RunResult` work, and
   what a single engine run looks like end‑to‑end.

2. [`02-config-and-manifest.md`](./02-config-and-manifest.md)  
   How the engine discovers and uses the `ade_config` package, its
   `manifest.json`, and the Python schema models in `ade_engine.schemas`.

3. [`03-io-and-table-detection.md`](./03-io-and-table-detection.md)  
   How input files are discovered and read, how sheets are selected, and how
   row detectors find table boundaries (`RawTable`).

4. [`04-column-mapping.md`](./04-column-mapping.md)  
   How raw headers/columns are mapped to canonical fields via detectors,
   scoring, and tie‑breaking (`MappedTable`).

5. [`05-normalization-and-validation.md`](./05-normalization-and-validation.md)  
   How transforms and validators run per row to produce normalized data and
   validation issues (`NormalizedTable`).

6. [`06-artifact-json.md`](./06-artifact-json.md)  
   The structure of `artifact.json`, how the artifact is updated during a run,
   and how it is used by ADE API for reporting.

7. [`07-telemetry-events.md`](./07-telemetry-events.md)  
   The telemetry event system, event envelopes, sinks, and the NDJSON log.

8. [`08-hooks-and-extensibility.md`](./08-hooks-and-extensibility.md)  
   Hook stages, how hooks are registered, and patterns for extending behavior
   without modifying the engine.

9. [`09-cli-and-integration.md`](./09-cli-and-integration.md)  
   CLI entrypoint, flags, JSON output, and how the ADE backend calls the
   engine inside virtual environments.

10. [`10-testing-and-quality.md`](./10-testing-and-quality.md)  
    Testing strategy, fixtures, regression checks, and change‑management
    guidelines.

Each document assumes you are familiar with the concepts introduced in
`ade_engine/README.md` and in the preceding chapters.
