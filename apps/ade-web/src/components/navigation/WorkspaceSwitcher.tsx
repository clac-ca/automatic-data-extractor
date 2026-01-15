import { useState } from "react";

import { useNavigate } from "react-router-dom";

import { getDefaultWorkspacePath } from "@/navigation/workspacePaths";
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
import { SidebarMenu, SidebarMenuButton, SidebarMenuItem, useSidebar } from "@/components/ui/sidebar";
import { CheckIcon, ChevronDownIcon, ChevronRightIcon } from "@/components/icons";
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { writePreferredWorkspaceId } from "@/lib/workspacePreferences";

interface WorkspaceSwitcherProps {
  readonly onNavigate?: () => void;
}

export function WorkspaceSwitcher({ onNavigate }: WorkspaceSwitcherProps) {
  const { workspace, workspaces } = useWorkspaceContext();
  const { state } = useSidebar();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const label = `Switch workspace: ${workspace.name}`;
  const popoverSide = state === "collapsed" ? "right" : "bottom";
  const popoverOffset = state === "collapsed" ? 12 : 8;
  const popoverWidthClass =
    state === "collapsed"
      ? "w-[min(22rem,80vw)]"
      : "w-[min(22rem,80vw)] sm:w-[--radix-popper-anchor-width]";

  const handleSelectWorkspace = (workspaceId: string) => {
    setOpen(false);
    onNavigate?.();
    if (workspaceId === workspace.id) return;
    writePreferredWorkspaceId(workspaceId);
    navigate(getDefaultWorkspacePath(workspaceId));
  };

  const handleManageWorkspaces = () => {
    setOpen(false);
    onNavigate?.();
    navigate("/workspaces");
  };

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <SidebarMenuButton
              tooltip={label}
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-md bg-sidebar-primary text-[0.6rem] font-semibold uppercase text-sidebar-primary-foreground group-data-[collapsible=icon]:h-6 group-data-[collapsible=icon]:w-6">
                {getWorkspaceInitials(workspace.name)}
              </span>
              <span className="flex min-w-0 flex-1 flex-col group-data-[collapsible=icon]:hidden">
                <span className="truncate text-sm font-semibold">{workspace.name}</span>
                <span className="truncate text-xs text-sidebar-foreground/60">Switch workspace</span>
              </span>
              <ChevronDownIcon className="ml-auto h-4 w-4 text-sidebar-foreground/70 group-data-[collapsible=icon]:hidden" />
            </SidebarMenuButton>
          </PopoverTrigger>
          <PopoverContent side={popoverSide} align="start" sideOffset={popoverOffset} className={`${popoverWidthClass} p-0`}>
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
      </SidebarMenuItem>
    </SidebarMenu>
  );
}

function getWorkspaceInitials(name: string) {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return "WS";
  const initials = parts.slice(0, 2).map((part) => part[0] ?? "");
  return initials.join("").toUpperCase();
}
