# Recipe: Omnibar / Command Palette (⌘K / Ctrl K)

Use this when search is a global entry point:
- navigation (pages)
- actions (create, toggle, switch workspace)
- recent items
- user-aware results

This recipe focuses on the small UX details:
- open with ⌘K / Ctrl K
- don’t trigger shortcuts while typing in inputs
- Esc clears query first; Esc again closes
- close dialog on selection
- reset query when dialog closes (optional, but feels clean)

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
  SearchShortcut,
  SearchSeparator,
} from "@/components/ui/search"
import { Button } from "@/components/ui/button"

// Prevent global shortcut from firing while typing.
function isTypingElement(target: EventTarget | null) {
  const el = target as HTMLElement | null
  if (!el) return false
  const tag = el.tagName
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable
}

function useCommandK(onOpen: () => void) {
  React.useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (isTypingElement(e.target)) return

      const key = e.key.toLowerCase()
      const isMac = /Mac|iPhone|iPad|iPod/i.test(navigator.userAgent)
      const mod = isMac ? e.metaKey : e.ctrlKey

      if (mod && key === "k") {
        e.preventDefault()
        onOpen()
      }
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [onOpen])
}

export function OmnibarExample() {
  const [open, setOpen] = React.useState(false)
  const [query, setQuery] = React.useState("")

  useCommandK(() => setOpen(true))

  // Optional: reset query when closing
  React.useEffect(() => {
    if (!open) setQuery("")
  }, [open])

  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}>
        Search <span className="ml-2 text-xs text-muted-foreground">⌘K</span>
      </Button>

      <SearchDialog
        open={open}
        onOpenChange={setOpen}
        searchProps={{
          // Esc behavior: clear query first; otherwise allow Dialog to close.
          onKeyDown: (e) => {
            if (e.key === "Escape" && query) {
              e.preventDefault()
              setQuery("")
            }
          },
        }}
      >
        <SearchInput
          value={query}
          onValueChange={setQuery}
          placeholder="Search for pages, settings, commands…"
        />

        <SearchList>
          {query.trim().length === 0 ? (
            <div className="px-3 py-6 text-sm text-muted-foreground">
              Try typing <span className="font-medium text-foreground">“settings”</span> or{" "}
              <span className="font-medium text-foreground">“new”</span>.
            </div>
          ) : null}

          <SearchGroup heading="Navigation">
            <SearchItem
              value="nav:home"
              onSelect={() => {
                setOpen(false)
                // router.push("/")
              }}
            >
              Home
              <SearchShortcut>↵</SearchShortcut>
            </SearchItem>

            <SearchItem
              value="nav:settings"
              keywords={["preferences", "account"]}
              onSelect={() => {
                setOpen(false)
                // router.push("/settings")
              }}
            >
              Settings
              <SearchShortcut>↵</SearchShortcut>
            </SearchItem>
          </SearchGroup>

          <SearchSeparator />

          <SearchGroup heading="Actions">
            <SearchItem
              value="action:new"
              keywords={["create", "add"]}
              onSelect={() => {
                setOpen(false)
                // openCreateModal()
              }}
            >
              Create new…
              <SearchShortcut>⌘↵</SearchShortcut>
            </SearchItem>

            <SearchItem
              value="action:toggle-theme"
              keywords={["dark", "light", "theme"]}
              onSelect={() => {
                setOpen(false)
                // toggleTheme()
              }}
            >
              Toggle theme
              <SearchShortcut>T</SearchShortcut>
            </SearchItem>
          </SearchGroup>
        </SearchList>
      </SearchDialog>
    </>
  )
}
```

---

## Notes

* Keep command palette results short and high-signal (20–60 items).
* Use `keywords` to make matching feel “smart”.
* Group navigation vs actions; users build a mental model quickly.
