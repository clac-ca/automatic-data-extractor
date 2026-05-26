import { useMemo } from "react";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { cn } from "@/lib/utils";
import {
  WorkspaceDangerPage,
  WorkspaceGeneralPage,
  WorkspaceInvitationsListPage,
  WorkspaceInvitationCreatePage,
  WorkspaceInvitationDetailPage,
  WorkspacePrincipalsListPage,
  WorkspacePrincipalCreatePage,
  WorkspacePrincipalDetailPage,
  WorkspaceProcessingPage,
  WorkspaceRolesListPage,
  WorkspaceRoleCreatePage,
  WorkspaceRoleDetailPage,
} from "@/features/settings/pages/workspaces";

type WorkspaceSettingsNavItem = {
  readonly label: string;
  readonly path: string;
  readonly permission: string;
  readonly tone?: "danger";
};

export default function WorkspaceSettingsSection() {
  const { workspace } = useWorkspaceContext();
  const location = useLocation();

  const navItems = useMemo(() => {
    const items: readonly WorkspaceSettingsNavItem[] = [
      { label: "General", path: "general", permission: "workspace.settings.manage" },
      { label: "Processing", path: "processing", permission: "workspace.settings.manage" },
      { label: "Members & Access", path: "access/principals", permission: "workspace.members.read" },
      { label: "Roles", path: "access/roles", permission: "workspace.roles.read" },
      { label: "Invitations", path: "access/invitations", permission: "workspace.invitations.read" },
      { label: "Danger Zone", path: "lifecycle/danger", permission: "workspace.delete", tone: "danger" },
    ];

    // Filter to only show items the user has some level of permission for
    return items.filter((item) => {
      // General is always visible for read-only viewing
      if (item.path === "general") return true;
      return workspace.permissions.some(
        (p) => p.toLowerCase() === item.permission.toLowerCase() || p.toLowerCase() === "workspace.settings.manage"
      );
    });
  }, [workspace.permissions]);

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col md:flex-row overflow-hidden bg-background text-foreground">
      {/* Settings Sub-Sidebar */}
      <aside className="w-full md:w-64 shrink-0 border-b md:border-b-0 md:border-r border-border/60 bg-muted/5 p-4 md:p-6 overflow-y-auto">
        <div className="mb-4 hidden md:block">
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Workspace
          </p>
          <h2 className="text-lg font-bold tracking-tight text-foreground">Settings</h2>
        </div>
        <nav className="flex md:flex-col gap-1 overflow-x-auto md:overflow-x-visible">
          {navItems.map((item) => {
            const fullPath = `/workspaces/${workspace.id}/settings/${item.path}`;
            const active =
              location.pathname === fullPath ||
              location.pathname.startsWith(`${fullPath}/`);

            return (
              <Link
                key={item.path}
                to={fullPath}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors select-none whitespace-nowrap",
                  active
                    ? "bg-accent text-accent-foreground font-semibold"
                    : item.tone === "danger"
                      ? "text-destructive hover:bg-destructive/10"
                      : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Settings Form Content */}
      <main className="min-h-0 flex-1 overflow-auto bg-muted/5 p-6 md:p-8">
        <Routes>
          <Route path="settings/general" element={<WorkspaceGeneralPage workspace={workspace} />} />
          <Route path="settings/processing" element={<WorkspaceProcessingPage workspace={workspace} />} />
          <Route path="settings/access/principals" element={<WorkspacePrincipalsListPage workspace={workspace} />} />
          <Route path="settings/access/principals/create" element={<WorkspacePrincipalCreatePage workspace={workspace} />} />
          <Route path="settings/access/principals/:principalType/:principalId" element={<WorkspacePrincipalDetailPage workspace={workspace} />} />
          <Route path="settings/access/roles" element={<WorkspaceRolesListPage workspace={workspace} />} />
          <Route path="settings/access/roles/create" element={<WorkspaceRoleCreatePage workspace={workspace} />} />
          <Route path="settings/access/roles/:roleId" element={<WorkspaceRoleDetailPage workspace={workspace} />} />
          <Route path="settings/access/invitations" element={<WorkspaceInvitationsListPage workspace={workspace} />} />
          <Route path="settings/access/invitations/create" element={<WorkspaceInvitationCreatePage workspace={workspace} />} />
          <Route path="settings/access/invitations/:invitationId" element={<WorkspaceInvitationDetailPage workspace={workspace} />} />
          <Route path="settings/lifecycle/danger" element={<WorkspaceDangerPage workspace={workspace} />} />
          <Route path="settings/*" element={<Navigate to="general" replace />} />
        </Routes>
      </main>
    </div>
  );
}
