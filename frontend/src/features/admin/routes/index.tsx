import { Navigate, type RouteObject } from "react-router-dom";
import { RequireSession } from "../../../app/guards";
import { RequireGlobalPermission } from "../../../shared/rbac/RequireGlobalPermission";
import { RBAC } from "../../../shared/rbac/permissions";
import { AdminLayout } from "./AdminLayout";
import { GlobalRolesRoute } from "./GlobalRolesRoute";
import { GlobalAssignmentsRoute } from "./GlobalAssignmentsRoute";
import { WorkspaceAssignmentsRoute } from "./WorkspaceAssignmentsRoute";

export const adminRoutes: RouteObject[] = [
  {
    path: "/admin",
    element: <RequireSession />,
    children: [
      {
        element: (
          <RequireGlobalPermission needed={RBAC.Global.Roles.ReadAll}>
            <AdminLayout />
          </RequireGlobalPermission>
        ),
        children: [
          { index: true, element: <Navigate to="global/roles" replace /> },
          { path: "global/roles", element: <GlobalRolesRoute /> },
          { path: "global/assignments", element: <GlobalAssignmentsRoute /> },
          { path: "workspace", element: <WorkspaceAssignmentsRoute /> },
        ],
      },
    ],
  },
];
