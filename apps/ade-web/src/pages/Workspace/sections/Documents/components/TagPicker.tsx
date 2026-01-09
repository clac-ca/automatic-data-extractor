import clsx from "clsx";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchTagCatalog } from "@api/documents/tags";
import { Input } from "@/components/ui/input";

import { CheckIcon, ChevronDownIcon, CloseIcon, SearchIcon, TagIcon } from "@components/icons";

export function TagPicker({
  workspaceId,
  selected,
  onToggle,
  placeholder,
  disabled,
  buttonClassName,
  onOpenChange,
}: {
  workspaceId: string;
  selected: string[];
  onToggle: (tag: string) => void;
  placeholder: string;
  disabled?: boolean;
  buttonClassName?: string;
  onOpenChange?: (open: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const listId = useId();
  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
  }, []);
  const toggleOpen = useCallback(() => {
    setOpen((prev) => {
      if (prev) setQuery("");
      return !prev;
    });
  }, []);

  const effectiveQuery = query.trim();
  const canSearch = effectiveQuery.length >= 2;

  const tagsQuery = useQuery({
    queryKey: ["documents", workspaceId, "tags", { q: canSearch ? effectiveQuery : "" }],
    queryFn: ({ signal }) =>
      fetchTagCatalog(
        workspaceId,
        {
          page: 1,
          perPage: 20,
          sort: "-count",
          q: canSearch ? effectiveQuery : undefined,
        },
        signal,
      ),
    enabled: open && workspaceId.length > 0,
    staleTime: 30_000,
  });

  const items = useMemo(() => tagsQuery.data?.items ?? [], [tagsQuery.data?.items]);

  const createCandidate = useMemo(() => {
    const t = effectiveQuery;
    if (!t) return null;
    const exact = items.some((i) => i.tag.toLowerCase() === t.toLowerCase());
    if (exact) return null;
    return t;
  }, [effectiveQuery, items]);

  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
    }
  }, [open]);

  useEffect(() => {
    onOpenChange?.(open);
  }, [onOpenChange, open]);

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (!target) return;
      if (containerRef.current?.contains(target)) return;
      close();
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
      }
    };
    window.addEventListener("mousedown", handleClickOutside);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("mousedown", handleClickOutside);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [close, open]);

  return (
    <div
      ref={containerRef}
      className={clsx("relative", open ? "z-[var(--app-z-popover)]" : "z-0")}
      data-ignore-row-click="true"
    >
      <button
        type="button"
        onClick={toggleOpen}
        disabled={disabled}
        ref={triggerRef}
        className={clsx(
          "inline-flex min-w-0 items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-60",
          disabled
            ? "border-border bg-background text-muted-foreground"
            : "border-border bg-card text-foreground hover:bg-background dark:hover:bg-muted/40",
          buttonClassName,
        )}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls={open ? listId : undefined}
      >
        <TagIcon className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
        {selected.length === 0 ? (
          <span className="min-w-0 truncate text-muted-foreground">{placeholder}</span>
        ) : (
          <span className="min-w-0 truncate">
            {selected.slice(0, 2).join(", ")}
            {selected.length > 2 ? ` +${selected.length - 2}` : ""}
          </span>
        )}
        <ChevronDownIcon
          className={clsx("h-3.5 w-3.5 text-muted-foreground transition", open && "rotate-180")}
        />
      </button>

      {open ? (
        <div
          className="absolute left-0 top-[calc(100%+0.5rem)] z-[var(--app-z-popover)] w-[20rem] rounded-2xl border border-border bg-card p-3 shadow-lg"
          data-ignore-row-click="true"
          role="listbox"
          id={listId}
          aria-multiselectable
        >
          <div className="mb-2">
            <div className="relative">
              <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search or create tag…"
                className="h-9 pl-9"
              />
            </div>
            <div className="mt-1 text-[11px] text-muted-foreground">
              Type 2+ characters to search existing tags.
            </div>
          </div>

          {selected.length ? (
            <div className="mb-2 flex flex-wrap gap-1">
              {selected.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => onToggle(t)}
                  className="inline-flex items-center gap-1 rounded-full border border-border bg-background px-2 py-0.5 text-[11px] font-semibold text-foreground hover:text-destructive"
                  title="Remove tag"
                >
                  {t}
                  <CloseIcon className="h-3 w-3" />
                </button>
              ))}
            </div>
          ) : null}

          <div className="max-h-56 overflow-y-auto rounded-xl border border-border">
            {createCandidate ? (
              <button
                type="button"
                onClick={() => onToggle(createCandidate)}
                role="option"
                aria-selected={false}
                className="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-semibold text-foreground hover:bg-background dark:hover:bg-muted/40"
              >
                <span>Create “{createCandidate}”</span>
                <span className="text-[11px] text-muted-foreground">new</span>
              </button>
            ) : null}

            {tagsQuery.isLoading ? (
              <div className="px-3 py-3 text-xs text-muted-foreground">Loading tags…</div>
            ) : items.length === 0 ? (
              <div className="px-3 py-3 text-xs text-muted-foreground">
                {canSearch ? "No matches." : "No tags yet."}
              </div>
            ) : (
              items.map((item) => {
                const isSelected = selected.includes(item.tag);
                return (
                  <button
                    key={item.tag}
                    type="button"
                    onClick={() => onToggle(item.tag)}
                    role="option"
                    aria-selected={isSelected}
                    className={clsx(
                      "flex w-full items-center justify-between px-3 py-2 text-left text-xs font-semibold transition",
                      isSelected
                        ? "bg-muted text-foreground"
                        : "text-foreground hover:bg-background dark:hover:bg-muted/40",
                    )}
                  >
                    <span className="truncate">{item.tag}</span>
                    <span className="ml-3 flex items-center gap-2 text-[11px] text-muted-foreground">
                      {item.document_count}
                      {isSelected ? <CheckIcon className="h-3.5 w-3.5 text-foreground" /> : null}
                    </span>
                  </button>
                );
              })
            )}
          </div>

          <div className="mt-2 text-[11px] text-muted-foreground">Click a tag to toggle it.</div>
        </div>
      ) : null}
    </div>
  );
}
