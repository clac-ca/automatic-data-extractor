import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

import { useAuth } from "../app/auth/AuthContext";
import { useWorkspaceSelection } from "../app/workspaces/WorkspaceSelectionContext";
import { DocumentTypeSelect } from "./DocumentTypeSelect";
import { WorkspaceSwitcher } from "./WorkspaceSwitcher";

interface AppLayoutProps {
  children: ReactNode;
}

function navLinkClass(isActive: boolean, disabled = false) {
  if (disabled) {
    return "app-nav-link disabled";
  }
  return `app-nav-link${isActive ? " active" : ""}`;
}

export function AppLayout({ children }: AppLayoutProps) {
  const { status, email, signOut } = useAuth();
  const { selectedWorkspaceId } = useWorkspaceSelection();
  const workspacePath = selectedWorkspaceId
    ? `/workspaces/${selectedWorkspaceId}`
    : null;

  return (
    <div className="app-shell">
      <aside className="app-side-nav">
        <div className="app-nav-section">
          <NavLink to="/workspaces" className={({ isActive }) => navLinkClass(isActive)}>
            Workspaces
          </NavLink>
          <NavLink
            to={workspacePath ? `${workspacePath}/overview` : "/workspaces"}
            className={({ isActive }) => navLinkClass(isActive, !workspacePath)}
          >
            Overview
          </NavLink>
          <NavLink
            to={workspacePath ? `${workspacePath}/documents` : "/workspaces"}
            className={({ isActive }) => navLinkClass(isActive, !workspacePath)}
          >
            Documents
          </NavLink>
          <NavLink
            to={workspacePath ? `${workspacePath}/jobs` : "/workspaces"}
            className={({ isActive }) => navLinkClass(isActive, !workspacePath)}
          >
            Jobs
          </NavLink>
          <NavLink
            to={workspacePath ? `${workspacePath}/results` : "/workspaces"}
            className={({ isActive }) => navLinkClass(isActive, !workspacePath)}
          >
            Results
          </NavLink>
          <NavLink
            to={workspacePath ? `${workspacePath}/configurations` : "/workspaces"}
            className={({ isActive }) => navLinkClass(isActive, !workspacePath)}
          >
            Configurations
          </NavLink>
          <NavLink
            to={workspacePath ? `${workspacePath}/settings` : "/workspaces"}
            className={({ isActive }) => navLinkClass(isActive, !workspacePath)}
          >
            Workspace settings
          </NavLink>
        </div>
      </aside>
      <div className="app-main">
        <header className="top-bar">
          <div className="top-bar-left">
            <span className="top-bar-brand">Automatic Data Extractor</span>
          </div>
          <DocumentTypeSelect />
          <div className="top-bar-actions">
            {status === "authenticated" ? (
              <>
                <WorkspaceSwitcher />
                <div className="user-menu">
                  <span className="muted">{email}</span>
                  <button type="button" className="button-secondary" onClick={signOut}>
                    Sign out
                  </button>
                </div>
              </>
            ) : null}
          </div>
        </header>
        <main>{children}</main>
      </div>
    </div>
  );
}
