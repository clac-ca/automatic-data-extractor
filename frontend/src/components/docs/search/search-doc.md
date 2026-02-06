# Search (shadcn-style)

A small, composable search foundation built on **cmdk**. It gives you a “first-class” search UI (input + list + groups + items + dialog wrapper) without forcing data-fetching, caching, pagination, or result schemas.

This file is intentionally tiny so it can become the default choice across many apps and teams.

---

## Why this exists

Most “search components” fail because they try to solve every kind of search (local lists, remote APIs, pagination, filters, keyboard shortcuts, command palettes, comboboxes) inside one abstraction.

This `search.tsx` takes a different approach:

- **Minimal surface area**: primitives, not a framework.
- **Composable**: you assemble the UX you want.
- **Predictable**: cmdk handles keyboard nav and selection behavior.
- **Extensible**: you can layer in remote fetching, debouncing, caching, virtualization, filters, etc. in your app code.

---

## Mental model & terminology

### Query vs Value vs Keywords

- **Query**: what the user types in the input.
  - In cmdk, this is the `<Command.Input value=… onValueChange=… />`.
- **Item value**: the stable identity for an item.
  - You pass it via `<SearchItem value="projects:123" />`.
  - It should be unique and stable.
- **Keywords**: synonyms that improve matching.
  - `<SearchItem keywords={["billing", "invoices"]} />`

### Local vs Remote search

- **Local search**: cmdk filters items on the client.
  - Use `<Search shouldFilter />` (default behavior is cmdk’s default).
- **Remote search**: your server returns filtered results.
  - Use `<Search shouldFilter={false} />` to avoid double-filtering.

---

## Installation

1) Place `search.tsx` in:

- `components/ui/search.tsx`

2) Ensure you have these in your project:

- `cmdk`
- `lucide-react`
- shadcn `Dialog` component at `@/components/ui/dialog`
- your `cn` helper at `@/lib/utils`

> This component follows the shadcn pattern: you own the code, you can edit it, and you can extend it.

---

## Exports

- `Search` – root wrapper around cmdk `<Command />`
- `SearchDialog` – dialog wrapper for “command palette” style search
- `SearchInput` – input row (with icon + proper styling)
- `SearchList` – scrollable results container
- `SearchEmpty` – empty state (cmdk-driven)
- `SearchGroup` – group container + heading styling
- `SearchItem` – selectable item row (handles disabled/selected styling correctly)
- `SearchSeparator` – divider
- `SearchShortcut` – small right-aligned shortcut hint

---

## Quick start: local search (client filtering)

This is the simplest usage: render items, let cmdk filter locally.

```tsx
import * as React from "react"
import {
  Search,
  SearchInput,
  SearchList,
  SearchEmpty,
  SearchGroup,
  SearchItem,
} from "@/components/ui/search"

export function BasicSearch() {
  return (
    <Search className="w-[420px]">
      <SearchInput placeholder="Search docs…" />
      <SearchList>
        <SearchEmpty>No results.</SearchEmpty>

        <SearchGroup heading="Pages">
          <SearchItem value="getting-started">Getting Started</SearchItem>
          <SearchItem value="components">Components</SearchItem>
          <SearchItem value="theming">Theming</SearchItem>
        </SearchGroup>

        <SearchGroup heading="Community">
          <SearchItem value="discord" keywords={["chat", "help"]}>
            Discord
          </SearchItem>
          <SearchItem value="github" keywords={["repo", "issues"]}>
            GitHub
          </SearchItem>
        </SearchGroup>
      </SearchList>
    </Search>
  )
}
````

### Notes

* Always include `SearchList`. cmdk relies on it.
* Add `SearchEmpty` for a polished “no results” experience.
* Provide stable `value` strings (don’t use array index keys).

---

## Command palette: SearchDialog

`SearchDialog` wraps a shadcn `Dialog` and renders a `Search` inside it.

```tsx
import * as React from "react"
import {
  SearchDialog,
  SearchInput,
  SearchList,
  SearchEmpty,
  SearchGroup,
  SearchItem,
} from "@/components/ui/search"
import { Button } from "@/components/ui/button"

export function SearchCommandPalette() {
  const [open, setOpen] = React.useState(false)

  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}>
        Open Search
      </Button>

      <SearchDialog open={open} onOpenChange={setOpen}>
        <SearchInput placeholder="Search…" />
        <SearchList>
          <SearchEmpty>No results.</SearchEmpty>

          <SearchGroup heading="Navigation">
            <SearchItem value="home" onSelect={() => setOpen(false)}>
              Home
            </SearchItem>
            <SearchItem value="settings" onSelect={() => setOpen(false)}>
              Settings
            </SearchItem>
          </SearchGroup>
        </SearchList>
      </SearchDialog>
    </>
  )
}
```

### Passing cmdk props via `searchProps`

If you need advanced cmdk configuration (like remote search mode), pass `searchProps`:

```tsx
<SearchDialog
  open={open}
  onOpenChange={setOpen}
  searchProps={{ shouldFilter: false }}
>
  ...
</SearchDialog>
```

### Sizing the dialog content

This codebase exposes a small sizing hook on `SearchDialog`:

```tsx
<SearchDialog
  open={open}
  onOpenChange={setOpen}
  contentClassName="sm:max-w-2xl md:max-w-3xl"
>
  ...
</SearchDialog>
```

---

## Remote search recipe (server filtered results)

For remote search, you control the query state and fetch results from an API. Then you render items that are already filtered by the server.

Key points:

* Control the input `value`
* Debounce in your app (optional)
* Set `<Search shouldFilter={false}>`
* Handle loading/empty states yourself (or still use `SearchEmpty` if you prefer)

```tsx
import * as React from "react"
import {
  Search,
  SearchInput,
  SearchList,
  SearchGroup,
  SearchItem,
} from "@/components/ui/search"

