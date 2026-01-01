# UI primitives (DiceUI / shadcn)

This directory holds owned DiceUI/shadcn primitives installed via the shadcn CLI.
Do **not** add app-specific composites here—place those in feature folders (for example, `src/pages/**/components/`).

## Installed components

| Component | Source | Command | Notes |
| --- | --- | --- | --- |
| data-table | DiceUI | `npx shadcn@latest add "@diceui/data-table"` | Installs shared table primitives + helpers (`src/components/data-table`, `src/hooks`, `src/lib`, `src/config`, `src/types`). Local edits: `button` supports legacy `primary/danger` variants + `isLoading` (uses `Slottable` for `asChild` safety); `input`/`textarea` accept `invalid`. |
| data-grid | DiceUI | `npx shadcn@latest add "@diceui/data-grid"` | Adds grid primitives + helpers (`src/components/data-grid`, `src/hooks`, `src/lib`, `src/types`). |
| file-upload | DiceUI | `npx shadcn@latest add "@diceui/file-upload"` | `src/components/ui/file-upload.tsx`. |
| avatar-group | DiceUI | `npx shadcn@latest add "@diceui/avatar-group"` | `src/components/ui/avatar-group.tsx`. Local patch: avoid root Slot/asChild (multiple children) and wrap non-element item children to prevent Slot crashes. |
| action-bar | DiceUI | `npx shadcn@latest add "@diceui/action-bar"` | `src/components/ui/action-bar.tsx`. |

## Maintenance / Updating

- Re-run the same `shadcn add ...` command to update a component.
- Review the Git diff and reconcile changes with our local edits.
- Keep modifications minimal; prefer theme tokens and global styles over component tweaks.
- If a primitive needs a local edit, add a short comment in the file **and** record it in the Notes column above.
