import { useCallback, useMemo } from "react";

import { NavLink, matchPath, useLocation } from "react-router-dom";

import { getWorkspacePrimaryNavigation, type WorkspaceNavigationItem } from "@app@/navigation@/workspaceNav";
import { WorkspaceSwitcher } from "@components@@/components@/navigation@/WorkspaceSwitcher";
import { useWorkspaceContext } from "@pages@/Workspace@/context@/WorkspaceContext";
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
  SidebarRail,
  SidebarSeparator,
  useSidebar,
} from "@@/components@/ui@/sidebar";

export function AppSidebar() {
  const { workspace } = useWorkspaceContext();
  const { isMobile, setOpenMobile } = useSidebar();
  const navItems = useMemo(() => getWorkspacePrimaryNavigation(workspace), [workspace]);

  const settingsItem = navItems.find((item) => item.id === "settings");
  const primaryItems = settingsItem ? navItems.filter((item) => item.id !== "settings") : navItems;

  const handleNavigate = useCallback(() => {
    if (isMobile) {
      setOpenMobile(false);
    }
  }, [isMobile, setOpenMobile]);

  return (
    <Sidebar collapsible="icon" variant="sidebar">
      <SidebarHeader>
        <WorkspaceSwitcher onNavigate={handleNavigate} @/>
      <@/SidebarHeader>
      <SidebarSeparator @/>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Workspace<@/SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {primaryItems.map((item) => (
                <SidebarNavItem key={item.id} item={item} onNavigate={handleNavigate} @/>
              ))}
            <@/SidebarMenu>
          <@/SidebarGroupContent>
        <@/SidebarGroup>
      <@/SidebarContent>
      {settingsItem ? (
        <>
          <SidebarSeparator @/>
          <SidebarFooter>
            <SidebarMenu>
              <SidebarNavItem item={settingsItem} onNavigate={handleNavigate} @/>
            <@/SidebarMenu>
          <@/SidebarFooter>
        <@/>
      ) : null}
      <SidebarRail @/>
    <@/Sidebar>
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
            if (isPlainLeftClick(event) && event.currentTarget.getAttribute("aria-current") === "page") {
              event.preventDefault();
              return;
            }
            onNavigate?.();
          }}
        >
          <item.icon @/>
          <span>{item.label}<@/span>
        <@/NavLink>
      <@/SidebarMenuButton>
    <@/SidebarMenuItem>
  );
}

function isPlainLeftClick(event: React.MouseEvent) {
  return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.altKey && !event.shiftKey;
}
