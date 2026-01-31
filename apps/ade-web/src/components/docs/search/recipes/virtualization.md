# Recipe: Virtualization & Large Lists (performance-first)

This recipe is opinionated because it’s easy to “virtualize” and accidentally make UX worse.

## The rule: Search shouldn’t render thousands by default

For a command palette / search experience, the best performance strategy is usually:
- narrow results by typing
- cap results (e.g. 20–60)
- paginate or ask the user to type more if results are huge

If you’re trying to render thousands (e.g. time zones), you’re in “large option list” territory, not “search palette” territory.

### cmdk + true virtualization caveat

cmdk-based lists (like shadcn Command) are not designed with virtualization as a first-class feature. People run into this exact problem when trying to render huge lists (e.g. time zones) and virtualize them. :contentReference[oaicite:10]{index=10}

That doesn’t mean you can’t do it — it means you should document the tradeoffs clearly.

---

## Option A: Prefer “cap results + remote search”
This is the most “used-by-millions” approach:
- faster initial render
- no complicated keyboard edge cases
- predictable UX

If you’re returning 2,000 items, consider returning:
- top 50
- plus “refine your query” messaging
- or “load more” pagination

---

## Option B: Progressive enhancement with `content-visibility`
If your list is big but you **must** keep items mounted (e.g. because keyboard nav expects them),
a strong pragmatic tactic is using CSS `content-visibility: auto`.

It lets the browser skip layout/paint work for offscreen content. :contentReference[oaicite:11]{index=11}

Browser support is strong across modern browsers (see caniuse). :contentReference[oaicite:12]{index=12}

### Example: apply to each item

```css
/* apps/ade-web/src/styles/search.css (or wherever your global styles live) */

@supports (content-visibility: auto) {
  /* Tune selector to your SearchItem markup. */
  [data-slot="search-item"] {
    content-visibility: auto;
    /* Reserve space to avoid layout jumps while the browser skips rendering. */
    contain-intrinsic-size: 40px;
  }
}
```

**When this is a win**

* thousands of rows
* expensive row content (icons, highlights, badges)
* you want to keep DOM nodes (for cmdk behavior)

**When this is not enough**

* extremely large lists with heavy memory use
* you truly need “render only what’s visible”

---

## Option C: True virtualization with TanStack Virtual (headless)

TanStack Virtual is a headless utility to virtualize long lists. ([TanStack][5])
In React, `useVirtualizer` supports a `useFlushSync` option (and docs mention disabling it can help React 19 warnings/perf). ([TanStack][6])

### The tradeoff (be explicit)

True virtualization typically means “only visible items exist in the DOM.”
With cmdk, that can degrade:

* arrow-key navigation across unmounted items
* type-to-select across items that aren’t mounted
* “scroll to active item” behavior

If your UX depends heavily on cmdk’s built-in keyboard navigation across the full dataset,
prefer **Option B** or **cap results**.

### Copy/paste example: virtualized rendering inside SearchList

```tsx
"use client"

import * as React from "react"
import { useVirtualizer } from "@tanstack/react-virtual"
import { SearchList, SearchItem } from "@/components/ui/search"

type VirtualizedSearchListProps<T> = {
  items: T[]
  estimateItemSize?: number
  overscan?: number
  getKey: (item: T) => string
  getValue: (item: T) => string
  getKeywords?: (item: T) => string[] | undefined
  renderItem: (item: T) => React.ReactNode
  onSelect?: (item: T) => void
}

export function VirtualizedSearchList<T>({
  items,
  estimateItemSize = 40,
  overscan = 8,
  getKey,
  getValue,
  getKeywords,
  renderItem,
  onSelect,
}: VirtualizedSearchListProps<T>) {
  const parentRef = React.useRef<HTMLDivElement | null>(null)

  const rowVirtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => estimateItemSize,
    overscan,

    // If you see React 19 flushSync warnings or want better batching, disable it:
    // (TanStack Virtual defaults useFlushSync to true.) :contentReference[oaicite:15]{index=15}
    useFlushSync: false,
  })

  return (
    <SearchList ref={parentRef as any} className="relative max-h-64 overflow-y-auto">
      <div
        style={{
          height: rowVirtualizer.getTotalSize(),
          position: "relative",
        }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const item = items[virtualRow.index]
          return (
            <div
              key={getKey(item)}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              <SearchItem
                value={getValue(item)}
                keywords={getKeywords?.(item)}
                onSelect={() => onSelect?.(item)}
              >
                {renderItem(item)}
              </SearchItem>
            </div>
          )
        })}
      </div>
    </SearchList>
  )
}
```

### Practical guidance

* Only enable virtualization above a threshold (e.g. > 200 items).
* Keep row heights consistent if possible (performance + correctness).
* If you need dynamic heights, use TanStack Virtual measurement APIs (more complexity).

---

## Alternative libraries

* `react-window` is a stable, commonly used virtualization library. ([web.dev][7])
* The core tradeoffs with cmdk still apply.

---

## Recommended doc note to add in your Search docs

> For best UX, avoid rendering huge result sets in search palettes. Prefer narrowing + caps + pagination.
> Virtualization is provided as an advanced pattern and can affect keyboard navigation behavior.

[5]: https://tanstack.com/virtual/latest/docs?utm_source=chatgpt.com "Introduction | TanStack Virtual Docs"
[6]: https://tanstack.com/virtual/v3/docs/framework/react/react-virtual "React Virtual | TanStack Virtual React Docs"
[7]: https://web.dev/articles/virtualize-long-lists-react-window?utm_source=chatgpt.com "Virtualize large lists with react-window | Articles"
