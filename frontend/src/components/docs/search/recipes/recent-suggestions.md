# Recipe: Recent Searches & Suggestions (premium empty-state)

The best search UIs feel useful even when the query is empty:
- Recent selections
- Suggested pages/actions
- Trending or “quick access”

This recipe shows:
- a tiny localStorage-backed recents store
- rendering “Recents” when query is empty
- recording selections on item select

---

## Copy/paste example

```tsx
import * as React from "react"
import {
  SearchDialog,
  SearchInput,
  SearchList,
  SearchGroup,
  SearchItem,
  SearchSeparator,
} from "@/components/ui/search"
import { Button } from "@/components/ui/button"

type RecentItem = { id: string; label: string }

function useLocalStorageState<T>(key: string, initial: T) {
  const [state, setState] = React.useState<T>(() => {
    try {
      const raw = localStorage.getItem(key)
      return raw ? (JSON.parse(raw) as T) : initial
    } catch {
      return initial
    }
  })

  React.useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(state))
    } catch {
      // ignore quota / privacy mode
    }
  }, [key, state])

  return [state, setState] as const
}

function pushRecent(list: RecentItem[], item: RecentItem, limit = 8) {
  const next = [item, ...list.filter((x) => x.id !== item.id)]
  return next.slice(0, limit)
}

export function SearchWithRecentsExample() {
  const [open, setOpen] = React.useState(false)
  const [query, setQuery] = React.useState("")
  const [recents, setRecents] = useLocalStorageState<RecentItem[]>(
    "ade.search.recents",
    []
  )

  React.useEffect(() => {
    if (!open) setQuery("")
  }, [open])

  const suggestions: RecentItem[] = [
    { id: "nav:docs", label: "Docs" },
    { id: "nav:components", label: "Components" },
    { id: "nav:settings", label: "Settings" },
  ]

  const showRecents = query.trim().length === 0

  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}>
        Search
      </Button>

      <SearchDialog open={open} onOpenChange={setOpen}>
        <SearchInput value={query} onValueChange={setQuery} placeholder="Search…" />

        <SearchList>
          {showRecents ? (
            <>
              {recents.length ? (
                <SearchGroup heading="Recent">
                  {recents.map((r) => (
                    <SearchItem
                      key={r.id}
                      value={r.id}
                      onSelect={() => {
                        setOpen(false)
                        // navigate/action
                      }}
                    >
                      {r.label}
                    </SearchItem>
                  ))}

                  <SearchItem
                    value="recent:clear"
                    onSelect={() => {
                      setRecents([])
                    }}
                  >
                    Clear recent searches
                  </SearchItem>
                </SearchGroup>
              ) : (
                <div className="px-3 py-6 text-sm text-muted-foreground">
                  No recent searches yet.
                </div>
              )}

              <SearchSeparator />

              <SearchGroup heading="Suggested">
                {suggestions.map((s) => (
                  <SearchItem
                    key={s.id}
                    value={s.id}
                    onSelect={() => {
                      setRecents((prev) => pushRecent(prev, s))
                      setOpen(false)
                      // navigate/action
                    }}
                  >
                    {s.label}
                  </SearchItem>
                ))}
              </SearchGroup>
            </>
          ) : (
            <>
              {/* Replace this section with your actual remote/local search results.
                  The key is: whenever a real item is selected, record it. */}
              <SearchGroup heading="Results">
                <SearchItem
                  value="result:example"
                  onSelect={() => {
                    const chosen = { id: "result:example", label: "Example result" }
                    setRecents((prev) => pushRecent(prev, chosen))
                    setOpen(false)
                  }}
                >
                  Example result
                </SearchItem>
              </SearchGroup>
            </>
          )}
        </SearchList>
      </SearchDialog>
    </>
  )
}
```

---

## Notes (important in real products)

* Store minimal recent item data (id + label), not sensitive payloads.
* Limit length (6–12) to keep UI fast and relevant.
* Consider per-user scoping (workspace id) if your app supports multiple accounts.
