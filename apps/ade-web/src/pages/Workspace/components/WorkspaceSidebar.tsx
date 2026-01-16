import { useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { Check, ChevronsUpDown, FileText, LayoutGrid, PlayCircle, Settings, Wrench } from "lucide-react";

import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
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
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";

export function WorkspaceSidebar() {
  const { workspace, workspaces } = useWorkspaceContext();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [switcherOpen, setSwitcherOpen] = useState(false);

  const base = `/workspaces/${workspace.id}`;
  const workspaceLabel = workspace.name?.trim() || "Workspace";
  const workspaceSubpath = pathname.split("/").slice(3).join("/");

  const links = {
    documents: `${base}/documents`,
    runs: `${base}/runs`,
    configBuilder: `${base}/config-builder`,
    settings: `${base}/settings`,
  } as const;

  const isActive = (link: string) => pathname === link || pathname.startsWith(`${link}/`);
  const initials = (value: string) =>
    value
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((word) => word[0])
      .join("")
      .toUpperCase();

  return (
    <Sidebar collapsible="icon" className="group-data-[collapsible=icon]:z-50">
      <SidebarHeader>
        <div className="flex items-start gap-2">
          <SidebarMenu className="flex-1">
            <SidebarMenuItem>
              <Popover open={switcherOpen} onOpenChange={setSwitcherOpen}>
                <PopoverTrigger asChild>
                  <SidebarMenuButton
                    type="button"
                    size="lg"
                    className="h-auto w-full justify-between bg-sidebar-accent/40"
                    tooltip={workspaceLabel}
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <span className="flex size-8 items-center justify-center rounded-md bg-sidebar-accent text-xs font-semibold uppercase text-sidebar-foreground">
                        {initials(workspaceLabel)}
                      </span>
                      <span className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden">
                        <span className="block truncate text-sm font-semibold">{workspaceLabel}</span>
                        <span className="block truncate text-xs text-sidebar-foreground/70">
                          {workspace.slug}
                        </span>
                      </span>
                    </span>
                    <ChevronsUpDown className="size-4 opacity-60 group-data-[collapsible=icon]:hidden" />
                  </SidebarMenuButton>
                </PopoverTrigger>
                <PopoverContent
                  side="right"
                  align="start"
                  className="w-(--radix-popover-trigger-width) p-0"
                >
                  <Command>
                    <CommandInput placeholder="Search workspaces..." />
                    <CommandList>
                      <CommandEmpty>No workspaces found.</CommandEmpty>
                      <CommandGroup heading="Workspaces">
                        {workspaces.map((item) => (
                          <CommandItem
                            key={item.id}
                            value={`${item.name} ${item.slug}`}
                            onSelect={() => {
                              const nextPath = workspaceSubpath
                                ? `/workspaces/${item.id}/${workspaceSubpath}`
                                : `/workspaces/${item.id}`;
                              navigate(nextPath);
                              setSwitcherOpen(false);
                            }}
                          >
                            <span className="flex size-7 items-center justify-center rounded-md bg-sidebar-accent text-[11px] font-semibold uppercase text-sidebar-foreground">
                              {initials(item.name || "Workspace")}
                            </span>
                            <span className="min-w-0 flex-1 truncate">
                              {item.name || "Workspace"}
                            </span>
                            <Check
                              className={cn(
                                "ml-auto size-4 text-foreground",
                                item.id === workspace.id ? "opacity-100" : "opacity-0",
                              )}
                            />
                          </CommandItem>
                        ))}
                      </CommandGroup>
                      <CommandSeparator />
                      <CommandGroup heading="Actions">
                        <CommandItem
                          value="View all workspaces"
                          onSelect={() => {
                            navigate("/workspaces");
                            setSwitcherOpen(false);
                          }}
                        >
                          <LayoutGrid />
                          <span>View all workspaces</span>
                        </CommandItem>
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </SidebarMenuItem>
          </SidebarMenu>
          <SidebarTrigger
            className="mt-1 shrink-0 transition-transform duration-200 ease-linear group-data-[collapsible=icon]:translate-x-[calc(100%+theme(spacing.4))]"
          />
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Workspace</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={isActive(links.documents)}>
                  <NavLink to={links.documents}>
                    <FileText />
                    <span>Documents</span>
                  </NavLink>
                </SidebarMenuButton>
              </SidebarMenuItem>

              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={isActive(links.runs)}>
                  <NavLink to={links.runs}>
                    <PlayCircle />
                    <span>Runs</span>
                  </NavLink>
                </SidebarMenuButton>
              </SidebarMenuItem>

              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={isActive(links.configBuilder)}>
                  <NavLink to={links.configBuilder}>
                    <Wrench />
                    <span>Config Builder</span>
                  </NavLink>
                </SidebarMenuButton>
              </SidebarMenuItem>

              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={isActive(links.settings)}>
                  <NavLink to={links.settings}>
                    <Settings />
                    <span>Workspace Settings</span>
                  </NavLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
