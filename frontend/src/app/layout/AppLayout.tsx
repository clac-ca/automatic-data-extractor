import { useEffect, useState } from "react";
import { Outlet, useParams } from "react-router-dom";

import { TopBar } from "@components/navigation/TopBar";
import { SideNavigation } from "@components/navigation/SideNavigation";
import { StatusTray } from "@components/status/StatusTray";
import { ToastViewport } from "@components/feedback/ToastViewport";
import { useWorkspace } from "@hooks/useWorkspace";

import "@styles/layout.css";

export function AppLayout(): JSX.Element {
  const params = useParams<{ workspaceId?: string }>();
  const { workspaceId, setWorkspace } = useWorkspace();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  useEffect(() => {
    const routeWorkspaceId = params.workspaceId ?? null;

    if (routeWorkspaceId && routeWorkspaceId !== workspaceId) {
      setWorkspace(routeWorkspaceId);
    }
  }, [params.workspaceId, setWorkspace, workspaceId]);

  const handleMenuToggle = () => {
    setIsSidebarOpen((current) => !current);
  };

  const handleNavigate = () => {
    setIsSidebarOpen(false);
  };

  return (
    <div className={`app-shell ${isSidebarOpen ? "app-shell--sidebar-open" : ""}`}>
      <header className="app-shell__topbar">
        <TopBar onMenuToggle={handleMenuToggle} />
      </header>
      <aside className="app-shell__sidebar">
        <SideNavigation workspaceId={workspaceId} onNavigate={handleNavigate} />
      </aside>
      <main className="app-shell__main">
        <Outlet />
      </main>
      <StatusTray />
      <ToastViewport />
    </div>
  );
}
