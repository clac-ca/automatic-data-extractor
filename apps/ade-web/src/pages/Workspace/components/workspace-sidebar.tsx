import { useCallback, useState, type ComponentType, type SVGProps } from "react";
import { NavLink, generatePath, matchPath, useLocation, useNavigate } from "react-router-dom";

import type { WorkspaceProfile } from "@/types/workspaces";
import {
  CheckIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ConfigureIcon,
  DocumentIcon,
  GearIcon,
  RunsIcon,
} from "@/components/icons";
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { writePreferredWorkspaceId } from "@/lib/workspacePreferences";
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
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar";

type WorkspaceSectionId = "documents" | "runs" | "config-builder" | "settings";

interface WorkspaceSectionDescriptor {
  readonly id: WorkspaceSectionId;
  readonly path: string;
  readonly label: string;
  readonly icon: ComponentType<SVGProps<SVGSVGElement>>;
  readonly matchPrefix?: boolean;
}

const DEFAULT_WORKSPACE_SECTION_PATH = "documents";

const workspaceSections: readonly WorkspaceSectionDescriptor[] = [
  {
    id: "documents",
    path: DEFAULT_WORKSPACE_SECTION_PATH,
    label: "Documents",
    icon: DocumentIcon,
  },
  {
    id: "runs",
    path: "runs",
    label: "Runs",
    icon: RunsIcon,
  },
  {
    id: "config-builder",
    path: "config-builder",
    label: "Config Builder",
    icon: ConfigureIcon,
  },
  {
    id: "settings",
    path: "settings",
    label: "Workspace Settings",
    icon: GearIcon,
    matchPrefix: true,
  },
] as const;

export const defaultWorkspaceSection = workspaceSections[0];

export interface WorkspaceNavigationItem {
  readonly id: WorkspaceSectionId;
  readonly label: string;
  readonly href: string;
  readonly icon: ComponentType<SVGProps<SVGSVGElement>>;
  readonly matchPrefix?: boolean;
}

export function getWorkspacePrimaryNavigation(workspace: WorkspaceProfile): WorkspaceNavigationItem[] {
  return workspaceSections.map((section) => ({
    id: section.id,
    label: section.label,
    href: generatePath("/workspaces/:workspaceId/:section", {
      workspaceId: workspace.id,
      section: section.path,
    }),
    icon: section.icon,
    matchPrefix: section.matchPrefix,
  }));
}

interface WorkspaceSidebarProps {
  readonly items: readonly WorkspaceNavigationItem[];
}

export function WorkspaceSidebar({ items }: WorkspaceSidebarProps) {
  const { isMobile, setOpenMobile } = useSidebar();

  const settingsItem = findSettingsItem(items);
  const mainItems = settingsItem ? items.filter((item) => item.id !== settingsItem.id) : items;

  const handleNavigate = useCallback(() => {
    if (isMobile) {
      setOpenMobile(false);
    }
  }, [isMobile, setOpenMobile]);

  const sidebarContent = (
    <>
      <SidebarHeader className="min-h-[var(--topbar-height)] justify-center px-2 py-0">
        <WorkspaceSelector onNavigate={handleNavigate} />
      </SidebarHeader>
      <SidebarSeparator />
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Workspace</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {mainItems.map((item) => (
                <SidebarNavItem key={item.id} item={item} onNavigate={handleNavigate} />
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarSeparator />
      <SidebarFooter>
        <SidebarMenu>
          {settingsItem ? <SidebarNavItem item={settingsItem} onNavigate={handleNavigate} /> : null}
        </SidebarMenu>
      </SidebarFooter>
    </>
  );

  return (
    <Sidebar collapsible="icon" variant="sidebar" aria-label="Workspace navigation">
      {sidebarContent}
    </Sidebar>
  );
}

function SidebarNavItem({
  item,
  onNavigate,
}: {
  readonly item: WorkspaceNavigationItem;
  readonly onNavigate?: () => void;
}) {
  const location = useLocation();
  const isActive = Boolean(
    matchPath({ path: item.href, end: !(item.matchPrefix ?? false) }, location.pathname),
  );

  return (
    <SidebarMenuItem>
      <SidebarMenuButton asChild isActive={isActive} tooltip={item.label}>
        <NavLink
          to={item.href}
          end={!(item.matchPrefix ?? false)}
          onClick={(event) => {
            if (
              isPlainLeftClick(event) &&
              (event.currentTarget as HTMLElement).getAttribute("aria-current") === "page"
            ) {
              event.preventDefault();
              return;
            }
            onNavigate?.();
          }}
        >
          <item.icon />
          <span className="group-data-[collapsible=icon]:hidden">{item.label}</span>
        </NavLink>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
}

function WorkspaceSelector({ onNavigate }: { readonly onNavigate?: () => void }) {
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
      : "w-[min(22rem,80vw)] sm:w-[var(--radix-popper-anchor-width)]";

  const handleSelectWorkspace = (workspaceId: string) => {
    setOpen(false);
    onNavigate?.();
    if (workspaceId === workspace.id) return;
    writePreferredWorkspaceId(workspaceId);
    navigate(generatePath("/workspaces/:workspaceId/documents", { workspaceId }));
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
              size="lg"
              tooltip={label}
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-md bg-sidebar-primary text-[0.6rem] font-semibold uppercase text-sidebar-primary-foreground">
                {getWorkspaceInitials(workspace.name)}
              </span>
              <span className="flex min-w-0 flex-1 flex-col group-data-[collapsible=icon]:hidden">
                <span className="truncate text-sm font-semibold">{workspace.name}</span>
                <span className="truncate text-xs text-sidebar-foreground/60">Switch workspace</span>
              </span>
              <ChevronDownIcon className="ml-auto h-4 w-4 text-sidebar-foreground/70 group-data-[collapsible=icon]:hidden" />
            </SidebarMenuButton>
          </PopoverTrigger>
          <PopoverContent
            side={popoverSide}
            align="start"
            sideOffset={popoverOffset}
            className={`${popoverWidthClass} p-0`}
          >
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
                        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-[0.6rem] font-semibold uppercase text-primary">
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
                    <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-muted text-muted-foreground">
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

function isPlainLeftClick(event: React.MouseEvent) {
  return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.altKey && !event.shiftKey;
}

function findSettingsItem(items: readonly WorkspaceNavigationItem[]) {
  const exactIds = new Set(["settings", "workspace-settings", "workspacesettings", "preferences"]);

  const byExactId = items.find((item) => exactIds.has(item.id.toLowerCase()));
  if (byExactId) return byExactId;

  const byIdIncludes = items.find((item) => item.id.toLowerCase().includes("settings"));
  if (byIdIncludes) return byIdIncludes;

  const byHref = items.find((item) => /settings|preferences/i.test(item.href));
  if (byHref) return byHref;

  const byLabel = items.find((item) => /settings|preferences/i.test(item.label));
  return byLabel;
}
