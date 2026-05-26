import * as React from "react";

import { CloseIcon, PlusIcon, TagIcon } from "@/components/icons";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Command, CommandGroup, CommandItem, CommandList } from "@/components/ui/command";
import { Input } from "@/components/ui/input";
import { Popover, PopoverAnchor, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export function TagsCell({
  selected,
  tagOptions,
  onToggle,
  disabled = false,
  className,
  onTagOptionsChange,
  onCreateTag,
}: {
  selected: string[];
  tagOptions: string[];
  onToggle: (tag: string) => void;
  disabled?: boolean;
  className?: string;
  onTagOptionsChange?: (nextOptions: string[]) => void;
  onCreateTag?: (tag: string) => void | Promise<void>;
}) {
  const [open, setOpen] = React.useState(false);
  const [search, setSearch] = React.useState("");
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const anchorRef = React.useRef<HTMLDivElement | null>(null);
  const query = search.trim();
  const queryKey = query.toLowerCase();

  React.useEffect(() => {
    if (!open) {
      setSearch("");
      return;
    }
    requestAnimationFrame(() => inputRef.current?.focus());
  }, [open]);

  const allOptions = React.useMemo(() => {
    const seen = new Set<string>();
    const next: string[] = [];
    for (const tag of [...selected, ...tagOptions]) {
      const key = tag.trim().toLowerCase();
      if (!key || seen.has(key)) continue;
      seen.add(key);
      next.push(tag);
    }
    return next;
  }, [selected, tagOptions]);

  const filteredOptions = React.useMemo(() => {
    if (!queryKey) return allOptions;
    return allOptions.filter((tag) => tag.toLowerCase().includes(queryKey));
  }, [allOptions, queryKey]);

  const hasExactMatch = allOptions.some((tag) => tag.toLowerCase() === queryKey);
  const canCreate = query.length > 0 && !hasExactMatch && !disabled;

  const handleValueChange = React.useCallback(
    (next: string[]) => {
      const removed = selected.find((t) => !next.includes(t));
      const added = next.find((t) => !selected.includes(t));
      const changed = added ?? removed;
      if (changed) onToggle(changed);
    },
    [onToggle, selected],
  );

  const toggleTag = React.useCallback(
    (tag: string) => {
      const exists = selected.some((item) => item.toLowerCase() === tag.toLowerCase());
      handleValueChange(exists ? selected.filter((item) => item.toLowerCase() !== tag.toLowerCase()) : [...selected, tag]);
    },
    [handleValueChange, selected],
  );

  const createTag = React.useCallback(() => {
    if (!canCreate) return;
    const nextOptions = [...allOptions, query];
    onTagOptionsChange?.(nextOptions);
    void onCreateTag?.(query);
    handleValueChange([...selected, query]);
    setSearch("");
    requestAnimationFrame(() => inputRef.current?.focus());
  }, [allOptions, canCreate, handleValueChange, onCreateTag, onTagOptionsChange, query, selected]);

  return (
    <div className={cn("min-w-0", className)} data-row-interactive data-ignore-row-click>
      <Popover open={open} onOpenChange={(next) => !disabled && setOpen(next)}>
        {open ? (
          <PopoverAnchor asChild>
            <div
              ref={anchorRef}
              className="flex h-7 w-[180px] items-center gap-2 rounded-md border border-border/70 bg-background px-2 text-[11px] shadow-xs"
              data-row-interactive
            >
              <TagIcon aria-hidden className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              <Input
                ref={inputRef}
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    event.preventDefault();
                    setOpen(false);
                  }
                  if (event.key === "Enter" && canCreate) {
                    event.preventDefault();
                    createTag();
                  }
                }}
                placeholder={selected.length ? "Search or create tags..." : "Add tags..."}
                className="h-auto min-w-0 flex-1 border-0 bg-transparent p-0 text-[11px] font-normal shadow-none focus-visible:ring-0"
                disabled={disabled}
              />
            </div>
          </PopoverAnchor>
        ) : (
          <TooltipProvider delayDuration={150}>
            <Tooltip open={open ? false : undefined}>
              <TooltipTrigger asChild>
                <div data-row-interactive>
                  <PopoverTrigger asChild>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={disabled}
                      className="h-7 w-[180px] justify-start gap-1.5 rounded-md border-border/70 bg-background px-2 text-[11px] font-medium shadow-xs hover:border-ring/50 hover:bg-background"
                      aria-label="Edit tags"
                      data-row-interactive
                    >
                      <TagIcon aria-hidden className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                      {selected.length === 0 ? (
                        <span className="truncate text-muted-foreground">Add tags</span>
                      ) : (
                        <div className="flex min-w-0 flex-1 items-center gap-1 overflow-hidden">
                          {selected.length === 1 ? (
                            <Badge
                              variant="secondary"
                              className="rounded-xs px-1.5 py-0.5 text-[9px] font-medium leading-none shrink-0 justify-start max-w-[140px] bg-secondary/80 text-secondary-foreground border-none w-fit"
                            >
                              <span className="truncate w-full text-left">{selected[0]}</span>
                            </Badge>
                          ) : selected.length === 2 ? (
                            selected.map((tag) => (
                              <Badge
                                key={tag}
                                variant="secondary"
                                className="rounded-xs px-1.5 py-0.5 text-[9px] font-medium leading-none shrink-0 justify-start max-w-[65px] bg-secondary/80 text-secondary-foreground border-none w-fit"
                              >
                                <span className="truncate w-full text-left">{tag}</span>
                              </Badge>
                            ))
                          ) : (
                            <>
                              <Badge
                                variant="secondary"
                                className="rounded-xs px-1.5 py-0.5 text-[9px] font-medium leading-none shrink-0 justify-start max-w-[105px] bg-secondary/80 text-secondary-foreground border-none w-fit"
                              >
                                <span className="truncate w-full text-left">{selected[0]}</span>
                              </Badge>
                              <Badge
                                variant="secondary"
                                className="rounded-xs px-1.5 py-0.5 text-[9px] font-semibold leading-none shrink-0 bg-muted text-muted-foreground border-none"
                              >
                                +{selected.length - 1}
                              </Badge>
                            </>
                          )}
                        </div>
                      )}
                    </Button>
                  </PopoverTrigger>
                </div>
              </TooltipTrigger>
              {selected.length > 0 && (
                <TooltipContent
                  side="top"
                  align="center"
                  className="flex flex-col gap-1.5 p-2 bg-popover text-popover-foreground border border-border shadow-md max-w-[240px]"
                >
                  <div className="text-[9px] font-bold text-muted-foreground uppercase tracking-wider px-1">
                    Active Tags ({selected.length})
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {selected.map((tag) => (
                      <Badge
                        key={tag}
                        variant="secondary"
                        className="rounded-xs px-1.5 py-0.5 text-[10px] font-medium bg-secondary text-secondary-foreground border-none"
                      >
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </TooltipContent>
              )}
            </Tooltip>
          </TooltipProvider>
        )}
        <PopoverContent
          align="start"
          className="w-64 p-0 overflow-hidden"
          data-row-interactive
          onPointerDownCapture={(event) => {
            event.stopPropagation();
          }}
          onInteractOutside={(event) => {
            if (anchorRef.current?.contains(event.target as Node)) {
              event.preventDefault();
            }
          }}
        >
          {selected.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 border-b border-border bg-muted/20 p-2">
              {selected.map((tag) => (
                <Badge
                  key={tag}
                  variant="secondary"
                  className="flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-[10px] font-medium bg-background text-foreground border border-border"
                >
                  <span className="truncate max-w-[150px]">{tag}</span>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleTag(tag);
                    }}
                    className="text-muted-foreground hover:text-foreground hover:bg-muted p-0.5 rounded-xs transition-colors cursor-pointer"
                    aria-label={`Remove tag ${tag}`}
                  >
                    <CloseIcon className="h-2.5 w-2.5 shrink-0" />
                  </button>
                </Badge>
              ))}
            </div>
          ) : null}
          <Command shouldFilter={false}>
            <CommandList>
              {canCreate ? (
                <CommandGroup>
                  <CommandItem value={`create:${queryKey}`} onSelect={createTag}>
                    <PlusIcon aria-hidden className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="truncate">Create "{query}"</span>
                  </CommandItem>
                </CommandGroup>
              ) : null}
              <CommandGroup>
                {filteredOptions.length === 0 && !canCreate ? (
                  <div className="px-2 py-3 text-[11px] text-muted-foreground">
                    {query ? "No matches." : "No tags yet."}
                  </div>
                ) : null}
                {filteredOptions.map((tag) => {
                  const checked = selected.some((item) => item.toLowerCase() === tag.toLowerCase());
                  return (
                    <CommandItem
                      key={tag.toLowerCase()}
                      value={tag}
                      onSelect={() => toggleTag(tag)}
                      className={cn(checked && "bg-primary/10 text-primary")}
                    >
                      <Checkbox
                        checked={checked}
                        aria-hidden
                        tabIndex={-1}
                        className="pointer-events-none size-[18px] [&_[data-slot=checkbox-indicator]_svg]:!text-current"
                      />
                      <span className="truncate">{tag}</span>
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}
