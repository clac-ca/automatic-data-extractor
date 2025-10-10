import { Navigate, Outlet, RouterProvider, createBrowserRouter } from "react-router-dom";

import { WorkspaceLayout } from "./layouts/WorkspaceLayout";
import { HomeRedirectRoute } from "./routes/HomeRedirectRoute";
import { WorkspacesIndexRoute } from "./routes/WorkspacesIndexRoute";
import { LoginRoute } from "./routes/LoginRoute";
import { SetupRoute } from "./routes/SetupRoute";
import { NotFoundRoute } from "./routes/NotFoundRoute";
import { RequireSession } from "../features/auth/components/RequireSession";
import { WorkspacePlaceholderRoute } from "./routes/WorkspacePlaceholderRoute";
import { WorkspaceCreateRoute } from "./routes/WorkspaceCreateRoute";
import { AuthCallbackRoute } from "./routes/AuthCallbackRoute";

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
            children: [
              { path: "documents", element: <WorkspacePlaceholderRoute section="documents" /> },
              { path: "jobs", element: <WorkspacePlaceholderRoute section="jobs" /> },
              { path: "configurations", element: <WorkspacePlaceholderRoute section="configurations" /> },
              { path: "members", element: <WorkspacePlaceholderRoute section="members" /> },
              { path: "settings", element: <WorkspacePlaceholderRoute section="settings" /> },
              { path: "overview", element: <Navigate to="../documents" replace /> },
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
