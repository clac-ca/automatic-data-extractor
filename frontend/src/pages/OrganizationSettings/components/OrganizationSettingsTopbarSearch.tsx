import { useEffect, useMemo, useRef, useState } from "react";
import { Search as SearchIcon } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Search,
  SearchDialog,
  SearchEmpty,
  SearchGroup,
  SearchInput,
  SearchItem,
  SearchList,
} from "@/components/ui/search";
import type { OrganizationSettingsNavGroup } from "@/pages/OrganizationSettings/settingsNav";

interface OrganizationSettingsTopbarSearchProps {
  readonly navGroups: readonly OrganizationSettingsNavGroup[];
  readonly className?: string;
}

type SearchItemOption = {
  id: string;
  label: string;
  description: string;
  href: string;
  group: string;
};

function flattenNavGroups(navGroups: readonly OrganizationSettingsNavGroup[]): SearchItemOption[] {
  return navGroups.flatMap((group) =>
    group.items.map((item) => ({
      id: item.id,
      label: item.label,
      description: item.description,
      href: item.href,
      group: group.label,
    })),
  );
}

function filterItems(items: SearchItemOption[], query: string) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return items;
  }
  return items.filter((item) => {
    const haystack = `${item.label} ${item.description} ${item.group}`.toLowerCase();
    return haystack.includes(normalizedQuery);
  });
}

export function OrganizationSettingsTopbarSearch({
  navGroups,
  className,
}: OrganizationSettingsTopbarSearchProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [shortcutHint, setShortcutHint] = useState("Ctrl K");
  const inputRef = useRef<HTMLInputElement | null>(null);
  const allItems = useMemo(() => flattenNavGroups(navGroups), [navGroups]);
  const filteredItems = useMemo(() => filterItems(allItems, query), [allItems, query]);

  useEffect(() => {
    const ua = typeof navigator === "undefined" ? "" : navigator.userAgent;
    const isApple = /Mac|iPhone|iPad|iPod/i.test(ua);
    setShortcutHint(isApple ? "⌘ K" : "Ctrl K");
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const key = event.key.toLowerCase();
      if (key !== "k") return;
      if (!event.metaKey && !event.ctrlKey) return;
      if (event.shiftKey || event.altKey) return;

      const target = event.target as HTMLElement | null;
      const isTypingContext =
        !!target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable);
      if (isTypingContext) return;

      event.preventDefault();
      setOpen(true);
      inputRef.current?.focus();
      inputRef.current?.select();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const selectSection = (href: string) => {
    setOpen(false);
    if (location.pathname === href) {
      return;
    }
    navigate(href);
  };

  return (
    <>
      <Search
        shouldFilter={false}
        label="Search organization settings"
        className={cn(
          "relative w-full min-w-0 max-w-xl overflow-visible rounded-full border bg-card text-card-foreground shadow-sm transition-colors",
          "border-border/70 hover:bg-card/95 dark:hover:bg-card/90",
          "focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/30",
          "[&_[cmdk-input-wrapper]]:border-b-0 [&_[cmdk-input-wrapper]]:h-9 [&_[cmdk-input-wrapper]]:px-3",
          "[&_[cmdk-input]]:h-9 [&_[cmdk-input]]:py-0 [&_[cmdk-input]]:text-card-foreground",
          "[&_[data-slot=search-input-wrapper]_svg]:opacity-60",
          className,
        )}
      >
        <div className="relative w-full">
          <SearchInput
            ref={inputRef}
            value={query}
            onValueChange={setQuery}
            onFocus={() => setOpen(true)}
            onBlur={() => {
              window.setTimeout(() => setOpen(false), 120);
            }}
            onKeyDown={(event) => {
              if (event.key !== "Enter") return;
              const first = filteredItems[0];
              if (!first) return;
              event.preventDefault();
              selectSection(first.href);
            }}
            placeholder="Search settings sections..."
            aria-label="Search organization settings sections"
            className="pr-16"
          />
          {query.trim().length === 0 ? (
            <kbd className="pointer-events-none absolute right-3 inset-y-0 my-auto hidden h-5 items-center rounded bg-muted px-1.5 text-[10px] font-semibold leading-none text-muted-foreground lg:inline-flex">
              {shortcutHint}
            </kbd>
          ) : null}
        </div>
        {open ? (
          <SearchList
            className="absolute left-0 top-[calc(100%+0.5rem)] z-50 max-h-80 w-full rounded-xl border border-border bg-popover p-1 shadow-lg"
            onMouseDown={(event) => event.preventDefault()}
          >
            <SearchGroup heading="Sections">
              {filteredItems.map((item) => (
                <SearchItem key={item.id} value={item.id} onSelect={() => selectSection(item.href)}>
                  <div className="flex min-w-0 flex-col">
                    <span className="truncate font-medium">{item.label}</span>
                    <span className="truncate text-xs text-muted-foreground">{item.description}</span>
                  </div>
                </SearchItem>
              ))}
            </SearchGroup>
            {filteredItems.length === 0 ? <SearchEmpty>No matching sections</SearchEmpty> : null}
          </SearchList>
        ) : null}
      </Search>
    </>
  );
}

export function OrganizationSettingsTopbarSearchButton({
  navGroups,
  className,
}: OrganizationSettingsTopbarSearchProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const allItems = useMemo(() => flattenNavGroups(navGroups), [navGroups]);
  const filteredItems = useMemo(() => filterItems(allItems, query), [allItems, query]);

  const selectSection = (href: string) => {
    setOpen(false);
    if (location.pathname === href) {
      return;
    }
    navigate(href);
  };

  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label="Search organization settings sections"
        className={cn("h-9 w-9", className)}
        onClick={() => setOpen(true)}
      >
        <SearchIcon className="h-4 w-4" aria-hidden />
      </Button>

      <SearchDialog open={open} onOpenChange={setOpen} contentClassName="sm:max-w-lg">
        <SearchInput
          value={query}
          onValueChange={setQuery}
          placeholder="Search settings sections..."
          aria-label="Search organization settings sections"
        />
        <SearchList>
          <SearchGroup heading="Sections">
            {filteredItems.map((item) => (
              <SearchItem key={item.id} value={item.id} onSelect={() => selectSection(item.href)}>
                <div className="flex min-w-0 flex-col">
                  <span className="truncate font-medium">{item.label}</span>
                  <span className="truncate text-xs text-muted-foreground">{item.description}</span>
                </div>
              </SearchItem>
            ))}
          </SearchGroup>
          {filteredItems.length === 0 ? <SearchEmpty>No matching sections</SearchEmpty> : null}
        </SearchList>
      </SearchDialog>
    </>
  );
}
