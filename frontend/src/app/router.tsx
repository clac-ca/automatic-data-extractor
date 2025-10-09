import { createBrowserRouter, Outlet, RouterProvider } from "react-router-dom";

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
import { WorkspaceDocumentsRoute } from "../features/workspaces/routes/WorkspaceDocumentsRoute";
import { WorkspaceJobsRoute } from "../features/workspaces/routes/WorkspaceJobsRoute";
import { WorkspaceConfigurationsRoute } from "../features/workspaces/routes/WorkspaceConfigurationsRoute";
import { WorkspaceMembersRoute } from "../features/workspaces/routes/WorkspaceMembersRoute";
import { WorkspaceRolesRoute } from "../features/workspaces/routes/WorkspaceRolesRoute";
import { WorkspaceSettingsRoute } from "../features/workspaces/routes/WorkspaceSettingsRoute";
import { RequirePermission } from "../shared/rbac/RequirePermission";
import { RBAC } from "../shared/rbac/permissions";

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
                  path: "documents",
                  element: (
                    <RequirePermission needed={RBAC.Workspace.Documents.Read}>
                      <Outlet />
                    </RequirePermission>
                  ),
                  children: [
                    { index: true, element: <WorkspaceDocumentsRoute /> },
                    { path: ":documentTypeId", element: <DocumentTypeRoute /> },
                  ],
                },
                {
                  path: "jobs",
                  element: (
                    <RequirePermission needed={RBAC.Workspace.Jobs.Read}>
                      <WorkspaceJobsRoute />
                    </RequirePermission>
                  ),
                },
                {
                  path: "configurations",
                  element: (
                    <RequirePermission needed={RBAC.Workspace.Configurations.Read}>
                      <WorkspaceConfigurationsRoute />
                    </RequirePermission>
                  ),
                },
                {
                  path: "members",
                  element: (
                    <RequirePermission needed={RBAC.Workspace.Members.Read}>
                      <WorkspaceMembersRoute />
                    </RequirePermission>
                  ),
                },
                {
                  path: "roles",
                  element: (
                    <RequirePermission needed={RBAC.Workspace.Roles.Read}>
                      <WorkspaceRolesRoute />
                    </RequirePermission>
                  ),
                },
                {
                  path: "settings",
                  element: (
                    <RequirePermission needed={RBAC.Workspace.Settings.ReadWrite}>
                      <WorkspaceSettingsRoute />
                    </RequirePermission>
                  ),
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
