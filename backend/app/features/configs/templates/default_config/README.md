# Default Config Template

This template demonstrates the file-backed configuration format described in `config-engine-spec-v0.4.md`. It is cloned when a new config is created. Folder contents:

- `manifest.json` &mdash; Declares hooks, column modules, engine limits, and environment/secrets metadata.
- `on_job_start.py`, `on_job_end.py` &mdash; Optional hook scripts. Each exposes a keyword-only `run(...)`.
- `columns/` &mdash; Canonical column modules with `detect_*` heuristics and a `transform(...)`.
All paths referenced from `manifest.json` stay relative to the config root so import/export remains a simple directory copy or zip. Hooks and column modules follow the detector/transform signatures enforced by validation.
