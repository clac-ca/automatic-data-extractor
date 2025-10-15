import { useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { AppShell, type AppShellNavItem } from "./AppShell";
import { useSession } from "../../features/auth/context/SessionContext";
import { useLogoutMutation } from "../../features/auth/hooks/useLogoutMutation";
import { DirectoryIcon } from "../workspaces/icons";

export interface WorkspaceDirectoryLayoutProps {
  readonly children: ReactNode;
  readonly sidePanel?: ReactNode;
  readonly actions?: ReactNode;
}

export function WorkspaceDirectoryLayout({ children, sidePanel, actions }: WorkspaceDirectoryLayoutProps) {
  const session = useSession();
  const logoutMutation = useLogoutMutation();
  const navigate = useNavigate();
  const [navCollapsed, setNavCollapsed] = useState(false);
  const [focusMode, setFocusMode] = useState(false);

  const navItems: AppShellNavItem[] = [
    { id: "directory", label: "All workspaces", to: "/workspaces", icon: <DirectoryIcon className="h-5 w-5" />, kind: "primary" },
  ];

  const topBarActions = actions ? <div className="flex items-center gap-3">{actions}</div> : null;

  return (
    <AppShell
      brand={{
        label: "Automatic Data Extractor",
        subtitle: "Workspace Directory",
        onClick: () => navigate("/workspaces"),
      }}
      breadcrumbs={["Workspaces"]}
      navItems={navItems}
      isLeftRailCollapsed={navCollapsed}
      onToggleLeftRail={() => setNavCollapsed((current) => !current)}
      isFocusMode={focusMode}
      onToggleFocusMode={() => setFocusMode((current) => !current)}
      topBarActions={topBarActions}
      user={{
        displayName: session.user.display_name || session.user.email || "Signed in",
        email: session.user.email ?? "",
      }}
      onSignOut={() => logoutMutation.mutate()}
      isSigningOut={logoutMutation.isPending}
    >
      <div
        className={`grid gap-6 ${sidePanel ? "lg:grid-cols-[minmax(0,1fr)_280px]" : ""}`}
      >
        <div>{children}</div>
        {sidePanel ? <aside className="space-y-6">{sidePanel}</aside> : null}
      </div>
    </AppShell>
  );
}
