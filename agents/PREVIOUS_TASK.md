# Align settings with standard FastAPI conventions

## Context
`CURRENT_TASK.md` called for renaming and retyping configuration so the backend
exposes predictable, standard FastAPI/Pydantic settings ahead of frontend work.
The previous module mixed prefixes, optional strings, and bespoke helpers that
obscured defaults and required call sites to reach for custom properties.

## Outcome
- Rewrote `Settings` with grouped field names, first-class Pydantic types, and
  defaults that create runtime directories automatically while keeping access to
  the unwrapped JWT secret for token signing.【F:app/core/config.py†L28-L460】
- Updated services and CLI helpers to consume `storage_documents_dir`
  directly, reflecting the concrete directory returned by the new settings
  contract.【F:app/features/documents/service.py†L1-L83】【F:app/features/jobs/service.py†L1-L118】【F:app/cli/commands/reset.py†L1-L87】
- Refreshed environment templates, docs, and regression tests to match the
  renamed fields, JSON-based list inputs, and developer defaults so operators
  have a single, standard configuration story.【F:.env†L1-L18】【F:.env.example†L1-L45】【F:README.md†L137-L162】【F:docs/admin-guide/README.md†L12-L19】【F:tests/core/test_settings.py†L1-L234】

## Next steps
- Break the monolithic `Settings` class into domain-specific configs per
  `agents/BEST_PRACTICE_VIOLATIONS.md` item #4 so modules depend only on the
  configuration they need.
