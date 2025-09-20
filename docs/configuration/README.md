---
Audience: Support teams, configuration managers
Goal: Provide a safe path for drafting, validating, publishing, and rolling back ADE configurations.
Prerequisites: Access to the ADE configuration UI (or API credentials when automating), configuration editing permissions, and awareness of current deployment constraints.
When to use: Reference when planning configuration changes, reviewing lifecycle events, or responding to rollout issues.
Validation: Confirm both core guides render and list future TODOs for validation, authoring, and import/export coverage.
Escalate to: Configuration governance lead when lifecycle policies or rollback expectations change.
---

# Configuration workflows

ADE configurations are immutable revisions that govern how documents are processed. This section walks through the lifecycle end-to-end so support teams can iterate safely without breaking determinism. Day-to-day edits happen in the built-in configuration UI, which wraps the same REST endpoints described here for context.

## Core guides

1. [Configuration concepts](./concepts.md) — lifecycle states, versioning rules, and emitted events tied to the FastAPI routes and schemas.
2. [Publishing and rollback](./publishing-and-rollback.md) — step-by-step walkthrough for activating drafts, promoting earlier versions, and validating success.

## Planned expansions (TODO)

- `authoring-guide.md` — editing payloads, cloning revisions, and documenting assumptions.
- `validation-and-testing.md` — local smoke tests, sample document workflows, and checklist before activation.
- `import-export.md` — moving configurations between environments with audit tracking.
