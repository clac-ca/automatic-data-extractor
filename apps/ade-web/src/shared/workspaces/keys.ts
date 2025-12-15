import { DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE } from "@shared/api/pagination";
import type { ScopeType } from "@schema";

export const DEFAULT_WORKSPACE_PAGE_SIZE = MAX_PAGE_SIZE;
export const DEFAULT_MEMBER_PAGE_SIZE = DEFAULT_PAGE_SIZE;
export const DEFAULT_ROLE_PAGE_SIZE = DEFAULT_PAGE_SIZE;
export const DEFAULT_PERMISSION_PAGE_SIZE = DEFAULT_PAGE_SIZE;

const WORKSPACE_SCOPE: ScopeType = "workspace";

type WorkspaceListParams = {
  readonly page: number;
  readonly pageSize: number;
  readonly includeTotal?: boolean;
};

type PermissionListParams = {
  readonly scope: ScopeType;
  readonly page: number;
  readonly pageSize: number;
  readonly includeTotal?: boolean;
};

const defaultWorkspaceListParams: WorkspaceListParams = {
  page: 1,
  pageSize: DEFAULT_WORKSPACE_PAGE_SIZE,
  includeTotal: false,
};

const defaultMemberListParams: WorkspaceListParams = {
  page: 1,
  pageSize: DEFAULT_MEMBER_PAGE_SIZE,
  includeTotal: false,
};

const defaultRoleListParams: WorkspaceListParams = {
  page: 1,
  pageSize: DEFAULT_ROLE_PAGE_SIZE,
  includeTotal: false,
};

const defaultPermissionListParams: PermissionListParams = {
  scope: WORKSPACE_SCOPE,
  page: 1,
  pageSize: DEFAULT_PERMISSION_PAGE_SIZE,
  includeTotal: false,
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
  includeTotal: defaultWorkspaceListParams.includeTotal,
} as const;

