import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { RootRoute } from "./RootRoute";
import { NotFoundRoute } from "./NotFoundRoute";
import { AppErrorPage } from "./AppErrorPage";
import { SetupRoute } from "../features/setup/routes/SetupRoute";
import { LoginRoute } from "../features/auth/routes/LoginRoute";
import { LogoutRoute } from "../features/auth/routes/LogoutRoute";
import { RequireSession } from "../features/auth/components/RequireSession";
import { WorkspaceLayout } from "../features/workspaces/components/WorkspaceLayout";
import { WorkspaceOverviewRoute } from "../features/workspaces/routes/WorkspaceOverviewRoute";
import { DocumentTypeRoute } from "../features/workspaces/routes/DocumentTypeRoute";

export function createAppRouter() {
  return createBrowserRouter([
    { path: "/", element: <RootRoute />, errorElement: <AppErrorPage /> },
    { path: "/setup", element: <SetupRoute />, errorElement: <AppErrorPage /> },
    { path: "/login", element: <LoginRoute />, errorElement: <AppErrorPage /> },
    { path: "/logout", element: <LogoutRoute />, errorElement: <AppErrorPage /> },
    {
      path: "/workspaces",
      element: <RequireSession />,
      errorElement: <AppErrorPage />,
      children: [
        {
          element: <WorkspaceLayout />,
          children: [
            { index: true, element: <WorkspaceOverviewRoute /> },
            {
              path: ":workspaceId",
              children: [
                { index: true, element: <WorkspaceOverviewRoute /> },
                {
                  path: "document-types/:documentTypeId",
                  element: <DocumentTypeRoute />,
                },
              ],
            },
          ],
        },
      ],
    },
    { path: "*", element: <NotFoundRoute /> },
  ]);
}

const router = createAppRouter();

export function AppRouter() {
  return <RouterProvider router={router} />;
}
