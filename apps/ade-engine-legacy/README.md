# ade-engine

`ade-engine` is a small, deterministic **spreadsheet normalization engine**. It takes an input workbook (XLSX or CSV), detects tables, maps source columns to a canonical schema, applies transforms + validation, and writes a normalized workbook.

It is designed to run in two environments:

- **Local / CLI:** human-friendly logging to the console and optional log files.
- **Service / API:** structured **NDJSON** events on stdout (or a file) so an orchestrator can stream progress to a UI.

---

## Key features

- **Workbook → Sheet → Table pipeline** with clear stages:
  detection → extraction → mapping → normalization → rendering
- **Manifest-driven configuration** (`manifest.toml`) for schema + hook wiring
- **Pluggable detectors/transformers/validators** implemented as plain Python callables
- **Hooks** for lifecycle customization (e.g., table patching, post-processing)
- **Reporting modes**
  - `text`: readable lines (default)
  - `ndjson`: newline-delimited JSON events for machines

---

## Install

This repository is often used as a monorepo. Pick one:

```bash
# If you have a wheel/sdist for ade-engine
pip install ade-engine
```

```bash
# From source (editable), from repo root:
pip install -e apps/ade-engine
```

```bash
# Install just the ade-engine package from GitHub (no local clone needed):
pip install "git+https://github.com/clac-ca/automatic-data-extractor.git#subdirectory=apps/ade-engine"
```

Dependencies include `openpyxl` (XLSX IO), `pydantic` (manifest validation), and `typer` (CLI).

---

## Quick start

Normalize a workbook:

```bash
python -m ade_engine run --input path/to/source.xlsx
```

Write output to a custom directory:

```bash
python -m ade_engine run --input source.xlsx --output-dir ./out
```

Emit NDJSON events to stdout (useful for an API that streams progress):

```bash
python -m ade_engine run --input source.xlsx --log-format ndjson
```

Write NDJSON to a file:

```bash
python -m ade_engine run --input source.xlsx --log-format ndjson --logs-dir ./logs
```

---

## Where to read next

- Project overview: `docs/overview.md`
- Architecture: `docs/architecture.md`
- Workflow (data flow): `docs/workflow.md`
- Public API: `docs/api.md`
- Configuration: `docs/configuration.md`
- Development guide: `docs/development.md`
- Troubleshooting: `docs/troubleshooting.md`

---

## High-level architecture

```mermaid
flowchart LR
  CLI[CLI / API runner] -->|RunRequest| Engine[Engine]
  Engine --> Config[Config runtime (manifest + modules)]
  Engine --> IO[Workbook IO]
  Engine --> Pipeline[Pipeline]
  Pipeline --> Detect[Detect tables]
  Pipeline --> Extract[Extract cells]
  Pipeline --> Map[Map columns]
  Pipeline --> Norm[Normalize + validate]
  Pipeline --> Render[Render output]
  CLI --> Reporting[Reporting\n(text or ndjson)]
  Reporting --> Engine
  Reporting --> Pipeline
```

---

## Contributing

See `docs/development.md` for local setup, conventions, and how to add new config modules safely.

---

## License

See the repository’s license file (typically `LICENSE`) for terms.
