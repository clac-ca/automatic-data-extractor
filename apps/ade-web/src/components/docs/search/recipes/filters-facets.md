# Recipe: Filters & Facets (search + chips + scope)

This pattern keeps the Search foundation clean:
- **Search component** handles keyboard nav + UI primitives.
- **Filters UI** is your app’s responsibility.

You can put filters:
- above results
- below input
- in a sidebar
- in a popover

---

## Copy/paste example (scope + tag filters + remote search)

```tsx
import * as React from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Search,
  SearchInput,
  SearchList,
  SearchGroup,
  SearchItem,
  SearchSeparator,
} from "@/components/ui/search"

type Scope = "all" | "docs" | "issues"
type Filters = { scope: Scope; tags: string[] }

type Result = { id: string; label: string; kind: Scope }

function toggleTag(tags: string[], tag: string) {
  return tags.includes(tag) ? tags.filter((t) => t !== tag) : [...tags, tag]
}

async function fetchResults(query: string, filters: Filters, signal: AbortSignal): Promise<Result[]> {
  const params = new URLSearchParams()
  params.set("q", query)
  params.set("scope", filters.scope)
  if (filters.tags.length) params.set("tags", filters.tags.join(","))

  const res = await fetch(`/api/search?${params.toString()}`, { signal })
  if (!res.ok) throw new Error("Search failed")
  const json = (await res.json()) as { items: Result[] }
  return json.items ?? []
}

export function SearchWithFiltersExample() {
  const [query, setQuery] = React.useState("")
  const [filters, setFilters] = React.useState<Filters>({ scope: "all", tags: [] })

  const [items, setItems] = React.useState<Result[]>([])
  const [status, setStatus] = React.useState<"idle" | "loading" | "error" | "success">("idle")

  React.useEffect(() => {
    const q = query.trim()
    if (!q) {
      setItems([])
      setStatus("idle")
      return
    }

    const ac = new AbortController()
    setStatus("loading")

    fetchResults(q, filters, ac.signal)
      .then((res) => {
        if (ac.signal.aborted) return
        setItems(res)
        setStatus("success")
      })
      .catch(() => {
        if (ac.signal.aborted) return
        setStatus("error")
      })

    return () => ac.abort()
  }, [query, filters])

  return (
    <Search shouldFilter={false} className="w-full max-w-2xl rounded-md border bg-background">
      <SearchInput value={query} onValueChange={setQuery} placeholder="Search…" />

      {/* Filters UI lives OUTSIDE the search primitives. */}
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2">
        <span className="text-xs text-muted-foreground">Scope</span>
        {(["all", "docs", "issues"] as const).map((scope) => (
          <Button
            key={scope}
            type="button"
            variant={filters.scope === scope ? "default" : "outline"}
            size="sm"
            onClick={() => setFilters((f) => ({ ...f, scope }))}
          >
            {scope}
          </Button>
        ))}

        <div className="mx-2 h-4 w-px bg-border" />

        <span className="text-xs text-muted-foreground">Tags</span>
        {(["bug", "help-wanted", "design"] as const).map((tag) => {
          const active = filters.tags.includes(tag)
          return (
            <Button
              key={tag}
              type="button"
              variant={active ? "default" : "outline"}
              size="sm"
              onClick={() => setFilters((f) => ({ ...f, tags: toggleTag(f.tags, tag) }))}
            >
              {tag}
            </Button>
          )
        })}

        {filters.tags.length ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setFilters((f) => ({ ...f, tags: [] }))}
          >
            Clear tags
          </Button>
        ) : null}
      </div>

      <SearchList>
        {query.trim().length === 0 ? (
          <div className="py-6 text-center text-sm text-muted-foreground">Type to search.</div>
        ) : status === "loading" && items.length === 0 ? (
          <div className="py-6 text-center text-sm text-muted-foreground">Loading…</div>
        ) : status === "error" && items.length === 0 ? (
          <div className="py-6 text-center text-sm text-destructive">Something went wrong.</div>
        ) : items.length === 0 ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            No results for “{query.trim()}”.
          </div>
        ) : (
          <>
            <div className="px-3 py-2 text-xs text-muted-foreground">
              Filters: {" "}
              <Badge variant="secondary">{filters.scope}</Badge>{" "}
              {filters.tags.map((t) => (
                <Badge key={t} variant="secondary" className="ml-1">
                  {t}
                </Badge>
              ))}
            </div>

            <SearchSeparator />

            <SearchGroup heading="Results">
              {items.map((r) => (
                <SearchItem key={r.id} value={r.id} onSelect={() => {}}>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="shrink-0">
                      {r.kind}
                    </Badge>
                    <span className="truncate">{r.label}</span>
                  </div>
                </SearchItem>
              ))}
            </SearchGroup>
          </>
        )}
      </SearchList>
    </Search>
  )
}
```

---

## Notes

* Keep filters serializable (good for URLs, caching, analytics).
* In remote mode, filters belong to the API request key.
* Consider putting filters in the URL for shareable search state.
