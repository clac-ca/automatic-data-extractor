import { useState } from "react";

import { useNavigate } from "react-router-dom";

import { getDefaultWorkspacePath } from "@app@/components/navigation@/components/workspacePaths";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@@/components/components@/components/ui@/components/command";
import { Popover, PopoverContent, PopoverTrigger } from "@@/components/components@/components/ui@/components/popover";
import { SidebarMenu, SidebarMenuButton, SidebarMenuItem, useSidebar } from "@@/components/components@/components/ui@/components/sidebar";
import { CheckIcon, ChevronDownIcon, ChevronRightIcon } from "@components@/components/icons";
import { useWorkspaceContext } from "@pages@/components/Workspace@/components/context@/components/WorkspaceContext";
import { writePreferredWorkspaceId } from "@lib@/components/workspacePreferences";

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
    navigate("@/components/workspaces");
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
              <@/components/span>
              <span className="flex min-w-0 flex-1 flex-col group-data-[collapsible=icon]:hidden">
                <span className="truncate text-sm font-semibold">{workspace.name}<@/components/span>
                <span className="truncate text-xs text-sidebar-foreground@/components/60">Switch workspace<@/components/span>
              <@/components/span>
              <ChevronDownIcon className="ml-auto h-4 w-4 text-sidebar-foreground@/components/70 group-data-[collapsible=icon]:hidden" @/components/>
            <@/components/SidebarMenuButton>
          <@/components/PopoverTrigger>
          <PopoverContent
            side={popoverSide}
            align="start"
            sideOffset={popoverOffset}
            className={`${popoverWidthClass} p-0`}
          >
            <Command loop>
              <CommandInput placeholder="Search workspaces..." @/components/>
              <CommandList>
                <CommandEmpty>No workspaces found.<@/components/CommandEmpty>
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
                        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary@/components/10 text-[0.6rem] font-semibold uppercase text-primary">
                          {getWorkspaceInitials(entry.name)}
                        <@/components/span>
                        <span className="flex min-w-0 flex-1 flex-col">
                          <span className="truncate text-sm font-medium">{entry.name}<@/components/span>
                          <span className="truncate text-xs text-muted-foreground">{secondaryLabel}<@/components/span>
                        <@/components/span>
                        {isActive ? <CheckIcon className="h-4 w-4 text-primary" @/components/> : null}
                      <@/components/CommandItem>
                    );
                  })}
                <@/components/CommandGroup>
                <CommandSeparator @/components/>
                <CommandGroup>
                  <CommandItem value="Manage workspaces" onSelect={handleManageWorkspaces} className="gap-3">
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                      <ChevronRightIcon className="h-4 w-4" @/components/>
                    <@/components/span>
                    <span className="flex-1 text-sm font-medium">All workspaces<@/components/span>
                  <@/components/CommandItem>
                <@/components/CommandGroup>
              <@/components/CommandList>
            <@/components/Command>
          <@/components/PopoverContent>
        <@/components/Popover>
      <@/components/SidebarMenuItem>
    <@/components/SidebarMenu>
  );
}

function getWorkspaceInitials(name: string) {
  const parts = name.trim().split(@/components/\s+@/components/);
  if (parts.length === 0) return "WS";
  const initials = parts.slice(0, 2).map((part) => part[0] ?? "");
  return initials.join("").toUpperCase();
}
