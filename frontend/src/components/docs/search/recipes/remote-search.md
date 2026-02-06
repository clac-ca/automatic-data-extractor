# Recipe: Remote Search (server-filtered)

Use this when your backend returns already-filtered results. You control:
- query state
- debouncing (optional)
- request cancellation (recommended)
- loading/empty/error UI

## Why `shouldFilter={false}`

When results are server-filtered, client filtering can:
- double-filter (results disappear unexpectedly)
- make empty states unreliable
- waste CPU

So:  
✅ `shouldFilter={false}` in remote mode.

---

## UX checklist (the details that matter)

- Minimum query length (often 1–2 chars)
- Debounce typing (100–250ms)
- Cancel in-flight requests as the query changes
- Show “Type to search” when query is empty
- Show “Loading…” only when you have no results yet
- If you have previous results, keep them visible while refreshing (optional but feels premium)
- Cap results (e.g. 20–50) unless you truly need more

---

## Copy/paste example (fetch + AbortController + debounce)

```tsx
import * as React from "react"
import {
  Search,
  SearchInput,
  SearchList,
  SearchGroup,
  SearchItem,
  SearchSeparator,
} from "@/components/ui/search"

type SearchResult = {
  id: string
  title: string
  subtitle?: string
  href?: string
  keywords?: string[]
}

type RemoteState =
  | { status: "idle"; items: SearchResult[]; error: null }
  | { status: "loading"; items: SearchResult[]; error: null }
  | { status: "success"; items: SearchResult[]; error: null }
  | { status: "error"; items: SearchResult[]; error: unknown }

function useDebouncedValue<T>(value: T, delayMs: number) {
  const [debounced, setDebounced] = React.useState(value)
  React.useEffect(() => {
    const t = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(t)
  }, [value, delayMs])
  return debounced
}

async function fetchSearchResults(query: string, signal: AbortSignal): Promise<SearchResult[]> {
  // Example API:
  // GET /api/search?q=...
  const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`, { signal })
  if (!res.ok) throw new Error(`Search failed: ${res.status}`)
  const json = (await res.json()) as { items: SearchResult[] }
  return json.items ?? []
}

export function RemoteSearchExample() {
  const [query, setQuery] = React.useState("")
  const debouncedQuery = useDebouncedValue(query, 150)

  const [state, setState] = React.useState<RemoteState>({
    status: "idle",
    items: [],
    error: null,
  })

  React.useEffect(() => {
    const q = debouncedQuery.trim()
    const min = 1

    if (q.length < min) {
      setState({ status: "idle", items: [], error: null })
      return
    }

    const ac = new AbortController()

    // Premium behavior: if we already have items, keep them visible while refreshing
    setState((prev) => ({
      status: "loading",
      items: prev.items,
      error: null,
    }))

    fetchSearchResults(q, ac.signal)
      .then((items) => {
        if (ac.signal.aborted) return
        setState({ status: "success", items, error: null })
      })
      .catch((err) => {
        if (ac.signal.aborted) return
        setState((prev) => ({
          status: "error",
          items: prev.items,
          error: err,
        }))
      })

    return () => ac.abort()
  }, [debouncedQuery])

  const showIdle = query.trim().length === 0
  const showTooShort = query.trim().length > 0 && query.trim().length < 1 // change if you use min > 1
  const showEmpty = state.status !== "loading" && query.trim().length >= 1 && state.items.length === 0

  return (
    <Search shouldFilter={false} className="w-full max-w-xl rounded-md border bg-background">
      <SearchInput
        value={query}
        onValueChange={setQuery}
        placeholder="Search…"
        aria-label="Search"
      />

      <SearchList>
        {showIdle ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            Type to search.
          </div>
        ) : showTooShort ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            Type at least 1 character to search.
          </div>
        ) : null}

        {state.status === "loading" && state.items.length === 0 ? (
          <div className="py-6 text-center text-sm text-muted-foreground" aria-live="polite">
            Loading…
          </div>
        ) : null}

        {state.status === "error" && state.items.length === 0 ? (
          <div className="py-6 text-center text-sm text-destructive" aria-live="polite">
            Something went wrong. Try again.
          </div>
        ) : null}

        {showEmpty ? (
          <div className="py-6 text-center text-sm text-muted-foreground" aria-live="polite">
            No results for “{query.trim()}”.
          </div>
        ) : null}

        {state.items.length > 0 ? (
          <>
            <SearchGroup heading="Results">
              {state.items.map((item) => (
                <SearchItem
                  key={item.id}
                  value={item.id}
                  keywords={item.keywords}
                  onSelect={() => {
                    // navigate / handle selection
                    // e.g. router.push(item.href!)
                  }}
                >
                  <div className="flex min-w-0 flex-col">
                    <span className="truncate">{item.title}</span>
                    {item.subtitle ? (
                      <span className="truncate text-xs text-muted-foreground">
                        {item.subtitle}
                      </span>
                    ) : null}
                  </div>
                </SearchItem>
              ))}
            </SearchGroup>

            {state.status === "loading" ? (
              <>
                <SearchSeparator />
                <div className="px-3 py-2 text-xs text-muted-foreground" aria-live="polite">
                  Refreshing…
                </div>
              </>
            ) : null}

            {state.status === "error" ? (
              <>
                <SearchSeparator />
                <div className="px-3 py-2 text-xs text-destructive" aria-live="polite">
                  Couldn’t refresh results. Showing previous results.
                </div>
              </>
            ) : null}
          </>
        ) : null}
      </SearchList>
    </Search>
  )
}
```

---

## Notes

* If you need caching, use React Query/SWR at the app layer.
* If you need pagination, fetch “top N” first; avoid huge result sets in command palettes.
* If you need “grouped results”, return groups from your API and render multiple `SearchGroup`s.
