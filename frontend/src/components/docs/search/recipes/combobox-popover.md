# Recipe: Combobox Dropdown (Popover + single input)

Use this when search behaves like a form field:
- click/focus to open
- results appear in a dropdown under the input
- selection closes the dropdown
- input stays the single source of truth (avoid duplicating inputs)

This recipe shows the *composition approach*: `Search` + shadcn `Popover`.

---

## Copy/paste example (single input + PopoverContent list)

```tsx
import * as React from "react"
import * as PopoverPrimitive from "@radix-ui/react-popover"
import { Popover, PopoverContent } from "@/components/ui/popover"
import {
  Search,
  SearchList,
  SearchGroup,
  SearchItem,
} from "@/components/ui/search"
import { Command as CommandPrimitive } from "cmdk"
import { Search as SearchIcon } from "lucide-react"
import { cn } from "@/lib/utils"

type Option = { id: string; label: string; keywords?: string[] }

function ComboboxField({
  value,
  onValueChange,
  placeholder = "Search…",
  onFocus,
}: {
  value: string
  onValueChange: (v: string) => void
  placeholder?: string
  onFocus?: React.FocusEventHandler<HTMLInputElement>
}) {
  // This is intentionally a custom field so it looks like a normal input.
  // (The default SearchInput is tuned for “palette” layout with a divider.)
  return (
    <div className="flex h-10 items-center gap-2 rounded-md border bg-background px-3">
      <SearchIcon className="size-4 shrink-0 opacity-50" aria-hidden="true" />
      <CommandPrimitive.Input
        value={value}
        onValueChange={onValueChange}
        placeholder={placeholder}
        className={cn(
          "h-full w-full bg-transparent text-sm outline-none",
          "placeholder:text-muted-foreground"
        )}
        onFocus={onFocus}
      />
    </div>
  )
}

export function SearchComboboxExample() {
  const [open, setOpen] = React.useState(false)
  const [query, setQuery] = React.useState("")

  const options: Option[] = [
    { id: "apple", label: "Apple", keywords: ["fruit"] },
    { id: "banana", label: "Banana", keywords: ["fruit"] },
    { id: "carrot", label: "Carrot", keywords: ["vegetable"] },
  ]

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <Search className="w-full max-w-sm bg-transparent text-foreground">
        <PopoverPrimitive.Anchor asChild>
          <div data-slot="combobox-anchor">
            <ComboboxField
              value={query}
              onValueChange={setQuery}
              placeholder="Pick an ingredient…"
              onFocus={() => setOpen(true)}
            />
          </div>
        </PopoverPrimitive.Anchor>

        <PopoverContent
          align="start"
          side="bottom"
          sideOffset={6}
          className="w-[var(--radix-popover-trigger-width)] p-0"
          // Keep focus on the input when opening.
          onOpenAutoFocus={(e) => e.preventDefault()}
          // Don’t close when clicking the input again.
          onInteractOutside={(e) => {
            const target = e.target as HTMLElement
            if (target.closest('[data-slot="combobox-anchor"]')) e.preventDefault()
          }}
        >
          <div className="rounded-md border bg-popover text-popover-foreground shadow-md">
            <SearchList className="max-h-64">
              <SearchGroup heading="Options">
                {options.map((opt) => (
                  <SearchItem
                    key={opt.id}
                    value={opt.id}
                    keywords={opt.keywords}
                    onSelect={() => {
                      // “select” behavior is your choice:
                      // 1) set query to label
                      setQuery(opt.label)
                      // 2) close dropdown
                      setOpen(false)
                    }}
                  >
                    {opt.label}
                  </SearchItem>
                ))}
              </SearchGroup>

              {options.length === 0 ? (
                <div className="py-6 text-center text-sm text-muted-foreground">
                  No options.
                </div>
              ) : null}
            </SearchList>
          </div>
        </PopoverContent>
      </Search>
    </Popover>
  )
}
```

---

## Notes

* For a “true combobox”, you’ll often set the input value to the selected label and store the real value separately.
* For remote search comboboxes, set `<Search shouldFilter={false} />` and fetch results from an API.
* The `onInteractOutside` guard prevents the popover from closing when users click the input.
