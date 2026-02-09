import { useEffect, useMemo, useRef, useState } from "react";
import { Search as SearchIcon } from "lucide-react";
import { parseAsString, useQueryState } from "nuqs";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Search,
  SearchDialog,
  SearchInput,
} from "@/components/ui/search";

interface WorkspacesTopbarSearchProps {
  readonly className?: string;
}

const PAGE_QUERY_KEY = "page";

export function WorkspacesTopbarSearch({ className }: WorkspacesTopbarSearchProps) {
  const [searchValue, setSearchValue] = useQueryState("q", parseAsString);
  const [pageValue, setPageValue] = useQueryState(PAGE_QUERY_KEY, parseAsString);
  const [shortcutHint, setShortcutHint] = useState("Ctrl K");
  const inputRef = useRef<HTMLInputElement | null>(null);
  const searchQuery = useMemo(() => searchValue ?? "", [searchValue]);

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
      inputRef.current?.focus();
      inputRef.current?.select();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleSearchChange = (nextValue: string) => {
    const normalized = nextValue.trim().length > 0 ? nextValue : null;
    void setSearchValue(normalized);
    if (pageValue && pageValue !== "1") {
      void setPageValue(null);
    }
  };

  return (
    <>
      <Search
        shouldFilter={false}
        label="Search workspaces"
        className={cn(
          "w-full min-w-0 max-w-xl overflow-hidden rounded-full border bg-card text-card-foreground shadow-sm transition-colors",
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
            value={searchQuery}
            onValueChange={handleSearchChange}
            placeholder="Search workspaces..."
            aria-label="Search workspaces"
            className="pr-16"
          />
          {searchQuery.trim().length === 0 ? (
            <kbd className="pointer-events-none absolute right-3 inset-y-0 my-auto hidden h-5 items-center rounded bg-muted px-1.5 text-[10px] font-semibold leading-none text-muted-foreground lg:inline-flex">
              {shortcutHint}
            </kbd>
          ) : null}
        </div>
      </Search>
    </>
  );
}

export function WorkspacesTopbarSearchButton({ className }: { readonly className?: string }) {
  const [open, setOpen] = useState(false);
  const [searchValue, setSearchValue] = useQueryState("q", parseAsString);
  const [pageValue, setPageValue] = useQueryState(PAGE_QUERY_KEY, parseAsString);
  const searchQuery = useMemo(() => searchValue ?? "", [searchValue]);

  const handleSearchChange = (nextValue: string) => {
    const normalized = nextValue.trim().length > 0 ? nextValue : null;
    void setSearchValue(normalized);
    if (pageValue && pageValue !== "1") {
      void setPageValue(null);
    }
  };

  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label="Search workspaces"
        className={cn("h-9 w-9", className)}
        onClick={() => setOpen(true)}
      >
        <SearchIcon className="h-4 w-4" aria-hidden />
      </Button>

      <SearchDialog open={open} onOpenChange={setOpen} contentClassName="sm:max-w-lg">
        <SearchInput
          value={searchQuery}
          onValueChange={handleSearchChange}
          placeholder="Search workspaces..."
          aria-label="Search workspaces"
        />
      </SearchDialog>
    </>
  );
}
