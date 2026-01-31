import type {
  PermissionOut,
  PermissionPage,
  RoleCreate,
  RoleOut,
  RolePage,
  RoleUpdate,
  WorkspaceCreate,
  WorkspaceMemberCreate,
  WorkspaceMemberOut,
  WorkspaceMemberPage as WorkspaceMemberPageSchema,
  WorkspaceMemberUpdate,
  WorkspaceOut,
  WorkspacePage,
  WorkspaceUpdate,
  User,
} from "@/types";

export type WorkspaceProfile = WorkspaceOut;
export type WorkspaceListPage = WorkspacePage;

export type WorkspaceMember = WorkspaceMemberOut & { user?: User };
type WorkspaceMemberPageApi = WorkspaceMemberPageSchema;
export type WorkspaceMemberPage = Omit<WorkspaceMemberPageApi, "items"> & { items: WorkspaceMember[] };

export type RoleDefinition = RoleOut;
export type PermissionDefinition = PermissionOut;
export type WorkspaceCreatePayload = WorkspaceCreate;
export type WorkspaceUpdatePayload = WorkspaceUpdate;
export type RoleCreatePayload = RoleCreate;
export type RoleUpdatePayload = RoleUpdate;
export type RoleListPage = RolePage;
export type WorkspaceMemberRolesUpdatePayload = WorkspaceMemberUpdate;
export type WorkspaceMemberCreatePayload = WorkspaceMemberCreate;
export type PermissionListPage = PermissionPage;

