import type {
  PermissionOut,
  PermissionPage,
  RoleCreate,
  RoleOut,
  RolePage,
  RoleUpdate,
  WorkspaceCreate,
  WorkspaceOut,
  WorkspacePage,
  WorkspaceUpdate,
  components,
} from "@/types";

export type WorkspaceProfile = WorkspaceOut;
export type WorkspaceListPage = WorkspacePage;

export type WorkspacePrincipalType = "user" | "group";

export interface WorkspacePrincipal {
  readonly principal_type: WorkspacePrincipalType;
  readonly principal_id: string;
  readonly role_ids: string[];
  readonly role_slugs: string[];
  readonly created_at: string;
  readonly principal_display_name?: string | null;
  readonly principal_email?: string | null;
  readonly principal_slug?: string | null;
}

export interface WorkspacePrincipalPage {
  readonly items: WorkspacePrincipal[];
  readonly meta: components["schemas"]["CursorMeta"];
  readonly facets?: Record<string, unknown> | null;
}

export type WorkspaceMember = components["schemas"]["WorkspaceMemberOut"];
export type WorkspaceMemberUser = components["schemas"]["WorkspaceMemberUserOut"];
export type WorkspaceMemberSource = components["schemas"]["WorkspaceMemberSourceOut"];
export type WorkspaceMemberPage = components["schemas"]["WorkspaceMemberPage"];

export type RoleDefinition = RoleOut;
export type PermissionDefinition = PermissionOut;
export type WorkspaceCreatePayload = WorkspaceCreate;
export type WorkspaceUpdatePayload = WorkspaceUpdate;
export type RoleCreatePayload = RoleCreate;
export type RoleUpdatePayload = RoleUpdate;
export type RoleListPage = RolePage;
export type WorkspaceMemberRolesUpdatePayload = components["schemas"]["WorkspaceMemberUpdate"];
export type WorkspaceMemberCreatePayload = components["schemas"]["WorkspaceMemberCreate"];
export type PermissionListPage = PermissionPage;
