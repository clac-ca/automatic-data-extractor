import { Navigate, Outlet, RouterProvider, createBrowserRouter } from "react-router-dom";

import { WorkspaceLayout } from "./layouts/WorkspaceLayout";
import { HomeRedirectRoute } from "./routes/HomeRedirectRoute";
import { WorkspacesIndexRoute } from "./routes/WorkspacesIndexRoute";
import { LoginRoute } from "./routes/LoginRoute";
import { SetupRoute } from "./routes/SetupRoute";
import { NotFoundRoute } from "./routes/NotFoundRoute";
import { RequireSession } from "../features/auth/components/RequireSession";
import { WorkspacePlaceholderRoute } from "./routes/WorkspacePlaceholderRoute";
import { DocumentsRoute } from "./routes/DocumentsRoute";
import { ConfigurationsRoute } from "./routes/ConfigurationsRoute";
import { WorkspaceCreateRoute } from "./routes/WorkspaceCreateRoute";
import { AuthCallbackRoute } from "./routes/AuthCallbackRoute";
import { workspaceLoader } from "./workspaces/loader";
import { workspaceSections, defaultWorkspaceSection } from "./workspaces/sections";
import type { WorkspaceRouteHandle } from "./workspaces/sections";

const workspaceSectionRoutes = workspaceSections.map((section) => ({
  path: section.path,
  element:
    section.id === "documents"
      ? <DocumentsRoute />
      : section.id === "configurations"
        ? <ConfigurationsRoute />
        : <WorkspacePlaceholderRoute sectionId={section.id} />,
  handle: { workspaceSectionId: section.id } satisfies WorkspaceRouteHandle,
}));

const appRouter = createBrowserRouter([
  {
    path: "/",
    element: (
      <RequireSession>
        <Outlet />
      </RequireSession>
    ),
    children: [
      { index: true, element: <HomeRedirectRoute /> },
      {
        path: "workspaces",
        children: [
          { index: true, element: <WorkspacesIndexRoute /> },
          { path: "new", element: <WorkspaceCreateRoute /> },
          {
            path: ":workspaceId",
            element: <WorkspaceLayout />,
            loader: workspaceLoader,
            children: [
              ...workspaceSectionRoutes,
              { path: "overview", element: <Navigate to="../documents" replace /> },
              { index: true, element: <Navigate to={defaultWorkspaceSection.path} replace /> },
            ],
          },
        ],
      },
    ],
  },
  { path: "/login", element: <LoginRoute /> },
  { path: "/setup", element: <SetupRoute /> },
  { path: "/auth/callback", element: <AuthCallbackRoute /> },
  { path: "*", element: <NotFoundRoute /> },
]);

export function AppRouter() {
  return <RouterProvider router={appRouter} />;
}
