# Recipe: React Query Infinite Search (Load more / Infinite scroll)

Use this when you want:
- paginated results
- “Load more” at the bottom
- optional infinite scrolling
- better memory control via `maxPages` (when supported by your pagination model)

TanStack Query’s `useInfiniteQuery` adds `fetchNextPage`, `hasNextPage`, and `isFetchingNextPage`, etc. :contentReference[oaicite:6]{index=6}

---

## Important behavior to understand

### Infinite queries have one cache entry
An infinite query has one cache entry containing multiple pages (`data.pages`). Only one fetch can run at a time; calling `fetchNextPage` while another fetch is in flight can cause overwrites or inconsistent state if you don’t guard properly. :contentReference[oaicite:7]{index=7}

### `maxPages` exists — but it’s not free
`maxPages` limits the number of pages stored, which helps memory/network usage. The v5 docs note that `getNextPageParam` and `getPreviousPageParam` must be properly defined if `maxPages > 0`. :contentReference[oaicite:8]{index=8}

If your API only supports forward pagination, you may skip `maxPages` (or implement a bidirectional cursor).

---

## Copy/paste example: “Load more” row inside Search

```tsx
"use client"

import * as React from "react"
import { useInfiniteQuery } from "@tanstack/react-query"
import {
  Search,
  SearchInput,
  SearchList,
  SearchGroup,
  SearchItem,
  SearchSeparator,
} from "@/components/ui/search"
import { Loader2 } from "lucide-react"

type SearchResult = {
  id: string
  label: string
  description?: string
}

type Page = {
  items: SearchResult[]
  nextCursor?: string | null
  // optional if you want maxPages with bidirectional pagination:
  prevCursor?: string | null
}

async function fetchSearchPage(args: {
  q: string
  cursor: string | null
  signal: AbortSignal
}): Promise<Page> {
  const params = new URLSearchParams()
  params.set("q", args.q)
  if (args.cursor) params.set("cursor", args.cursor)

  const res = await fetch(`/api/search?${params.toString()}`, { signal: args.signal })
  if (!res.ok) throw new Error(`Search failed: ${res.status}`)
  return res.json()
}

export function SearchInfiniteExample() {
  const [query, setQuery] = React.useState("")
  const q = query.trim()

  const infinite = useInfiniteQuery({
    queryKey: ["search-infinite", { q }],
    enabled: q.length >= 1,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => fetchSearchPage({ q, cursor: pageParam, signal: signal! }),

    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,

    // Optional (only if your API supports it):
    getPreviousPageParam: (firstPage) => firstPage.prevCursor ?? undefined,

    // Optional: only enable if bidirectional pagination exists and you truly want it.
    // maxPages: 5,
  })

  const pages = infinite.data?.pages ?? []
  const items = pages.flatMap((p) => p.items)

  const showInitial = q.length === 0
  const showLoading = infinite.isPending && items.length === 0
  const showError = infinite.isError && items.length === 0
  const showEmpty = !infinite.isPending && !infinite.isError && q.length >= 1 && items.length === 0

  const canLoadMore = !!infinite.hasNextPage && !infinite.isFetchingNextPage

  return (
    <Search shouldFilter={false} className="w-full max-w-xl rounded-md border bg-background">
      <SearchInput value={query} onValueChange={setQuery} placeholder="Search…" />

      <SearchList>
        {showInitial ? (
          <div className="px-3 py-6 text-sm text-muted-foreground">Type to search.</div>
        ) : null}

        {showLoading ? (
          <div className="px-3 py-6 text-sm text-muted-foreground" aria-live="polite">
            Loading…
          </div>
        ) : null}

        {showError ? (
          <div className="px-3 py-6 text-sm text-destructive" aria-live="polite">
            Something went wrong.
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
                  onSelect={() => {
                    // handle selection
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

            {/* Load more row */}
            <SearchSeparator />

            <SearchItem
              value="__load_more__"
              disabled={!infinite.hasNextPage || infinite.isFetchingNextPage}
              onSelect={() => {
                if (!infinite.hasNextPage) return
                if (infinite.isFetching) return
                infinite.fetchNextPage()
              }}
            >
              <div className="flex w-full items-center justify-between">
                <span className="text-sm">
                  {infinite.hasNextPage ? "Load more" : "No more results"}
                </span>
                {infinite.isFetchingNextPage ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                ) : null}
              </div>
            </SearchItem>

            {/* Background refresh hint (not “load more”) */}
            {infinite.isFetching && !infinite.isFetchingNextPage ? (
              <div className="px-3 py-2 text-xs text-muted-foreground" aria-live="polite">
                Refreshing…
              </div>
            ) : null}
          </>
        ) : null}
      </SearchList>
    </Search>
  )
}
```

---

## Optional: Infinite scroll (IntersectionObserver)

A “Load more” button is more predictable and avoids accidental multiple fetches.
If you do infinite scroll, guard aggressively:

* `if (!hasNextPage) return`
* `if (isFetchingNextPage) return`
* call `fetchNextPage()` in response to the observer callback

Also remember: an InfiniteQuery has a single shared cache entry; avoid overlapping fetches. ([TanStack][4])

[4]: https://tanstack.com/query/v5/docs/react/guides/infinite-queries "Infinite Queries | TanStack Query React Docs"
