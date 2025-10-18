import { Navigate, Outlet, RouterProvider, createBrowserRouter } from "react-router-dom";

import { WorkspaceLayout } from "./layouts/workspace/WorkspaceLayout";
import { RequireSession } from "../features/auth/components/RequireSession";
import { workspaceLoader } from "./workspaces/loader";
import { HomeRedirectRoute } from "../features/workspaces/routes/home-redirect.route";
import { WorkspacesIndexRoute } from "../features/workspaces/routes/workspaces-index.route";
import { LoginRoute } from "../features/auth/routes/login.route";
import { SetupRoute } from "../features/setup/routes/setup.route";
import { NotFoundRoute } from "../features/system/routes/not-found.route";
import { WorkspaceCreateRoute } from "../features/workspaces/routes/workspace-create.route";
import { AuthCallbackRoute } from "../features/auth/routes/auth-callback.route";
import { DocumentsRoute } from "../features/documents/routes/documents.route";
import { ConfigurationsRoute } from "../features/configurations/routes/configurations.route";
import { WorkspaceSettingsRoute } from "../features/workspaces/routes/workspace-settings.route";

const appRouter = createBrowserRouter([
  {
    path: "/",
    element: <AuthenticatedOutletLayout />,
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
            shouldRevalidate: ({ currentParams, nextParams }) =>
              currentParams.workspaceId !== nextParams.workspaceId,
            children: [
              { path: "documents", element: <DocumentsRoute /> },
              { path: "config", element: <ConfigurationsRoute /> },
              { path: "settings", element: <WorkspaceSettingsRoute /> },
              { index: true, element: <Navigate to="documents" replace /> },
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

function AuthenticatedOutletLayout() {
  return (
    <RequireSession>
      <Outlet />
    </RequireSession>
  );
}
