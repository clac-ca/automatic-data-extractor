import { Outlet, type RouteObject } from "react-router-dom";
import { RequireSession } from "../../../app/guards";
import { RequirePermission } from "../../../shared/rbac/RequirePermission";
import { RBAC } from "../../../shared/rbac/permissions";
import { WorkspaceLayout } from "../components/WorkspaceLayout";
import { WorkspaceOverviewRoute } from "./WorkspaceOverviewRoute";
import { WorkspaceDocumentsRoute } from "./WorkspaceDocumentsRoute";
import { DocumentTypeRoute } from "./DocumentTypeRoute";
import { WorkspaceJobsRoute } from "./WorkspaceJobsRoute";
import { WorkspaceConfigurationsRoute } from "./WorkspaceConfigurationsRoute";
import { WorkspaceMembersRoute } from "./WorkspaceMembersRoute";
import { WorkspaceRolesRoute } from "./WorkspaceRolesRoute";
import { WorkspaceSettingsRoute } from "./WorkspaceSettingsRoute";

export const workspaceRoutes: RouteObject[] = [
  {
    path: "/workspaces",
    element: <RequireSession />,
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
];
