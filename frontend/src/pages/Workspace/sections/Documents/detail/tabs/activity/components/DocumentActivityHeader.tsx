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
    <div className="border-b border-border bg-background px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold">Activity</div>
          <div className="text-xs text-muted-foreground">
            Notes and processing events for this document.
          </div>
        </div>
        <div className="flex items-center gap-2">
          <FilterChip
            active={filter === "all"}
            onClick={() => onFilterChange("all")}
            label="All"
          />
          <FilterChip
            active={filter === "comments"}
            onClick={() => onFilterChange("comments")}
            label="Discussions"
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
      variant={active ? "secondary" : "outline"}
      className="h-8 text-xs"
      onClick={onClick}
    >
      {label}
    </Button>
  );
}