type Result = { id: string; title: string }

export function RemoteSearch() {
  const [query, setQuery] = React.useState("")
  const [results, setResults] = React.useState<Result[]>([])
  const [loading, setLoading] = React.useState(false)

  React.useEffect(() => {
    if (!query) {
      setResults([])
      return
    }

    let cancelled = false
    setLoading(true)

    ;(async () => {
      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`)
        const json = (await res.json()) as { items: Result[] }
        if (!cancelled) setResults(json.items)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [query])

  return (
    <Search shouldFilter={false} className="w-[420px]">
      <SearchInput value={query} onValueChange={setQuery} placeholder="Search…" />

      <SearchList>
        {query.length === 0 ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            Type to search.
          </div>
        ) : loading ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            Loading…
          </div>
        ) : results.length === 0 ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            No results for “{query}”.
          </div>
        ) : (
          <SearchGroup heading="Results">
            {results.map((r) => (
              <SearchItem
                key={r.id}
                value={r.id}
                onSelect={() => {
                  // navigate, fill input, etc.
                }}
              >
                {r.title}
              </SearchItem>
            ))}
          </SearchGroup>
        )}
      </SearchList>
    </Search>
  )
}
```

### Recommended enhancements (outside this component)

* Debounce with your preferred hook
* Use React Query / SWR for caching + request dedupe
* Abort in-flight requests with `AbortController` for fast typing
* Add “recent searches” or “suggestions” when query is empty

---

## Keyboard shortcut to open SearchDialog (recipe)

This component doesn’t ship global keyboard handling by design. Here’s the recommended recipe:

```tsx
import * as React from "react"

function useCommandK(onOpen: () => void) {
  React.useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isMac = navigator.platform.toLowerCase().includes("mac")
      const mod = isMac ? e.metaKey : e.ctrlKey

      if (mod && e.key.toLowerCase() === "k") {
        e.preventDefault()
        onOpen()
      }
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [onOpen])
}
```

Use it in your palette component:

```tsx
useCommandK(() => setOpen(true))
```

---

## Building richer items (icons, metadata, shortcuts)

`SearchItem` accepts arbitrary children. You can render complex layouts.

```tsx
import { FileText } from "lucide-react"
import { SearchItem, SearchShortcut } from "@/components/ui/search"

<SearchItem value="docs:intro" keywords={["start", "overview"]}>
  <FileText className="mr-2 opacity-60" />
  <div className="flex min-w-0 flex-1 flex-col">
    <span className="truncate">Introduction</span>
    <span className="truncate text-xs text-muted-foreground">
      Docs • Getting started
    </span>
  </div>
  <SearchShortcut>↵</SearchShortcut>
</SearchItem>
```

---

## Disabled items

Use `disabled` for items that can’t be selected.

```tsx
<SearchItem value="billing" disabled>
  Billing (coming soon)
</SearchItem>
```

This foundation uses correct selector patterns so a `"false"` attribute won’t accidentally style everything as disabled.

---

## Controlled selection (optional)

cmdk supports controlling the “active item value” at the root:

```tsx
const [value, setValue] = React.useState("")

<Search value={value} onValueChange={setValue}>
  ...
</Search>
```

Useful if you want to sync selection with external state or analytics.

---

## Styling & theming

All primitives accept `className`. The default styles use shadcn tokens:

* `bg-popover`, `text-popover-foreground`
* `border-border`
* `bg-accent`, `text-accent-foreground`
* `text-muted-foreground`

If your design system differs, change these tokens once in `search.tsx`.

---

## Performance notes

This component keeps logic minimal. For large lists:

* Prefer remote search, or
* Virtualize the list (e.g. render only visible items)
* Avoid expensive rendering inside each item
* Keep `value` stable and unique

If you want virtualization, you can wrap `SearchList` children with a virtualizer and still use `SearchItem` for rows.

---

## Troubleshooting

### “No results” never shows

* Ensure `SearchEmpty` is inside `SearchList`.
* In remote mode (`shouldFilter={false}`), you may prefer your own empty UI.

## Performance note

> For best UX, avoid rendering huge result sets in search palettes. Prefer narrowing + caps + pagination. Virtualization is provided as an advanced pattern and can affect keyboard navigation behavior. See [Virtualization & Large Lists](./recipes/virtualization.md) for guidance.

## Recipes

- [Recipes index](./recipes/README.md)
- [Remote search](./recipes/remote-search.md)
- [React Query (TanStack Query v5)](./recipes/react-query.md)
- [React Query Infinite (load more / infinite scroll)](./recipes/react-query-infinite.md)
- [Virtualization & Large Lists](./recipes/virtualization.md)
- [Omnibar / Command-K](./recipes/omnibar-commandk.md)
- [Combobox dropdown](./recipes/combobox-popover.md)
- [Filters & facets](./recipes/filters-facets.md)
- [Recent searches & suggestions](./recipes/recent-suggestions.md)

### “Keyboard selection doesn’t work”

* Make sure every `SearchItem` has a `value`.
* Ensure `SearchList` exists (cmdk expects it).

### “Everything looks disabled”

* Pass real booleans to `disabled` (not `"false"` strings).
* This foundation uses strict selectors, but upstream code can still break if you pass incorrect prop types.

---

## Design philosophy recap

* This is a **foundation**, not a full search product.
* It provides **excellent defaults** + **escape hatches**.
* It’s easy to extend without forking or fighting the API.
