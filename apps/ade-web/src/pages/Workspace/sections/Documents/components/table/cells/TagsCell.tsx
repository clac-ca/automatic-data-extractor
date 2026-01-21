import { useState } from "react";
import { Command as CommandPrimitive } from "cmdk";

import { CloseIcon, PlusIcon, TagIcon } from "@/components/icons";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Faceted,
  FacetedBadgeList,
  FacetedContent,
  FacetedEmpty,
  FacetedGroup,
  FacetedItem,
  FacetedList,
  FacetedTrigger,
} from "@/components/ui/faceted";
import { cn } from "@/lib/utils";

export function TagsCell({
  selected,
  tagOptions,
  onToggle,
  disabled = false,
  className,
}: {
  selected: string[];
  tagOptions: string[];
  onToggle: (tag: string) => void;
  disabled?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const options = tagOptions.map((tag) => ({ label: tag, value: tag }));
  const normalizedQuery = query.trim();
  const normalizedQueryLower = normalizedQuery.toLowerCase();
  const hasExactMatch = tagOptions.some((tag) => tag.toLowerCase() === normalizedQueryLower);
  const hasQueryMatches = normalizedQuery.length > 0
    && tagOptions.some((tag) => tag.toLowerCase().includes(normalizedQueryLower));
  const canCreate = normalizedQuery.length > 0 && !hasExactMatch;
  const shouldCreateOnEnter = canCreate && !hasQueryMatches;
  const emptyLabel = normalizedQuery.length > 0
    ? "No tags found. Press Enter to create."
    : "No tags yet. Type to create.";
  const placeholder = selected.length ? "Type to add tags..." : "Add tags...";

  const handleCreate = () => {
    if (!canCreate || disabled) return;
    onToggle(normalizedQuery);
    setQuery("");
  };

  return (
    <div className={cn("min-w-0", className)} data-ignore-row-click>
      <Faceted
        multiple
        value={selected}
        open={open}
        onOpenChange={(nextOpen) => {
          setOpen(nextOpen);
          if (!nextOpen) {
            setQuery("");
          }
        }}
      >
        <FacetedTrigger asChild>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled}
            className="h-7 min-w-[120px] justify-start gap-2 bg-background px-2 text-[11px]"
          >
            <TagIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <FacetedBadgeList
              options={options}
              placeholder="Add tags"
              max={2}
              className="min-w-0 flex-1"
              badgeClassName="text-[10px]"
            />
          </Button>
        </FacetedTrigger>
        <FacetedContent className="w-64">
          <div className="border-b px-2 py-2">
            <div className="flex flex-wrap items-center gap-1 rounded-md border border-input bg-background px-2 py-1 text-[11px] shadow-xs focus-within:ring-1 focus-within:ring-ring">
              {selected.map((tag) => (
                <Badge key={tag} variant="secondary" className="gap-1 px-1.5 py-0 text-[10px]">
                  <span className="truncate">{tag}</span>
                  <button
                    type="button"
                    className="rounded-sm p-0.5 text-muted-foreground transition hover:text-foreground"
                    onClick={() => {
                      if (!disabled) {
                        onToggle(tag);
                      }
                    }}
                    aria-label={`Remove ${tag}`}
                    disabled={disabled}
                  >
                    <CloseIcon className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
              <CommandPrimitive.Input
                value={query}
                onValueChange={setQuery}
                placeholder={placeholder}
                disabled={disabled}
                autoFocus={!disabled}
                className="min-w-[6ch] flex-1 bg-transparent py-1 text-[11px] outline-none placeholder:text-muted-foreground"
                onKeyDown={(event) => {
                  if (event.key === "Enter" && shouldCreateOnEnter) {
                    event.preventDefault();
                    handleCreate();
                  }
                }}
              />
            </div>
            <div className="mt-1 text-[10px] text-muted-foreground">
              Type to search or create. Press Enter to create.
            </div>
          </div>
          <FacetedList>
            <FacetedEmpty>{emptyLabel}</FacetedEmpty>
            {canCreate ? (
              <FacetedGroup>
                <FacetedItem
                  value={normalizedQuery}
                  disabled={disabled}
                  onSelect={() => {
                    handleCreate();
                  }}
                >
                  <PlusIcon className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="truncate">Create "{normalizedQuery}"</span>
                </FacetedItem>
              </FacetedGroup>
            ) : null}
            {tagOptions.length ? (
              <FacetedGroup>
                {tagOptions.map((tag) => (
                  <FacetedItem
                    key={tag}
                    value={tag}
                    disabled={disabled}
                    onSelect={() => {
                      if (!disabled) {
                        onToggle(tag);
                      }
                    }}
                  >
                    <span className="truncate">{tag}</span>
                  </FacetedItem>
                ))}
              </FacetedGroup>
            ) : null}
          </FacetedList>
        </FacetedContent>
      </Faceted>
    </div>
  );
}
