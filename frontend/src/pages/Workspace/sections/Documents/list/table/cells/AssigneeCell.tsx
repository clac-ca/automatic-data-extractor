import { ChevronUpDownIcon, UserIcon } from "@/components/icons";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  Faceted,
  FacetedContent,
  FacetedEmpty,
  FacetedGroup,
  FacetedInput,
  FacetedItem,
  FacetedList,
  FacetedTrigger,
} from "@/components/ui/faceted";
import { getInitials } from "@/lib/format";
import { cn } from "@/lib/utils";

import type { WorkspacePerson } from "../../../shared/types";

export function AssigneeCell({
  assigneeId,
  people,
  currentUserId,
  onAssign,
  disabled = false,
  className,
}: {
  assigneeId: string | null;
  people: WorkspacePerson[];
  currentUserId?: string;
  onAssign: (next: string | null) => void;
  disabled?: boolean;
  className?: string;
}) {
  const selectedPerson = people.find((person) => person.id === assigneeId) ?? null;
  const label = selectedPerson?.label ?? "Unassigned";
  const initials = selectedPerson
    ? getInitials(selectedPerson.label, selectedPerson.email)
    : null;
  const value = assigneeId ?? "unassigned";

  const handleValueChange = (next?: string) => {
    if (!next || next === "unassigned") {
      if (assigneeId !== null) {
        onAssign(null);
      }
      return;
    }

    if (next === "assign-to-me" && currentUserId) {
      if (assigneeId !== currentUserId) {
        onAssign(currentUserId);
      }
      return;
    }

    if (next !== assigneeId) {
      onAssign(next);
    }
  };

  return (
    <div className={cn("min-w-[140px]", className)} data-row-interactive data-ignore-row-click>
      <Faceted value={value} onValueChange={handleValueChange}>
        <FacetedTrigger asChild>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled}
            className="h-7 min-w-[140px] justify-between gap-2 bg-background px-2 text-[11px]"
            data-row-interactive
          >
            <span className="flex min-w-0 items-center gap-2">
              {selectedPerson ? (
                <Avatar className="h-5 w-5">
                  <AvatarFallback className="text-[10px] font-semibold text-foreground">
                    {initials}
                  </AvatarFallback>
                </Avatar>
              ) : (
                <UserIcon className="h-3.5 w-3.5 text-muted-foreground" />
              )}
              <span className={cn("min-w-0 truncate", selectedPerson ? "text-foreground" : "text-muted-foreground")}>
                {label}
              </span>
            </span>
            <ChevronUpDownIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          </Button>
        </FacetedTrigger>
        <FacetedContent
          className="w-56"
          data-row-interactive
          onPointerDownCapture={(event) => {
            event.stopPropagation();
          }}
        >
          <FacetedInput placeholder="Search people..." disabled={disabled} />
          <FacetedList>
            <FacetedEmpty>No people found.</FacetedEmpty>
            <FacetedGroup>
              {currentUserId ? (
                <FacetedItem value="assign-to-me" disabled={disabled}>
                  <UserIcon className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="truncate">Assign to me</span>
                </FacetedItem>
              ) : null}
              <FacetedItem value="unassigned" disabled={disabled}>
                <UserIcon className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="truncate">Unassigned</span>
              </FacetedItem>
              {people.map((person) => (
                <FacetedItem key={person.id} value={person.id} disabled={disabled}>
                  <Avatar className="h-5 w-5">
                    <AvatarFallback className="text-[10px] font-semibold text-foreground">
                      {getInitials(person.label, person.email)}
                    </AvatarFallback>
                  </Avatar>
                  <span className="min-w-0 truncate">{person.label}</span>
                </FacetedItem>
              ))}
            </FacetedGroup>
          </FacetedList>
        </FacetedContent>
      </Faceted>
    </div>
  );
}
