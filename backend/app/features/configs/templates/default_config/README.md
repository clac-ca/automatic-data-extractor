# Default Config Template

This template demonstrates the file-backed configuration format described in the
[file-backed config engine ADR](../../../../../../docs/reference/adr/0001-file-backed-config-engine.md).
It is cloned whenever a new configuration is created. Folder contents:

- `manifest.json` &mdash; Declares hooks, column modules, engine limits, and
  environment/secret metadata. The template ships the v0.5 manifest schema.
- `on_job_start.py`, `on_job_end.py` &mdash; Optional hook scripts. Each exposes a
  keyword-only `run(...)` entry point.
- `columns/` &mdash; Canonical column modules with multiple `detect_*` heuristics
  and a single `transform(...)` implementation. Validation enforces the
  required signatures and return shapes.

All paths referenced from `manifest.json` stay relative to the config root, so
import/export remains a simple directory copy or zip. Hooks and column modules
follow the detector/transform signatures enforced by validation.
