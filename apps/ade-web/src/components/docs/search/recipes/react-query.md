# Recipe: React Query (TanStack Query v5) for Search

This recipe shows a clean, “standard best practice” way to wire your Search UI to a remote API using TanStack Query v5.

You get:
- request deduping
- caching and garbage collection
- cancellation via AbortSignal
- consistent error/loading state handling
- an easy path to pagination/infinite queries later

TanStack Query provides an `AbortSignal` to query functions (QueryFunctionContext) and supports query cancellation when queries become out-of-date/inactive. :contentReference[oaicite:0]{index=0}

---

## When to use this

Use React Query when:
- you want caching and request dedupe
- you want cancellation “for free”
- multiple components might use the same search query
- you want a clean separation: UI in Search primitives, data fetching in the data layer

If your search is purely local (filtering an in-memory list), you don’t need React Query.

---

## Key principles

### 1) Server-filtered results should disable cmdk filtering
If your API returns filtered results, set:

```tsx
<Search shouldFilter={false} />
```

Otherwise, cmdk may double-filter and produce confusing empty states.

### 2) Treat `queryKey` like the source of truth

Everything that affects results belongs in the query key:

* query string
* filters/scope
* feature flags that change results

### 3) Always pass `signal` to fetch

TanStack Query provides `signal`, and if you consume it, requests can be aborted when queries are superseded. ([TanStack][1])

### 4) Prefer `gcTime` (not `cacheTime`) in v5

In v5, `cacheTime` was renamed to `gcTime` to better reflect “garbage collection time.” ([TanStack][2])

### 5) Keep the UI honest while typing

For search, **showing old results for a new query is often worse than showing a small loading state**.

React Query *can* keep previous results using `placeholderData` + `keepPreviousData`, but be deliberate: it can feel like “wrong results” while typing.
The `keepPreviousData` helper still exists in v5, now used via `placeholderData`. ([TanStack][3])

---

## Copy/paste example (debounced query + useQuery)

```tsx
"use client"

import * as React from "react"
import { queryOptions, useQuery } from "@tanstack/react-query"
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
  label: string
  description?: string
  href?: string
  keywords?: string[]
}

type SearchFilters = {
  scope?: "all" | "docs" | "issues"
}

type SearchApiResponse = {
  items: SearchResult[]
}

function useDebouncedValue<T>(value: T, delayMs: number) {
  const [debounced, setDebounced] = React.useState(value)
  React.useEffect(() => {
    const t = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(t)
  }, [value, delayMs])
  return debounced
}

async function fetchSearchResults(args: {
  q: string
  filters: SearchFilters
  signal: AbortSignal
}): Promise<SearchApiResponse> {
  const params = new URLSearchParams()
  params.set("q", args.q)
  if (args.filters.scope) params.set("scope", args.filters.scope)

  const res = await fetch(`/api/search?${params.toString()}`, { signal: args.signal })
  if (!res.ok) throw new Error(`Search failed: ${res.status}`)
  return res.json()
}

// Best practice: centralize queryKey + queryFn using queryOptions
// so it’s shareable (useQuery, prefetchQuery, etc). :contentReference[oaicite:4]{index=4}
function searchQueryOptions(q: string, filters: SearchFilters) {
  return queryOptions({
    queryKey: ["search", { q, filters }],
    queryFn: ({ signal }) => fetchSearchResults({ q, filters, signal: signal! }),
    enabled: q.trim().length >= 1,
    staleTime: 30_000,
    gcTime: 5 * 60_000,
    retry: 1,
  })
}

export function SearchReactQueryExample() {
  const [query, setQuery] = React.useState("")
  const [filters] = React.useState<SearchFilters>({ scope: "all" })

  const debouncedQuery = useDebouncedValue(query, 150)
  const q = debouncedQuery.trim()

  const search = useQuery(searchQueryOptions(q, filters))

  const items = search.data?.items ?? []
  const showInitial = query.trim().length === 0
  const showTooShort = query.trim().length > 0 && q.length < 1
  const showLoading = search.isPending && items.length === 0
  const showError = search.isError && items.length === 0
  const showEmpty = !search.isPending && !search.isError && q.length >= 1 && items.length === 0

  return (
    <Search shouldFilter={false} className="w-full max-w-xl rounded-md border bg-background">
      <SearchInput
        value={query}
        onValueChange={setQuery}
        placeholder="Search…"
        aria-label="Search"
      />

      <SearchList>
        {showInitial ? (
          <div className="px-3 py-6 text-sm text-muted-foreground">Type to search.</div>
        ) : null}

        {showTooShort ? (
          <div className="px-3 py-6 text-sm text-muted-foreground">
            Type at least 1 character.
          </div>
        ) : null}

        {showLoading ? (
          <div className="px-3 py-6 text-sm text-muted-foreground" aria-live="polite">
            Loading…
          </div>
        ) : null}

        {showError ? (
          <div className="px-3 py-6 text-sm text-destructive" aria-live="polite">
            Something went wrong. Try again.
          </div>
        ) : null}

        {showEmpty ? (
          <div className="px-3 py-6 text-sm text-muted-foreground" aria-live="polite">
            No results for “{q}”.
          </div>
        ) : null}

        {items.length > 0 ? (
          <>
            <SearchGroup heading="Results">
              {items.map((item) => (
                <SearchItem
                  key={item.id}
                  value={item.id}
                  keywords={item.keywords}
                  onSelect={() => {
                    // navigate / select
                    // router.push(item.href!)
                  }}
                >
                  <div className="flex min-w-0 flex-col">
                    <span className="truncate">{item.label}</span>
                    {item.description ? (
                      <span className="truncate text-xs text-muted-foreground">
                        {item.description}
                      </span>
                    ) : null}
                  </div>
                </SearchItem>
              ))}
            </SearchGroup>

            {/* Optional: “refreshing” hint when background fetching */}
            {search.isFetching && !search.isPending ? (
              <>
                <SearchSeparator />
                <div className="px-3 py-2 text-xs text-muted-foreground" aria-live="polite">
                  Refreshing…
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

## Optional: “lagged” UI with placeholderData

If you want to keep old results visible while fetching new query keys, TanStack Query v5 supports this via `placeholderData: keepPreviousData`. ([TanStack][3])

Be careful: for *search*, this can show “wrong results” while typing. Consider adding a subtle “Refreshing…” indicator if you do it.


[1]: https://tanstack.com/query/v5/docs/react/guides/query-cancellation "Query Cancellation | TanStack Query React Docs"
[2]: https://tanstack.com/query/v5/docs/react/guides/migrating-to-v5?utm_source=chatgpt.com "Migrating to TanStack Query v5"
[3]: https://tanstack.com/query/v5/docs/react/guides/migrating-to-v5 "Migrating to TanStack Query v5 | TanStack Query React Docs"
