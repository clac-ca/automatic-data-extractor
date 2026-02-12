import { Badge } from "@/components/ui/badge";

interface AssignmentChipsProps {
  readonly assignments: readonly string[];
  readonly emptyLabel?: string;
}

export function AssignmentChips({
  assignments,
  emptyLabel = "No assignments",
}: AssignmentChipsProps) {
  if (assignments.length === 0) {
    return <span className="text-xs text-muted-foreground">{emptyLabel}</span>;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {assignments.map((assignment) => (
        <Badge key={assignment} variant="secondary" className="text-xs">
          {assignment}
        </Badge>
      ))}
    </div>
  );
}

