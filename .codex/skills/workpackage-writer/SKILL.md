---
name: workpackage-writer
description: Create or standardize workpackage.md files and workpackage folder structures. Use when asked to draft a work package, convert notes into a workpackage, or decide between a single workpackage and a rollup with subpackages.
---

# Workpackage Writer

## Overview
Create planning work packages for ADE and store them under `workpackages/`. Always create a dedicated folder per work package, then draft using the canonical template.

## Output location and naming
- Base dir: `workpackages/`
- Always: `workpackages/<wp-id>-<slug>/workpackage.md`
- Rollup: `workpackages/<wp-id>-<slug>/subpackages/<name>/workpackage.md`
- Naming: use lowercase letters, digits, and hyphens. If the user provides an ID (for example, `WP12`), normalize to `wp12` and prefix the folder (for example, `workpackages/wp12-<slug>/`). If no ID is provided, default to `wp-<slug>`.

## Decide output shape
- Use subpackages when there are multiple workstreams or teams, independent milestones, multiple repos/services, or more than 15 checklist items.
- If ambiguous, ask one clarifying question about the number of parallel workstreams/owners.

## Workflow
1. Gather inputs: title, scope, constraints, non-goals, locked decisions, acceptance criteria, and major work areas.
2. Start from `assets/workpackage.template.md` and fill in the sections in order.
3. Use the Plan/Scope/WBS/Open Questions structure near the top so work is visible immediately.
4. Build a WBS with phases, work packages, and task checklists.
5. For rollups: top-level contains plan + WBS for milestones only, plus a subpackage list. Each subpackage contains detailed WBS tasks and acceptance criteria.

## Rules
- Only create `.md` and `.py` files inside `workpackages/`. Place logs or artifacts elsewhere.
- Use ASCII punctuation and headers.
- Keep checklist items concrete and verifiable.

## Resources
- `assets/workpackage.template.md`
- `references/workpackage-guidelines.md`
