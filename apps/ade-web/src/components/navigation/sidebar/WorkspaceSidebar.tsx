import { useCallback } from "react";
import { NavLink, matchPath, useLocation } from "react-router-dom";
import clsx from "clsx";

import {
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
  SidebarRail,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { WorkspaceSwitcher } from "@/components/navigation/sidebar/WorkspaceSwitcher";
import type { WorkspaceNavigationItem } from "@/pages/Workspace/components/workspaceNavigation";

interface WorkspaceSidebarProps {
  readonly items: readonly WorkspaceNavigationItem[];
}

export function WorkspaceSidebar({ items }: WorkspaceSidebarProps) {
  const { isMobile, openMobile, setOpenMobile, state } = useSidebar();
  const isCollapsed = state === "collapsed";

  const settingsItem = findSettingsItem(items);
  const mainItems = settingsItem ? items.filter((item) => item.id !== settingsItem.id) : items;

  const handleNavigate = useCallback(() => {
    if (isMobile) {
      setOpenMobile(false);
    }
  }, [isMobile, setOpenMobile]);

  const sidebarContent = (
    <>
      <SidebarHeader className="relative">
        <div className="flex items-center justify-between gap-2">
          <WorkspaceSwitcher onNavigate={handleNavigate} />
          <SidebarTrigger
            className={clsx(
              "shrink-0",
              isCollapsed
                ? "absolute right-0 top-1/2 z-[var(--app-z-nav)] -translate-y-1/2 translate-x-full"
                : null,
            )}
          />
        </div>
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
      <SidebarRail />
    </>
  );

  if (isMobile) {
    return (
      <Sheet open={openMobile} onOpenChange={setOpenMobile}>
        <SheetContent
          data-sidebar="sidebar"
          data-mobile="true"
          className="w-[var(--app-shell-sidebar-mobile-width)] bg-sidebar p-0 text-sidebar-foreground [&>button]:hidden"
          side="left"
        >
          <SheetHeader className="sr-only">
            <SheetTitle>Sidebar</SheetTitle>
            <SheetDescription>Displays the workspace navigation.</SheetDescription>
          </SheetHeader>
          <div className="flex h-full w-full flex-col">{sidebarContent}</div>
        </SheetContent>
      </Sheet>
    );
  }

  return (
    <aside
      className={clsx(
        "group relative hidden h-full min-h-0 flex-shrink-0 flex-col border-r bg-sidebar text-sidebar-foreground md:flex",
        "transition-[width] duration-200 ease-linear",
        state === "collapsed" ? "w-[var(--sidebar-width-icon)]" : "w-[var(--sidebar-width)]",
      )}
      aria-label="Workspace navigation"
      data-state={state}
      data-collapsible={state === "collapsed" ? "icon" : ""}
      data-variant="sidebar"
      data-side="left"
    >
      <div data-sidebar="sidebar" className="flex h-full w-full flex-col">
        {sidebarContent}
      </div>
    </aside>
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
