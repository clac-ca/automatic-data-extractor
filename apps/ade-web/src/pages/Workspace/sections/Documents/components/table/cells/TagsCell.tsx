import { TagIcon } from "@/components/icons";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
  const label = selected.length
    ? selected.length > 2
      ? `${selected.slice(0, 2).join(", ")} +${selected.length - 2}`
      : selected.join(", ")
    : "Add tags";

  return (
    <div className={cn("min-w-0", className)} data-ignore-row-click>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled}
            className="h-7 min-w-[120px] justify-between gap-2 bg-background px-2 text-[11px]"
          >
            <span className="flex min-w-0 items-center gap-2">
              <TagIcon className="h-3.5 w-3.5 text-muted-foreground" />
              <span className={cn("truncate", selected.length ? "text-foreground" : "text-muted-foreground")}>
                {label}
              </span>
            </span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          {tagOptions.length === 0 ? (
            <div className="px-2 py-1.5 text-xs text-muted-foreground">No tags available</div>
          ) : (
            tagOptions.map((tag) => (
              <DropdownMenuCheckboxItem
                key={tag}
                checked={selected.includes(tag)}
                onCheckedChange={() => onToggle(tag)}
              >
                {tag}
              </DropdownMenuCheckboxItem>
            ))
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
