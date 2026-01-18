# Search Recipes

These recipes are companion docs for the `Search` foundation (`@/components/ui/search`).

They intentionally live **outside** the core component so `search.tsx` stays small, composable, and stable. Each recipe is a pattern you can copy, ship, and customize without forking the base primitives.

## Recipes

1) **Remote Search (server-filtered)**
- File: `remote-search.md`
- Use when results come from an API and you want request cancellation, debouncing, and good loading/empty UX.
- Key: `<Search shouldFilter={false} />`

2) **Omnibar / Command Palette (⌘K / Ctrl K)**
- File: `omnibar-commandk.md`
- Use when search is an app-wide entry point: navigation + actions + quick switching.
- Key: `SearchDialog` + global keyboard shortcut guard.

3) **Combobox Dropdown (Popover + single input)**
- File: `combobox-popover.md`
- Use when search behaves like a form field: open on focus, results in a dropdown.
- Key: keep focus in the input; close on select; click-outside behavior.

4) **Filters & Facets**
- File: `filters-facets.md`
- Use when search depends on additional UI state (scope, tags, archived, etc.).
- Key: filters live outside the search component; you render filter UI wherever you want.

5) **Recent Searches & Suggestions**
- File: `recent-suggestions.md`
- Use when you want a high-quality “empty query” state: recents, suggested actions, trending items, etc.
- Key: store recents as minimal data; keep privacy in mind.
