"use client";

import * as React from "react";

import { CloseIcon, PlusIcon } from "@/components/icons";
import { Badge } from "@/components/ui/badge";
import { Command, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

type TagSelectorProps = {
  /** Selected tags (controlled). */
  value: string[];
  /** Selected tags change (controlled). */
  onValueChange: (next: string[]) => void;

  /** Available options to choose from. */
  options?: string[];
  /**
   * Option list change (controlled by the parent).
   * If provided, newly created tags can be appended here so all instances see them immediately.
   */
  onOptionsChange?: (next: string[]) => void;

  /** Disable all interactions. */
  disabled?: boolean;

  /** Allow creating a new tag when there's no exact match. */
  allowCreate?: boolean;

  /**
   * Called when a tag is created (for persistence).
   * Can be async. Component does not block UX on it by default.
   */
  onCreate?: (tag: string) => void | Promise<void>;

  /** Popover open (controlled). */
  open?: boolean;
  /** Popover open (uncontrolled initial). */
  defaultOpen?: boolean;
  /** Popover open change. */
  onOpenChange?: (open: boolean) => void;

  /** Trigger element (Button, etc). */
  children: React.ReactElement;

  /** Placeholder for the input. */
  placeholder?: string;

  /** Empty state text. */
  emptyText?: string | ((query: string) => string);

  /** Customize the “Create …” row text. */
  createText?: (tag: string) => React.ReactNode;

  /** Customize filtering. Defaults to case-insensitive substring match. */
  filterOption?: (option: string, query: string) => boolean;

  /** Styling hooks. */
  className?: string;
  contentClassName?: string;

  /** Keep the menu open after selecting an option. Defaults to true (multi-select UX). */
  keepOpenOnSelect?: boolean;

  /** If true, pressing Enter with no matches creates the tag (when creatable). */
  createOnEnterWhenEmpty?: boolean;
};

function normalize(input: string) {
  return input.trim();
}

function keyOf(input: string) {
  return normalize(input).toLowerCase();
}

function uniqByKey(values: string[]) {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const v of values) {
    const k = keyOf(v);
    if (!k) continue;
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(v);
  }
  return out;
}

