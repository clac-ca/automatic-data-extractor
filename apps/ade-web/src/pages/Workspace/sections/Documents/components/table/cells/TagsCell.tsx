import * as React from "react";

import { TagIcon } from "@/components/icons";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { TagSelector } from "../../../ui/tag-selector";

export function TagsCell({
  selected,
  tagOptions,
  onToggle,
  disabled = false,
  className,

  // Optional: allows fixing bug #2 (shared options update + persistence)
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
  const primaryTag = selected[0] ?? "";
  const overflowCount = Math.max(selected.length - 1, 0);

  // Adapter: TagSelector works with the full array, but your table cell API toggles one tag.
  const handleValueChange = React.useCallback(
    (next: string[]) => {
      const removed = selected.find((t) => !next.includes(t));
      const added = next.find((t) => !selected.includes(t));
      const changed = added ?? removed;
      if (changed) onToggle(changed);
    },
    [onToggle, selected]
  );

  return (
    <div className={cn("min-w-0", className)} data-ignore-row-click>
      <TagSelector
        value={selected}
        onValueChange={handleValueChange}
        options={tagOptions}
        onOptionsChange={onTagOptionsChange}
        onCreate={onCreateTag}
        disabled={disabled}
        allowCreate
        placeholder={selected.length ? "Search or create tags…" : "Add tags…"}
        emptyText={(q) => (q ? "No matches." : "No tags yet.")}
        keepOpenOnSelect
      >
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          className="h-7 min-w-[120px] justify-start gap-2 bg-background px-2 text-[11px]"
          aria-label="Edit tags"
        >
          <TagIcon aria-hidden className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />

          <span className="flex min-w-0 flex-1 items-center gap-1 overflow-hidden">
            {selected.length === 0 ? (
              <span className="truncate text-muted-foreground">Add tags</span>
            ) : (
              <>
                <Badge
                  variant="secondary"
                  className="min-w-0 max-w-[120px] px-1.5 py-0 text-[10px]"
                  title={primaryTag}
                >
                  <span className="min-w-0 truncate">{primaryTag}</span>
                </Badge>

                {overflowCount > 0 ? (
                  <Badge
                    variant="secondary"
                    className="shrink-0 px-1.5 py-0 text-[10px]"
                    aria-label={`${overflowCount} more tags`}
                  >
                    +{overflowCount}
                  </Badge>
                ) : null}
              </>
            )}
          </span>
        </Button>
      </TagSelector>
    </div>
  );
}
