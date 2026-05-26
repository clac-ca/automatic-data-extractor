import * as React from "react";

import { ChevronUpDownIcon, SearchIcon, UserIcon } from "@/components/icons";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Command, CommandGroup, CommandItem, CommandList } from "@/components/ui/command";
import { Input } from "@/components/ui/input";
import { Popover, PopoverAnchor, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
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
  const [open, setOpen] = React.useState(false);
  const [search, setSearch] = React.useState("");
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const anchorRef = React.useRef<HTMLDivElement | null>(null);
  const selectedPerson = people.find((person) => person.id === assigneeId) ?? null;
  const label = selectedPerson?.label ?? "Unassigned";
  const initials = selectedPerson
    ? getInitials(selectedPerson.label, selectedPerson.email)
    : null;

  React.useEffect(() => {
    if (!open) {
      setSearch("");
      return;
    }
    requestAnimationFrame(() => inputRef.current?.focus());
  }, [open]);

  const filteredPeople = React.useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return people;
    return people.filter((person) =>
      [person.label, person.email].some((value) => value?.toLowerCase().includes(query)),
    );
  }, [people, search]);

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

  const selectAndClose = (next?: string) => {
    handleValueChange(next);
    setOpen(false);
  };

  return (
    <div className={cn("w-[180px]", className)} data-row-interactive data-ignore-row-click>
      <Popover open={open} onOpenChange={(next) => !disabled && setOpen(next)}>
        {open ? (
          <PopoverAnchor asChild>
            <div
              ref={anchorRef}
              className="flex h-7 w-[180px] items-center gap-2 rounded-md border border-border/70 bg-background px-2 text-[11px] shadow-xs"
              data-row-interactive
            >
              <SearchIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              <Input
                ref={inputRef}
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    event.preventDefault();
                    setOpen(false);
                  }
                }}
                placeholder="Search people..."
                className="h-auto min-w-0 flex-1 border-0 bg-transparent p-0 text-[11px] font-normal shadow-none focus-visible:ring-0"
                disabled={disabled}
              />
            </div>
          </PopoverAnchor>
        ) : (
          <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled}
            className="h-7 w-[180px] justify-start gap-2 rounded-md border-border/70 bg-background px-2 text-[11px] font-medium shadow-xs hover:border-ring/50 hover:bg-background"
            data-row-interactive
          >
            <span className="flex min-w-0 flex-1 items-center gap-2">
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
          </PopoverTrigger>
        )}
        <PopoverContent
          align="start"
          className="w-56 p-0"
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
          <Command shouldFilter={false}>
            <CommandList>
              <CommandGroup>
              {currentUserId ? (
                <CommandItem value="assign-to-me" disabled={disabled} onSelect={() => selectAndClose("assign-to-me")}>
                  <Checkbox
                    checked={false}
                    aria-hidden
                    tabIndex={-1}
                    className="pointer-events-none size-[18px] [&_[data-slot=checkbox-indicator]_svg]:!text-current"
                  />
                  <UserIcon className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="truncate">Assign to me</span>
                </CommandItem>
              ) : null}
              <CommandItem value="unassigned" disabled={disabled} onSelect={() => selectAndClose("unassigned")}>
                <Checkbox
                  checked={assigneeId === null}
                  aria-hidden
                  tabIndex={-1}
                  className="pointer-events-none size-[18px] [&_[data-slot=checkbox-indicator]_svg]:!text-current"
                />
                <UserIcon className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="truncate">Unassigned</span>
              </CommandItem>
              {filteredPeople.length === 0 ? (
                <div className="px-2 py-3 text-[11px] text-muted-foreground">No people found.</div>
              ) : null}
              {filteredPeople.map((person) => (
                <CommandItem
                  key={person.id}
                  value={person.id}
                  disabled={disabled}
                  onSelect={() => selectAndClose(person.id)}
                  className={cn(assigneeId === person.id && "bg-primary/10 text-primary")}
                >
                  <Checkbox
                    checked={assigneeId === person.id}
                    aria-hidden
                    tabIndex={-1}
                    className="pointer-events-none size-[18px] [&_[data-slot=checkbox-indicator]_svg]:!text-current"
                  />
                  <Avatar className="h-5 w-5">
                    <AvatarFallback className="text-[10px] font-semibold text-foreground">
                      {getInitials(person.label, person.email)}
                    </AvatarFallback>
                  </Avatar>
                  <span className="min-w-0 truncate">{person.label}</span>
                </CommandItem>
              ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}
