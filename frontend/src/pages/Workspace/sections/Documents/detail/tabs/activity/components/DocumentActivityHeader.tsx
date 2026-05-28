import { Button } from "@/components/ui/button";
import type { DocumentActivityFilter } from "@/pages/Workspace/sections/Documents/shared/navigation";

export function DocumentActivityHeader({
  filter,
  onFilterChange,
}: {
  filter: DocumentActivityFilter;
  onFilterChange: (filter: DocumentActivityFilter) => void;
}) {
  return (
    <div className="border-b border-border bg-background/80 px-4 py-3 backdrop-blur-md">
      <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold">Document chat</div>
          <div className="text-xs text-muted-foreground">
            Ask questions, leave decisions, and review document events in context.
          </div>
        </div>
        <div className="flex items-center gap-1 rounded-full border border-border bg-muted/40 p-1 shadow-sm">
          <FilterChip
            active={filter === "all"}
            onClick={() => onFilterChange("all")}
            label="All"
          />
          <FilterChip
            active={filter === "comments"}
            onClick={() => onFilterChange("comments")}
            label="Messages"
          />
          <FilterChip
            active={filter === "events"}
            onClick={() => onFilterChange("events")}
            label="Events"
          />
        </div>
      </div>
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <Button
      type="button"
      size="sm"
      variant={active ? "secondary" : "ghost"}
      className="h-7 rounded-full px-3 text-xs data-[active=true]:shadow-sm"
      data-active={active ? "true" : undefined}
      onClick={onClick}
    >
      {label}
    </Button>
  );
}
