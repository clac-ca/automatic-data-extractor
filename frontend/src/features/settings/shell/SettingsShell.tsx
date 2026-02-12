import { useMemo, type ReactNode } from "react";
import { Link, matchPath, useLocation } from "react-router-dom";

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
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarProvider,
  SidebarRail,
  SidebarSeparator,
} from "@/components/ui/sidebar";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { WorkspaceProfile } from "@/types/workspaces";

import type { SettingsEntityType } from "../routing/contracts";
import { settingsPaths } from "../routing/contracts";
import { settingsRail } from "../routing/navTree";
import {
  hasRequiredGlobalPermission,
  hasRequiredWorkspacePermission,
  parseSettingsRouteContext,
} from "../routing/utils";
import { useOptionalSettingsSectionContext } from "../shared/SettingsSectionContext";

function resolveWorkspacePath(pathPattern: string, workspaceId: string) {
  return pathPattern.replace(":workspaceId", encodeURIComponent(workspaceId));
}

function isPathActive(pathname: string, path: string) {
  if (path.includes(":workspaceId")) {
    const pattern = path.endsWith("/") ? `${path}*` : `${path}/*`;
    return Boolean(matchPath(path, pathname) || matchPath(pattern, pathname));
  }
  return pathname === path || pathname.startsWith(`${path}/`);
}

function entityTypeMatchesRailItem(itemId: string, entityType: SettingsEntityType | undefined) {
  if (!entityType) {
    return false;
  }
  if (itemId === "organization.users") {
    return entityType === "organizationUser";
  }
  if (itemId === "organization.groups") {
    return entityType === "organizationGroup";
  }
  if (itemId === "organization.roles") {
    return entityType === "organizationRole";
  }
  if (itemId === "workspaces.principals") {
    return entityType === "workspacePrincipal";
  }
  if (itemId === "workspaces.roles") {
    return entityType === "workspaceRole";
  }
  if (itemId === "workspaces.invitations") {
    return entityType === "workspaceInvitation";
  }
  return false;
}

