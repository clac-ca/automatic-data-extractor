import { RBAC } from "./permissions";
import { hasPermission, type PermissionList } from "./utils";

export const workspaceCan = {
  manageDocuments: (permissions: PermissionList) => hasPermission(permissions, RBAC.Workspace.Documents.ReadWrite),
  manageJobs: (permissions: PermissionList) => hasPermission(permissions, RBAC.Workspace.Jobs.ReadWrite),
  manageConfigurations: (permissions: PermissionList) => hasPermission(permissions, RBAC.Workspace.Configurations.ReadWrite),
  manageMembers: (permissions: PermissionList) => hasPermission(permissions, RBAC.Workspace.Members.ReadWrite),
  manageRoles: (permissions: PermissionList) => hasPermission(permissions, RBAC.Workspace.Roles.ReadWrite),
  manageSettings: (permissions: PermissionList) => hasPermission(permissions, RBAC.Workspace.Settings.ReadWrite),
  deleteWorkspace: (permissions: PermissionList) => hasPermission(permissions, RBAC.Workspace.Delete),
};

export const globalCan = {
  createWorkspaces: (permissions: PermissionList) =>
    hasPermission(permissions, RBAC.Global.Workspaces.Create) ||
    hasPermission(permissions, RBAC.Global.Workspaces.ReadWriteAll),
};
