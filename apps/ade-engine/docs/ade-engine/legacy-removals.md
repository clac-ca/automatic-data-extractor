# Legacy Removals

Removed in this refactor:
- `ade_engine/config/*` (manifest loader, module-string wiring).
- `ade_engine/schemas/manifest.py`.
- Manifest-driven column ordering and writer toggles.

Config packages no longer require `manifest.toml`; discovery imports Python modules instead.
