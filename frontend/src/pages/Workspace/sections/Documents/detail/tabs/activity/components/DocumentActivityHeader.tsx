import { Button } from "@/components/ui/button";
import type { DocumentActivityFilter } from "@/pages/Workspace/sections/Documents/shared/navigation";

export function DocumentActivityHeader({
  filter,
  counts,
  onFilterChange,
}: {
  filter: DocumentActivityFilter;
  counts: { all: number; comments: number; events: number };
  onFilterChange: (filter: DocumentActivityFilter) => void;
}) {
  return (
    <div className="border-b border-border bg-background px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold">Activity</div>
          <div className="text-xs text-muted-foreground">
            Collaboration thread and processing history for this document.
          </div>
        </div>
        <div className="flex items-center gap-2">
          <FilterChip
            active={filter === "all"}
            onClick={() => onFilterChange("all")}
            label={`All (${counts.all})`}
          />
          <FilterChip
            active={filter === "comments"}
            onClick={() => onFilterChange("comments")}
            label={`Comments (${counts.comments})`}
          />
          <FilterChip
            active={filter === "events"}
            onClick={() => onFilterChange("events")}
            label={`Events (${counts.events})`}
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
      variant={active ? "secondary" : "outline"}
      className="h-8 text-xs"
      onClick={onClick}
    >
      {label}
    </Button>
  );
}
