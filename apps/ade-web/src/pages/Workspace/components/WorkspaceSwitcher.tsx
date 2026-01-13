import { useState } from "react";
import clsx from "clsx";

import { useNavigate } from "react-router-dom";
import { getDefaultWorkspacePath } from "@app/navigation/workspacePaths";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  CheckIcon,
  ChevronDownIcon,
  ChevronDownSmallIcon,
  ChevronRightIcon,
} from "@components/icons";
import { useWorkspaceContext } from "@pages/Workspace/context/WorkspaceContext";
import { writePreferredWorkspaceId } from "@lib/workspacePreferences";

type WorkspaceSwitcherVariant = "rail" | "drawer";
type WorkspaceSwitcherDensity = "default" | "compact";

interface WorkspaceSwitcherProps {
  readonly variant?: WorkspaceSwitcherVariant;
  readonly density?: WorkspaceSwitcherDensity;
  readonly showLabel?: boolean;
  readonly onNavigate?: () => void;
  readonly onOpenChange?: (open: boolean) => void;
  readonly className?: string;
}

export function WorkspaceSwitcher({
  variant = "drawer",
  density = "default",
  showLabel,
  onNavigate,
  onOpenChange,
  className,
}: WorkspaceSwitcherProps) {
  const { workspace, workspaces } = useWorkspaceContext();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const isRail = variant === "rail";
  const isCompact = density === "compact";
  const displayLabel = !isCompact && (showLabel ?? !isRail);
  const label = `Switch workspace: ${workspace.name}`;

  const setPopoverOpen = (nextOpen: boolean) => {
    setOpen(nextOpen);
    onOpenChange?.(nextOpen);
  };

  const handleSelectWorkspace = (workspaceId: string) => {
    setPopoverOpen(false);
    onNavigate?.();
    if (workspaceId === workspace.id) return;
    writePreferredWorkspaceId(workspaceId);
    navigate(getDefaultWorkspacePath(workspaceId));
  };

  const handleManageWorkspaces = () => {
    setPopoverOpen(false);
    onNavigate?.();
    navigate("/workspaces");
  };

  const popoverSide = isRail ? "right" : "bottom";
  const popoverOffset = isRail ? 12 : 8;

  return (
    <div
      className={clsx(
        "flex",
        isCompact ? "w-full" : "flex-col gap-2",
        isRail && !isCompact && "items-center",
        className,
      )}
    >
      {displayLabel ? (
        <span className="px-2 text-[0.63rem] font-semibold uppercase tracking-[0.4em] text-sidebar-foreground">
          Workspace
        </span>
      ) : null}
      <Popover open={open} onOpenChange={setPopoverOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-label={label}
            title={label}
            className={clsx(
              "group relative flex items-center rounded-xl text-sidebar-foreground",
              "transition-colors duration-150 motion-reduce:transition-none",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar",
              "data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground",
              isRail
                ? "h-11 w-11 justify-center bg-sidebar-accent/70 hover:bg-sidebar-accent"
                : isCompact
                  ? "h-[var(--app-shell-control-h)] w-full gap-3 border border-sidebar-border/60 bg-sidebar/60 px-2.5 py-0 hover:border-sidebar-border hover:bg-sidebar-accent/80 hover:text-sidebar-accent-foreground"
                  : "w-full gap-3 border border-sidebar-border/60 bg-sidebar/60 px-2.5 py-2 hover:border-sidebar-border hover:bg-sidebar-accent/80 hover:text-sidebar-accent-foreground",
            )}
          >
            <span
              className={clsx(
                "flex items-center justify-center bg-primary text-xs font-semibold uppercase text-primary-foreground shadow-sm",
                isCompact ? "h-8 w-8 rounded-lg" : "h-10 w-10 rounded-xl",
              )}
            >
              {getWorkspaceInitials(workspace.name)}
            </span>
            {isRail ? null : isCompact ? (
              <span className="flex min-w-0 flex-1 items-center">
                <span className="truncate text-sm font-semibold">{workspace.name}</span>
              </span>
            ) : (
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-sm font-semibold">{workspace.name}</span>
                <span className="truncate text-xs text-sidebar-foreground/70 group-hover:text-sidebar-accent-foreground/80 group-data-[state=open]:text-sidebar-accent-foreground/80">
                  Switch workspace
                </span>
              </span>
            )}
            {isRail ? (
              <span className="absolute bottom-1 right-1 inline-flex h-4 w-4 items-center justify-center rounded-full bg-sidebar text-sidebar-foreground shadow-sm">
                <ChevronDownSmallIcon className="h-3 w-3" />
              </span>
            ) : (
              <ChevronDownIcon className="ml-auto h-4 w-4 text-sidebar-foreground/70 group-hover:text-sidebar-accent-foreground group-data-[state=open]:text-sidebar-accent-foreground" />
            )}
          </button>
        </PopoverTrigger>
        <PopoverContent side={popoverSide} align="start" sideOffset={popoverOffset} className="w-[min(22rem,80vw)] p-0">
          <Command loop>
            <CommandInput placeholder="Search workspaces..." autoFocus />
            <CommandList>
              <CommandEmpty>No workspaces found.</CommandEmpty>
              <CommandGroup heading="Workspaces">
                {workspaces.map((entry) => {
                  const isActive = entry.id === workspace.id;
                  const secondaryLabel = entry.slug ?? entry.id;
                  return (
                    <CommandItem
                      key={entry.id}
                      value={`${entry.name} ${secondaryLabel}`}
                      onSelect={() => handleSelectWorkspace(entry.id)}
                      className="gap-3"
                    >
                      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-[0.6rem] font-semibold uppercase text-primary">
                        {getWorkspaceInitials(entry.name)}
                      </span>
                      <span className="flex min-w-0 flex-1 flex-col">
                        <span className="truncate text-sm font-medium">{entry.name}</span>
                        <span className="truncate text-xs text-muted-foreground">{secondaryLabel}</span>
                      </span>
                      {isActive ? <CheckIcon className="h-4 w-4 text-primary" /> : null}
                    </CommandItem>
                  );
                })}
              </CommandGroup>
              <CommandSeparator />
              <CommandGroup>
                <CommandItem value="Manage workspaces" onSelect={handleManageWorkspaces} className="gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                    <ChevronRightIcon className="h-4 w-4" />
                  </span>
                  <span className="flex-1 text-sm font-medium">All workspaces</span>
                </CommandItem>
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}

function getWorkspaceInitials(name: string) {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return "WS";
  const initials = parts.slice(0, 2).map((part) => part[0] ?? "");
  return initials.join("").toUpperCase();
}
