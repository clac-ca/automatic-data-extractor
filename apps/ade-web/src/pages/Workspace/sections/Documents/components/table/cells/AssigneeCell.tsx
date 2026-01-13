import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

import type { WorkspacePerson } from "../../../types";

export function AssigneeCell({
  assigneeId,
  people,
  onAssign,
  disabled = false,
  className,
}: {
  assigneeId: string | null;
  people: WorkspacePerson[];
  onAssign: (next: string | null) => void;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("min-w-[140px]", className)} data-ignore-row-click>
      <Select
        value={assigneeId ?? "unassigned"}
        onValueChange={(value) => onAssign(value === "unassigned" ? null : value)}
        disabled={disabled}
      >
        <SelectTrigger className="h-7 bg-background px-2 text-[11px]">
          <SelectValue placeholder="Unassigned" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="unassigned">Unassigned</SelectItem>
          {people.map((person) => (
            <SelectItem key={person.id} value={person.id}>
              {person.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
