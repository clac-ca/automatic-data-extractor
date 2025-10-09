import { RBAC } from "./permissions";
import { hasAnyPermission, hasPermission, type PermissionList } from "./utils";

export const workspaceCan = {
  viewDocuments: (permissions: PermissionList) =>
    hasAnyPermission(permissions, [RBAC.Workspace.Documents.Read, RBAC.Workspace.Documents.ReadWrite]),
  manageDocuments: (permissions: PermissionList) => hasPermission(permissions, RBAC.Workspace.Documents.ReadWrite),
  viewJobs: (permissions: PermissionList) =>
    hasAnyPermission(permissions, [RBAC.Workspace.Jobs.Read, RBAC.Workspace.Jobs.ReadWrite]),
  manageJobs: (permissions: PermissionList) => hasPermission(permissions, RBAC.Workspace.Jobs.ReadWrite),
  viewConfigurations: (permissions: PermissionList) =>
    hasAnyPermission(permissions, [RBAC.Workspace.Configurations.Read, RBAC.Workspace.Configurations.ReadWrite]),
  manageConfigurations: (permissions: PermissionList) => hasPermission(permissions, RBAC.Workspace.Configurations.ReadWrite),
  viewMembers: (permissions: PermissionList) =>
    hasAnyPermission(permissions, [RBAC.Workspace.Members.Read, RBAC.Workspace.Members.ReadWrite]),
  manageMembers: (permissions: PermissionList) => hasPermission(permissions, RBAC.Workspace.Members.ReadWrite),
  viewRoles: (permissions: PermissionList) =>
    hasAnyPermission(permissions, [RBAC.Workspace.Roles.Read, RBAC.Workspace.Roles.ReadWrite]),
  manageRoles: (permissions: PermissionList) => hasPermission(permissions, RBAC.Workspace.Roles.ReadWrite),
  manageSettings: (permissions: PermissionList) => hasPermission(permissions, RBAC.Workspace.Settings.ReadWrite),
  deleteWorkspace: (permissions: PermissionList) => hasPermission(permissions, RBAC.Workspace.Delete),
};

export const globalCan = {
  createWorkspaces: (permissions: PermissionList) =>
    hasAnyPermission(permissions, [RBAC.Global.Workspaces.Create, RBAC.Global.Workspaces.ReadWriteAll]),
};
