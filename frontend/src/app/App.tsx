import { Suspense } from "react";
import {
  Navigate,
  NavLink,
  Outlet,
  RouterProvider,
  createBrowserRouter,
  useParams,
  useRouteError,
} from "react-router-dom";

import { Button } from "@components/Button";
import { Page } from "@components/Page";
import { useWorkspacesQuery, useWorkspaceContextQuery } from "@api/hooks/workspaces";
import { LoginPage } from "@pages/LoginPage";
import { WorkspaceListPage } from "@pages/workspaces/WorkspaceListPage";
import { WorkspaceOverviewPage } from "@pages/workspaces/WorkspaceOverviewPage";
import { WorkspacePlaceholderPage } from "@pages/workspaces/WorkspacePlaceholderPage";

import { useAuth } from "./providers/AuthProvider";
import "./App.css";

const router = createBrowserRouter([
  {
    path: "/",
    element: <RootLayout />,
    errorElement: <RootErrorBoundary />,
    children: [
      { index: true, element: <Navigate to="/workspaces" replace /> },
      {
        path: "login",
        element: <LoginPage />,
      },
      {
        path: "workspaces",
        element: <WorkspacesLayout />,
        children: [
          { index: true, element: <WorkspacesRoute /> },
          {
            path: ":workspaceId",
            element: <WorkspaceDetailLayout />,
            children: [
              { index: true, element: <WorkspaceOverviewPage /> },
              { path: "documents", element: <WorkspacePlaceholderPage name="Documents" /> },
              { path: "jobs", element: <WorkspacePlaceholderPage name="Jobs" /> },
              { path: "configurations", element: <WorkspacePlaceholderPage name="Configurations" /> },
            ],
          },
        ],
      },
    ],
  },
]);

export function App() {
  return <RouterProvider router={router} />;
}

function RootLayout() {
  const { userName } = useAuth();

  return (
    <div className="app-shell">
      <aside className="app-shell__sidebar">
        <div className="app-shell__brand">
          <span className="app-shell__brand-mark">ADE</span>
          <span className="app-shell__brand-copy">Automatic Data Extractor</span>
        </div>
        <WorkspaceSwitcher />
        <nav className="app-shell__nav">
          <NavLink to="/workspaces" end>
            Workspaces
          </NavLink>
          <NavLink to="/login">Login</NavLink>
        </nav>
        <footer className="app-shell__footer">
          <span>Signed in as</span>
          <strong>{userName}</strong>
        </footer>
      </aside>
      <main className="app-shell__main">
        <Suspense fallback={<LoadingState />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  );
}

function WorkspacesLayout() {
  return <Outlet />;
}

function WorkspacesRoute() {
  const { data: workspaces, isLoading } = useWorkspacesQuery();

  return <WorkspaceListPage workspaces={workspaces} isLoading={isLoading} />;
}

function WorkspaceDetailLayout() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const { data, isLoading } = useWorkspaceContextQuery(workspaceId);

  return (
    <Page
      title={data?.workspace.name ?? "Workspace"}
      description="Navigate between workspace surfaces."
      actions={<Button>TODO: Primary action</Button>}
    >
      {isLoading ? (
        <LoadingState label="Loading workspace" />
      ) : (
        <div className="workspace-detail">
          <aside className="workspace-detail__nav">
            <NavLink to="." end>
              Overview
            </NavLink>
            <NavLink to="documents">Documents</NavLink>
            <NavLink to="jobs">Jobs</NavLink>
            <NavLink to="configurations">Configurations</NavLink>
          </aside>
          <div className="workspace-detail__content">
            <Outlet />
          </div>
        </div>
      )}
    </Page>
  );
}

function WorkspaceSwitcher() {
  const { data: workspaces, isLoading } = useWorkspacesQuery();

  return (
    <div className="workspace-switcher">
      <span className="workspace-switcher__label">Workspace</span>
      {isLoading ? (
        <span className="workspace-switcher__value">Loading…</span>
      ) : workspaces && workspaces.length > 0 ? (
        <span className="workspace-switcher__value">{workspaces[0].name}</span>
      ) : (
        <span className="workspace-switcher__value">No workspaces</span>
      )}
    </div>
  );
}

function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="loading-state">
      <span className="loading-state__spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

function RootErrorBoundary() {
  const error = useRouteError();
  console.error(error);
  return (
    <div className="error-state">
      <h1>Something went wrong</h1>
      <p>TODO: Improve error presentation and recovery options.</p>
    </div>
  );
}