export function SettingsShell({
  globalPermissions,
  workspaces,
  selectedWorkspace,
  children,
}: {
  readonly globalPermissions: ReadonlySet<string>;
  readonly workspaces: readonly WorkspaceProfile[];
  readonly selectedWorkspace: WorkspaceProfile | null;
  readonly children: ReactNode;
}) {
  const location = useLocation();
  const routeContext = parseSettingsRouteContext(location.pathname);
  const sectionContext = useOptionalSettingsSectionContext();

  const routeWorkspace = useMemo(() => {
    if (!routeContext.workspaceId) {
      return null;
    }
    return workspaces.find((workspace) => workspace.id === routeContext.workspaceId) ?? null;
  }, [routeContext.workspaceId, workspaces]);

  const effectiveWorkspace = routeWorkspace ?? selectedWorkspace;
  const currentLocationHref = `${location.pathname}${location.search}${location.hash}`;
  const contextualEntityLabel = sectionContext?.entityLabel ?? routeContext.entityId ?? null;

  const visibleRailGroups = useMemo(() => {
    return settingsRail
      .map((group) => {
        if (group.id !== "workspaces") {
          const items = group.items.filter((item) => {
            if (!hasRequiredGlobalPermission(item.requiredPermissions, globalPermissions)) {
              return false;
            }
            return true;
          });
          return { ...group, items };
        }

        if (workspaces.length === 0) {
          return { ...group, items: [] };
        }

        const listItem = group.items.find((item) => item.id === "workspaces.list");
        const contextualItems =
          routeContext.scope === "workspaces" && routeWorkspace
            ? group.items
                .filter((item) => item.id !== "workspaces.list")
                .filter((item) => hasRequiredWorkspacePermission(item.requiredPermissions, routeWorkspace))
            : [];

        const items = [listItem, ...contextualItems].filter((item): item is NonNullable<typeof item> =>
          Boolean(item),
        );

        return { ...group, items };
      })
      .filter((group) => group.items.length > 0);
  }, [globalPermissions, routeContext.scope, routeWorkspace, workspaces.length]);

  const sectionTitle =
    routeContext.scope === "organization"
      ? "Organization"
      : routeContext.scope === "workspaces"
        ? "Workspaces"
        : "Home";

  const sectionSubtitle =
    routeContext.scope === "organization"
      ? "Manage identity, policy, and security controls"
      : routeContext.scope === "workspaces"
        ? "Manage workspace access, processing, and lifecycle"
        : "Unified administration for organization and workspace settings";

  return (
    <SidebarProvider defaultOpen className="flex h-full min-h-0 w-full overflow-hidden bg-background">
      <Sidebar collapsible="icon" className="border-r border-border/60">
        <SidebarHeader className="border-b border-border/60 px-3 py-3">
          <div className="group-data-[collapsible=icon]:hidden">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              ADE Admin
            </p>
            <h2 className="text-base font-semibold text-foreground">Settings</h2>
          </div>
          <div className="hidden items-center justify-center group-data-[collapsible=icon]:flex">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-muted text-xs font-semibold text-foreground">
              S
            </span>
          </div>
        </SidebarHeader>

        <SidebarContent>
          {visibleRailGroups.map((group) => (
            <SidebarGroup key={group.id}>
              <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {group.id === "workspaces"
                    ? (() => {
                        const listItem = group.items.find((item) => item.id === "workspaces.list");
                        if (!listItem) {
                          return null;
                        }

                        const workspaceIdForPath = routeWorkspace?.id ?? effectiveWorkspace?.id;
                        const listHref = listItem.path;
                        const contextualItems = group.items.filter((item) => item.id !== "workspaces.list");
                        const listActive =
                          location.pathname === settingsPaths.workspaces.list ||
                          routeContext.scope === "workspaces";

                        const selectedWorkspaceActive =
                          routeContext.scope === "workspaces" && Boolean(routeWorkspace);
                        const workspaceName = (routeWorkspace ?? effectiveWorkspace)?.name ?? "Workspace";

                        return (
                          <SidebarMenuItem key={listItem.id}>
                            <SidebarMenuButton asChild isActive={listActive}>
                              <Link
                                to={listHref}
                                className={cn(
                                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                                  listActive ? "font-semibold" : undefined,
                                )}
                                aria-current={location.pathname === settingsPaths.workspaces.list ? "page" : undefined}
                              >
                                <listItem.icon className="size-4" />
                                <span>{listItem.label}</span>
                              </Link>
                            </SidebarMenuButton>

                            {contextualItems.length > 0 && workspaceIdForPath ? (
                              <SidebarMenuSub>
                                <SidebarMenuSubItem>
                                  <SidebarMenuSubButton
                                    asChild
                                    isActive={selectedWorkspaceActive}
                                  >
                                    <Link to={settingsPaths.workspaces.general(workspaceIdForPath)}>
                                      <span>{workspaceName}</span>
                                    </Link>
                                  </SidebarMenuSubButton>
                                  <SidebarMenuSub>
                                    {contextualItems.map((item) => {
                                      const href = resolveWorkspacePath(item.path, workspaceIdForPath);
                                      const active = isPathActive(location.pathname, href);
                                      const entityActive = entityTypeMatchesRailItem(
                                        item.id,
                                        routeContext.entityType,
                                      );
                                      return (
                                        <SidebarMenuSubItem key={item.id}>
                                          <SidebarMenuSubButton
                                            asChild
                                            isActive={active}
                                            className={cn(
                                              item.tone === "danger"
                                                ? "text-destructive hover:text-destructive"
                                                : undefined,
                                            )}
                                          >
                                            <Link to={href} aria-current={active ? "page" : undefined}>
                                              <span>{item.label}</span>
                                            </Link>
                                          </SidebarMenuSubButton>

                                          {entityActive && contextualEntityLabel ? (
                                            <SidebarMenuSub>
                                              <SidebarMenuSubItem>
                                                <SidebarMenuSubButton asChild isActive>
                                                  <Link to={currentLocationHref} aria-current="page">
                                                    <span>{contextualEntityLabel}</span>
                                                  </Link>
                                                </SidebarMenuSubButton>
                                              </SidebarMenuSubItem>
                                            </SidebarMenuSub>
                                          ) : null}
                                        </SidebarMenuSubItem>
                                      );
                                    })}
                                  </SidebarMenuSub>
                                </SidebarMenuSubItem>
                              </SidebarMenuSub>
                            ) : null}
                          </SidebarMenuItem>
                        );
                      })()
                    : group.items.map((item) => {
                        const workspaceIdForPath = routeWorkspace?.id ?? effectiveWorkspace?.id;
                        const href =
                          item.path.includes(":workspaceId") && workspaceIdForPath
                            ? resolveWorkspacePath(item.path, workspaceIdForPath)
                            : item.path;
                        const active = isPathActive(location.pathname, href);
                        const entityActive = entityTypeMatchesRailItem(item.id, routeContext.entityType);

                        return (
                          <SidebarMenuItem key={item.id}>
                            <SidebarMenuButton asChild isActive={active}>
                              <Link
                                to={href}
                                className={cn(
                                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                                  item.tone === "danger" ? "text-destructive" : undefined,
                                  active ? "font-semibold" : undefined,
                                )}
                                aria-current={active ? "page" : undefined}
                              >
                                <item.icon className="size-4" />
                                <span>{item.label}</span>
                              </Link>
                            </SidebarMenuButton>

                            {entityActive && contextualEntityLabel ? (
                              <SidebarMenuSub>
                                <SidebarMenuSubItem>
                                  <SidebarMenuSubButton asChild isActive>
                                    <Link to={currentLocationHref} aria-current="page">
                                      <span>{contextualEntityLabel}</span>
                                    </Link>
                                  </SidebarMenuSubButton>
                                </SidebarMenuSubItem>
                              </SidebarMenuSub>
                            ) : null}
                          </SidebarMenuItem>
                        );
                      })}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          ))}
        </SidebarContent>

        <SidebarSeparator />
        <SidebarFooter>
          <p className="px-2 text-xs text-muted-foreground group-data-[collapsible=icon]:hidden">
            Unified settings console
          </p>
        </SidebarFooter>
        <SidebarRail />
      </Sidebar>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <header className="border-b border-border/60 bg-background px-6 py-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-semibold tracking-tight text-foreground">Settings</h1>
                <Badge variant="outline">{sectionTitle}</Badge>
                {routeWorkspace ? <Badge variant="secondary">{routeWorkspace.name}</Badge> : null}
              </div>
              <p className="text-sm text-muted-foreground">{sectionSubtitle}</p>
            </div>
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-auto bg-muted/20 p-4 sm:p-6">{children}</main>
      </div>
    </SidebarProvider>
  );
}
