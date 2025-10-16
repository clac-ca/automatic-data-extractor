import type { ReactNode } from "react";
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { AppShell, type AppShellProfileMenuItem, type AppShellSidebarConfig } from "./AppShell";
import { useSession } from "../../features/auth/context/SessionContext";
import { useLogoutMutation } from "../../features/auth/hooks/useLogoutMutation";

export interface WorkspaceDirectoryLayoutProps {
  readonly children: ReactNode;
  readonly actions?: ReactNode;
  readonly sidebar?: AppShellSidebarConfig;
}

export function WorkspaceDirectoryLayout({ children, actions, sidebar }: WorkspaceDirectoryLayoutProps) {
  const session = useSession();
  const logoutMutation = useLogoutMutation();
  const navigate = useNavigate();
  const userPermissions = session.user.permissions ?? [];
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
      user={{
        displayName: session.user.display_name || session.user.email || "Signed in",
        email: session.user.email ?? "",
      }}
      onSignOut={() => logoutMutation.mutate()}
      isSigningOut={logoutMutation.isPending}
    >
      {children}
    </AppShell>
  );
}
