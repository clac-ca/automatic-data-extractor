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

const defaultWorkspaceListParams = {
  page: 1,
  pageSize: DEFAULT_WORKSPACE_PAGE_SIZE,
  sort: null,
  q: null,
};

const defaultMemberListParams = {
  page: 1,
  pageSize: DEFAULT_MEMBER_PAGE_SIZE,
};

const defaultRoleListParams = {
  page: 1,
  pageSize: DEFAULT_ROLE_PAGE_SIZE,
};

const defaultPermissionListParams = {
  scope: WORKSPACE_SCOPE,
  page: 1,
  pageSize: DEFAULT_PERMISSION_PAGE_SIZE,
};

export const workspacesKeys = {
  all: () => ["workspaces"] as const,
  list: (params: Record<string, unknown> = defaultWorkspaceListParams) =>
    [...workspacesKeys.all(), "list", params] as const,
  detail: (workspaceId: string) => [...workspacesKeys.all(), "detail", workspaceId] as const,
  members: (workspaceId: string, params: Record<string, unknown> = defaultMemberListParams) =>
    [...workspacesKeys.detail(workspaceId), "members", params] as const,
  roles: (workspaceId: string, params: Record<string, unknown> = defaultRoleListParams) =>
    [...workspacesKeys.detail(workspaceId), "roles", params] as const,
  permissions: (params: Record<string, unknown> = defaultPermissionListParams) =>
    ["permissions", params] as const,
};

export const WORKSPACE_LIST_DEFAULT_PARAMS = {
  page: defaultWorkspaceListParams.page,
  pageSize: defaultWorkspaceListParams.pageSize,
  sort: defaultWorkspaceListParams.sort,
  q: defaultWorkspaceListParams.q,
} as const;
