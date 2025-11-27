# ADE Engine – Detailed Documentation Index

This folder contains deeper “chapters” that expand on the high-level overview
in `ade_engine/README.md`. Read that first, then use this folder as a reference
while building or extending the engine and configurations.

## Terminology

| Concept        | Term in code       | Notes                                                    |
| -------------- | ------------------ | -------------------------------------------------------- |
| Run            | `run`              | One call to `Engine.run()` or one CLI invocation         |
| Config package | `config_package`   | Installed `ade_config` package for this run              |
| Config version | `manifest.version` | Version declared by the config package manifest          |
| Build          | build              | Virtual environment built for a specific config version  |
| User data file | `source_file`      | Original spreadsheet on disk                             |
| User sheet     | `source_sheet`     | Worksheet/tab in the spreadsheet                         |
| Canonical col  | `field`            | Defined in manifest; never call this a “column”          |
| Physical col   | column             | B / C / index 0,1,2… in a sheet                          |
| Output workbook| normalized workbook| Written to `output_dir`; includes mapped + normalized data|

These docs stick to that vocabulary to avoid synonyms like “input file” or
mixing “field”/“column”. Backend notions (run/workspace/tenant) only appear as
opaque metadata if the caller supplies them.

### Package layout (flattened, layered by convention)

* Core runtime: `core/engine.py`, `core/types.py`, `core/pipeline/`
* Config runtime: `config/` loader + registries (currently `config_runtime/loader.py`, `manifest_context.py`)
* Infra/adapters: `infra/io.py`, `infra/telemetry.py`
* Public API & CLI: `ade_engine/__init__.py`, `cli/app.py`, `__main__.py`
* Schemas: `schemas/`

Recommended reading order (mirrors the pipeline flow):

1. [`01-engine-runtime.md`](./01-engine-runtime.md)  
   How the `Engine` is constructed, how `RunRequest` and `RunResult` work, and
   what a single engine run looks like end‑to‑end.

2. [`02-config-and-manifest.md`](./02-config-and-manifest.md)  
   How the engine discovers and uses the `ade_config` package, its
   `manifest.json`, and the Python schema models in `ade_engine.schemas`.

3. [`03-io-and-table-detection.md`](./03-io-and-table-detection.md)  
   How source files are discovered and read, how sheets are selected, and how
   row detectors find table boundaries (`ExtractedTable`).

4. [`04-column-mapping.md`](./04-column-mapping.md)  
   How raw headers/columns are mapped to canonical fields via detectors,
   scoring, and tie‑breaking (`MappedTable`).

5. [`05-normalization-and-validation.md`](./05-normalization-and-validation.md)  
   How transforms and validators run per row to produce normalized data and
   validation issues (`NormalizedTable`).

6. [`07-telemetry-events.md`](./07-telemetry-events.md)  
   Engine telemetry event system (`ade.event/v1`), event envelopes, sinks, and
   the NDJSON log. See `11-ade-event-model.md` for the unified ADE event
   envelope shared with the backend and build/run streaming design.

7. [`08-hooks-and-extensibility.md`](./08-hooks-and-extensibility.md)  
   Hook stages, how hooks are registered, and patterns for extending behavior
   without modifying the engine.

8. [`09-cli-and-integration.md`](./09-cli-and-integration.md)  
   CLI entrypoint, flags, JSON output, and how the ADE backend calls the
   engine inside virtual environments.

9. [`10-testing-and-quality.md`](./10-testing-and-quality.md)  
    Testing strategy, fixtures, regression checks, and change-management
    guidelines.

10. [`11-ade-event-model.md`](./11-ade-event-model.md)  
    Unified ADE event envelope, build/run streaming shape, env planning, and
    persistence guidance.

11. [`12-run-summary-and-reporting.md`](./12-run-summary-and-reporting.md)  
    Run summary schema (`ade.run_summary/v1`), how it’s computed from telemetry,
    and how to persist/report it.

Each document assumes you are familiar with the concepts introduced in
`ade_engine/README.md` and in the preceding chapters.
