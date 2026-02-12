# Pattern Matrix

Scoring: `1` (poor) to `5` (strong). Promotion rule: adopt patterns scoring `>= 4` and compatible with ADE’s shadcn/Lucide stack.

| Pattern | Source(s) | Findability | Density | Action prominence | Deep-link clarity | Mobile resilience | Accessibility clarity | Score | Adopt |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Dedicated grouped left nav (`Home` / `Organization` / `Workspaces`) | Microsoft admin + Fluent nav | 5 | 4 | 4 | 5 | 4 | 4 | 4.3 | Yes |
| Full-page detail routes for entities (`/new`, `/:id`) | Carbon edit/review + Microsoft patterns | 5 | 5 | 5 | 5 | 4 | 4 | 4.7 | Yes |
| List-first management with command bar and filters | Carbon table + ADE Documents | 5 | 5 | 5 | 4 | 4 | 4 | 4.5 | Yes |
| Narrow right-side edit panes | Legacy ADE settings | 2 | 2 | 3 | 3 | 3 | 3 | 2.7 | No |
| Tiny multi-card settings landing pages | Legacy ADE settings | 2 | 2 | 2 | 3 | 3 | 3 | 2.5 | No |
| Sticky save/discard bar on dirty detail forms | Carbon edit/review + ADE patterns | 4 | 4 | 5 | 4 | 4 | 4 | 4.2 | Yes |
| Role/permission chips in list cells + detail editor | Microsoft + Vercel team patterns | 4 | 5 | 4 | 4 | 4 | 4 | 4.2 | Yes |
| Hide unauthorized sections entirely (not disabled) | Microsoft admin visibility model | 5 | 4 | 4 | 5 | 4 | 4 | 4.3 | Yes |

## Adopted principles

1. One first-class settings shell with dedicated left nav.
2. Entity interactions are route-first and full-page.
3. List + command bar + row click is the default model.
4. No narrow-pane-first editing for core settings entities.
5. Permission filtering is visibility-based, not disable-only.
