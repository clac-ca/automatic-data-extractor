# Workpackage Guidelines

## Location
- Store all work packages under `workpackages/`.
- Only `.md` and `.py` files go in `workpackages/`. Keep uploads, logs, and binaries elsewhere.

## Output shape
- Always create a folder per work package under `workpackages/`.
- Use subpackages when there are multiple streams, independent milestones, or separate owners.

## Rollup rules
- Top-level `workpackage.md` is a rollup: plan, scope, high-level WBS, subpackage list, and milestone checklist only.
- Subpackages contain detailed WBS tasks, acceptance criteria, and implementation steps.

## Checklist rules
- Use `[ ]` for open items and `[x]` for completed items.
- Each item must be concrete and verifiable.
- If the plan changes, update the work package first.

## Naming
- Use lowercase slugs with hyphens for folder names.
- Folder format: `workpackages/<wp-id>-<slug>/`.
- If the user provides an explicit identifier (WP12, RFC-3), normalize to lowercase and use it as `<wp-id>` (for example, `wp12`, `rfc-3`).
- If no identifier is provided, use `wp` as the `<wp-id>`.
