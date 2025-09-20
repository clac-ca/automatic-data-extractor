---
Audience: All personas
Goal: Provide authoritative reference tables that stay in sync with ADE's source of truth.
Prerequisites: Ability to compare documentation against the repository (for automation owners) and basic familiarity with ADE terminology.
When to use: Consult when you need exact configuration values, CLI commands, or release history rather than narrative guides.
Validation: Ensure the environment variable matrix is present and record TODOs for upcoming references.
Escalate to: Documentation maintainers when reference tables drift from `backend/app/config.py` or related source files.
---

# Reference

Reference content captures stable contracts that other guides rely on. Keep these tables synchronised with the code so automation and compliance reviews can trust them.

## Available reference

- [Environment variables](./environment-variables.md) — grouped by concern with defaults and restart guidance.

## Planned references (TODO)

- `api-schema.md` — OpenAPI-derived schema overview.
- `cli-index.md` — CLI command catalogue.
- `release-notes.md` — summary of shipped changes with doc updates.
