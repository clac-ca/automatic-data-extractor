# UI primitives (DiceUI / shadcn)

This directory holds owned DiceUI/shadcn primitives installed via the shadcn CLI.
Do **not** add app-specific composites here. Use the data-table kit directly and
keep feature-specific UI in `src/pages/**/components/`.

## Structure

- `src/components/ui` - vendor primitives (update via shadcn)
- `src/components/data-table` - DiceUI data-table kit (vendor feature)
- `src/pages/**/components` - feature-specific UI

## Installed components

| Component | Source | Command | Notes |
| --- | --- | --- | --- |
| data-table | DiceUI | `npx shadcn@latest add "@diceui/data-table"` | Installs shared table primitives + helpers (`src/components/data-table`, `src/hooks`, `src/lib`, `src/config`, `src/types`). |
| data-table-filter-list | DiceUI | `npx shadcn@latest add "@diceui/data-table-filter-list"` | Adds advanced toolbar + filter list UI. |
| data-table-filter-menu | DiceUI | `npx shadcn@latest add "@diceui/data-table-filter-menu"` | Adds command-palette style filter menu. |
| data-table-sort-list | DiceUI | `npx shadcn@latest add "@diceui/data-table-sort-list"` | Adds sort list UI. |
| action-bar | DiceUI | `npx shadcn@latest add "@diceui/action-bar"` | Floating action bar for row selection. |
| stack | DiceUI | `npx shadcn@latest add "@diceui/stack"` | — |
| select | shadcn | `npx shadcn@latest add select` | — |
| checkbox | shadcn | `npx shadcn@latest add checkbox` | — |
| dialog | shadcn | `npx shadcn@latest add dialog` | — |
| avatar | shadcn | `npx shadcn@latest add avatar` | — |
| avatar-group | DiceUI | `npx shadcn@latest add "@diceui/avatar-group"` | — |
| confirm-dialog | app | — | Uses `bg-overlay` token for the overlay. |

## Maintenance / Updating

- Re-run the same `shadcn add ...` command to update a component.
- Review the Git diff and reconcile changes with our local edits.
- Keep modifications minimal; prefer theme tokens and global styles over component tweaks.
- If a primitive needs a local edit, add a short comment in the file **and** record it in the Notes column above.
