import {
  DEFAULT_MEMBER_PAGE_SIZE,
  DEFAULT_PERMISSION_PAGE_SIZE,
  DEFAULT_ROLE_PAGE_SIZE,
  DEFAULT_WORKSPACE_PAGE_SIZE,
} from "@api/workspaces/api";
import type { ScopeType } from "@schema";

export {
  DEFAULT_WORKSPACE_PAGE_SIZE,
  DEFAULT_MEMBER_PAGE_SIZE,
  DEFAULT_ROLE_PAGE_SIZE,
  DEFAULT_PERMISSION_PAGE_SIZE,
};

const WORKSPACE_SCOPE: ScopeType = "workspace";

type WorkspaceListParams = {
  readonly page: number;
  readonly pageSize: number;
  readonly sort?: string | null;
  readonly q?: string | null;
  readonly filtersKey?: string | null;
  readonly joinOperator?: "and" | "or" | null;
};

type PermissionListParams = {
  readonly scope: ScopeType;
  readonly page: number;
  readonly pageSize: number;
};

const defaultWorkspaceListParams: WorkspaceListParams = {
  page: 1,
  pageSize: DEFAULT_WORKSPACE_PAGE_SIZE,
  sort: null,
  q: null,
};

const defaultMemberListParams: WorkspaceListParams = {
  page: 1,
  pageSize: DEFAULT_MEMBER_PAGE_SIZE,
};

const defaultRoleListParams: WorkspaceListParams = {
  page: 1,
  pageSize: DEFAULT_ROLE_PAGE_SIZE,
};

const defaultPermissionListParams: PermissionListParams = {
  scope: WORKSPACE_SCOPE,
  page: 1,
  pageSize: DEFAULT_PERMISSION_PAGE_SIZE,
};

export const workspacesKeys = {
  all: () => ["workspaces"] as const,
  list: (params: WorkspaceListParams = defaultWorkspaceListParams) =>
    [...workspacesKeys.all(), "list", { ...params }] as const,
  detail: (workspaceId: string) => [...workspacesKeys.all(), "detail", workspaceId] as const,
  members: (workspaceId: string, params: WorkspaceListParams = defaultMemberListParams) =>
    [...workspacesKeys.detail(workspaceId), "members", { ...params }] as const,
  roles: (workspaceId: string, params: WorkspaceListParams = defaultRoleListParams) =>
    [...workspacesKeys.detail(workspaceId), "roles", { ...params }] as const,
  permissions: (params: PermissionListParams = defaultPermissionListParams) => ["permissions", { ...params }] as const,
};

export const WORKSPACE_LIST_DEFAULT_PARAMS = {
  page: defaultWorkspaceListParams.page,
  pageSize: defaultWorkspaceListParams.pageSize,
  sort: defaultWorkspaceListParams.sort,
  q: defaultWorkspaceListParams.q,
} as const;