export function TagSelector({
  value,
  onValueChange,
  options = [],
  onOptionsChange,
  disabled = false,
  allowCreate = true,
  onCreate,

  open: openProp,
  defaultOpen = false,
  onOpenChange,

  children,
  placeholder = "Search or create tags…",
  emptyText,
  createText,
  filterOption,
  className,
  contentClassName,

  keepOpenOnSelect = true,
  createOnEnterWhenEmpty = true,
}: TagSelectorProps) {
  const [openUncontrolled, setOpenUncontrolled] = React.useState(defaultOpen);
  const open = openProp ?? openUncontrolled;

  const setOpen = React.useCallback(
    (next: boolean) => {
      // Block opening when disabled, but allow closing.
      if (disabled && next) return;

      if (openProp === undefined) setOpenUncontrolled(next);
      onOpenChange?.(next);
    },
    [disabled, onOpenChange, openProp]
  );

  const [search, setSearch] = React.useState("");
  const [createdLocal, setCreatedLocal] = React.useState<string[]>([]);

  const inputRef = React.useRef<HTMLInputElement>(null);

  // Reset search when closing (works for controlled or uncontrolled open).
  React.useEffect(() => {
    if (!open) setSearch("");
  }, [open]);

  // Focus input on open.
  React.useEffect(() => {
    if (!open || disabled) return;
    requestAnimationFrame(() => inputRef.current?.focus());
  }, [open, disabled]);

  const query = normalize(search);
  const queryKey = keyOf(search);

  // Merge options with locally created tags (improves UX within this instance).
  const mergedOptions = React.useMemo(() => {
    return uniqByKey([...options, ...createdLocal]);
  }, [options, createdLocal]);

  const selectedKeys = React.useMemo(() => {
    return new Set(value.map(keyOf).filter(Boolean));
  }, [value]);

  const optionKeys = React.useMemo(() => {
    return new Set(mergedOptions.map(keyOf).filter(Boolean));
  }, [mergedOptions]);

  const hasExactMatch = queryKey.length > 0 && (selectedKeys.has(queryKey) || optionKeys.has(queryKey));

  const canCreate = allowCreate && !disabled && query.length > 0 && !hasExactMatch;

  const defaultFilter: NonNullable<TagSelectorProps["filterOption"]> = React.useCallback(
    (option, q) => keyOf(option).includes(keyOf(q)),
    []
  );

  const filteredOptions = React.useMemo(() => {
    const fn = filterOption ?? defaultFilter;
    if (!query) return mergedOptions;
    return mergedOptions.filter((opt) => fn(opt, query));
  }, [mergedOptions, query, filterOption, defaultFilter]);

  const resolvedEmptyText = React.useMemo(() => {
    const fallback = query ? "No matches." : "No tags.";
    if (typeof emptyText === "function") return emptyText(query);
    return emptyText ?? fallback;
  }, [emptyText, query]);

  const focusInput = React.useCallback(() => {
    requestAnimationFrame(() => inputRef.current?.focus());
  }, []);

  const removeByKey = React.useCallback(
    (tagKey: string) => {
      const next = value.filter((t) => keyOf(t) !== tagKey);
      onValueChange(next);
    },
    [onValueChange, value]
  );

  const toggle = React.useCallback(
    (tag: string) => {
      if (disabled) return;

      const k = keyOf(tag);
      if (!k) return;

      const exists = value.some((t) => keyOf(t) === k);
      const next = exists ? value.filter((t) => keyOf(t) !== k) : [...value, tag];
      onValueChange(next);
    },
    [disabled, onValueChange, value]
  );

  const commitCreate = React.useCallback(() => {
    if (!canCreate) return;

    const created = query;
    const createdK = keyOf(created);
    if (!createdK) return;

    // Update local options so the tag remains selectable even if parent doesn't update options.
    setCreatedLocal((prev) => uniqByKey([...prev, created]));

    // Update shared options if parent provides it (THIS is what fixes bug #2 across documents).
    if (onOptionsChange) {
      onOptionsChange(uniqByKey([...options, created]));
    }

    // Fire create side-effect (persist).
    // Intentionally not awaited; parent can handle async + errors as desired.
    onCreate?.(created);

    // Select it.
    onValueChange([...value, created]);

    setSearch("");
    focusInput();
  }, [canCreate, focusInput, onCreate, onOptionsChange, onValueChange, options, query, value]);

  const handleSelectOption = React.useCallback(
    (tag: string) => {
      toggle(tag);
      focusInput();
      if (!keepOpenOnSelect) setOpen(false);
    },
    [focusInput, keepOpenOnSelect, setOpen, toggle]
  );

  const handleBackspace = React.useCallback(() => {
    if (disabled) return;
    if (search.length !== 0) return;
    if (value.length === 0) return;

    const last = value[value.length - 1];
    if (!last) return;

    removeByKey(keyOf(last));
    focusInput();
  }, [disabled, focusInput, removeByKey, search.length, value]);

  return (
    <div className={cn("min-w-0", className)}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>{children}</PopoverTrigger>

        <PopoverContent
          align="start"
          className={cn("w-64 p-0", contentClassName)}
          onOpenAutoFocus={(e) => {
            // Keep focus in the input rather than PopoverContent.
            e.preventDefault();
            inputRef.current?.focus();
          }}
          onCloseAutoFocus={(e) => {
            // Let trigger regain focus naturally.
            e.preventDefault();
          }}
        >
          <Command shouldFilter={false}>
            <div className="border-b px-2 py-2">
              <div className="flex flex-wrap items-center gap-1 rounded-md border border-input bg-background px-2 py-1 text-[11px] shadow-xs focus-within:ring-1 focus-within:ring-ring">
                {value.map((tag) => (
                  <Badge
                    key={keyOf(tag) || tag}
                    variant="secondary"
                    className="max-w-full gap-1 px-1.5 py-0 text-[10px]"
                    title={tag}
                  >
                    <span className="min-w-0 truncate">{tag}</span>
                    <button
                      type="button"
                      disabled={disabled}
                      aria-label={`Remove tag ${tag}`}
                      className="rounded-sm p-0.5 text-muted-foreground transition hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
                      onMouseDown={(e) => {
                        // Prevent input blur when clicking remove.
                        e.preventDefault();
                      }}
                      onClick={() => {
                        if (disabled) return;
                        removeByKey(keyOf(tag));
                        focusInput();
                      }}
                    >
                      <CloseIcon aria-hidden className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}

                <CommandInput
                  ref={inputRef}
                  value={search}
                  onValueChange={setSearch}
                  disabled={disabled}
                  placeholder={placeholder}
                  className="min-w-[6ch] flex-1 bg-transparent py-1 text-[11px] outline-none placeholder:text-muted-foreground"
                  onKeyDown={(e) => {
                    if (e.key === "Backspace") {
                      // Bug #3: remove last tag but keep dropdown open.
                      // We never close on value changes.
                      if (search.length === 0) {
                        e.preventDefault();
                        handleBackspace();
                      }
                    }

                    if (e.key === "Enter") {
                      // If there are no matches and it's creatable, Enter creates.
                      // This avoids the "I typed a new tag but got stuck on empty state" UX.
                      if (createOnEnterWhenEmpty && canCreate && filteredOptions.length === 0) {
                        e.preventDefault();
                        e.stopPropagation();
                        commitCreate();
                      }
                    }

                    if (e.key === "Escape") {
                      // Close quickly.
                      e.preventDefault();
                      setOpen(false);
                    }
                  }}
                />
              </div>
            </div>

            <CommandList className="max-h-64 overflow-auto">
              {/* Bug #1 fix: empty state only when there are no visible options AND we are not showing Create. */}
              {filteredOptions.length === 0 && !canCreate ? (
                <div className="px-3 py-6 text-center text-[11px] text-muted-foreground">
                  {resolvedEmptyText}
                </div>
              ) : null}

              {canCreate ? (
                <CommandGroup>
                  <CommandItem
                    value={`__create__:${queryKey}`}
                    onSelect={() => commitCreate()}
                    className="gap-2"
                  >
                    <PlusIcon aria-hidden className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="truncate">
                      {createText ? createText(query) : <>Create “{query}”</>}
                    </span>
                  </CommandItem>
                </CommandGroup>
              ) : null}

              {filteredOptions.length > 0 ? (
                <CommandGroup>
                  {filteredOptions.map((tag) => (
                    <CommandItem key={keyOf(tag) || tag} value={tag} onSelect={() => handleSelectOption(tag)}>
                      <span className="truncate">{tag}</span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              ) : null}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}
