import type { ReactNode } from "react";
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { useSessionQuery } from "../../features/auth/hooks/useSessionQuery";
import { AppShell, type AppShellProfileMenuItem, type AppShellSidebarConfig } from "./AppShell";

export interface WorkspaceDirectoryLayoutProps {
  readonly children: ReactNode;
  readonly actions?: ReactNode;
  readonly sidebar?: AppShellSidebarConfig;
}

export function WorkspaceDirectoryLayout({ children, actions, sidebar }: WorkspaceDirectoryLayoutProps) {
  const { session } = useSessionQuery();
  const navigate = useNavigate();
  const userPermissions = session?.user.permissions ?? [];
  const canManageAdmin = userPermissions.includes("System.Settings.ReadWrite");

  const profileMenuItems = useMemo<AppShellProfileMenuItem[]>(() => {
    if (!canManageAdmin) {
      return [];
    }
    return [{ type: "nav", label: "Admin settings", to: "/settings" }];
  }, [canManageAdmin]);

  return (
    <AppShell
      brand={{
        label: "Automatic Data Extractor",
        subtitle: "Workspace Directory",
        onClick: () => navigate("/workspaces"),
      }}
      navItems={[{ label: "All workspaces", to: "/workspaces", end: true }]}
      breadcrumbs={["Workspaces"]}
      actions={actions}
      sidebar={sidebar}
      profileMenuItems={profileMenuItems}
    >
      {children}
    </AppShell>
  );
}
