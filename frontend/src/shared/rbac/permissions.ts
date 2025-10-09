export const RBAC = {
  Global: {
    Workspaces: {
      Create: "Workspaces.Create",
      ReadAll: "Workspaces.Read.All",
      ReadWriteAll: "Workspaces.ReadWrite.All",
    },
    Roles: {
      ReadAll: "Roles.Read.All",
      ReadWriteAll: "Roles.ReadWrite.All",
    },
    Users: {
      ReadAll: "Users.Read.All",
      ReadWriteAll: "Users.ReadWrite.All",
      Manage: "Users.Manage",
    },
  },
  Workspace: {
    Read: "Workspace.Read",
    Documents: {
      Read: "Workspace.Documents.Read",
      ReadWrite: "Workspace.Documents.ReadWrite",
    },
    Jobs: {
      Read: "Workspace.Jobs.Read",
      ReadWrite: "Workspace.Jobs.ReadWrite",
    },
    Configurations: {
      Read: "Workspace.Configurations.Read",
      ReadWrite: "Workspace.Configurations.ReadWrite",
    },
    Members: {
      Read: "Workspace.Members.Read",
      ReadWrite: "Workspace.Members.ReadWrite",
    },
    Roles: {
      Read: "Workspace.Roles.Read",
      ReadWrite: "Workspace.Roles.ReadWrite",
    },
    Settings: {
      ReadWrite: "Workspace.Settings.ReadWrite",
    },
    Delete: "Workspace.Delete",
  },
} as const;

export type WorkspacePermission = (typeof RBAC)["Workspace"][keyof typeof RBAC.Workspace] extends infer Group
  ? Group extends string
    ? Group
    : Group extends Record<string, string>
      ? Group[keyof Group]
      : never
  : never;

export type GlobalPermission = (typeof RBAC)["Global"][keyof typeof RBAC.Global] extends infer Group
  ? Group extends string
    ? Group
    : Group extends Record<string, string>
      ? Group[keyof Group]
      : never
  : never;
