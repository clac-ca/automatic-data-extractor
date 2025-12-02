import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { client } from "@shared/api/client";
import type {
  PermissionOut,
  PermissionPage,
  RoleCreate,
  RoleOut,
  RolePage,
  RoleUpdate,
  ScopeType,
  WorkspaceCreate,
  WorkspaceMemberCreate,
  WorkspaceMemberOut,
  WorkspaceMemberPage as WorkspaceMemberPageSchema,
  WorkspaceMemberUpdate,
  WorkspacePage,
  WorkspaceOut,
  WorkspaceUpdate,
  paths,
  User,
} from "@schema";
import type { PathsWithMethod } from "openapi-typescript-helpers";

const DEFAULT_WORKSPACE_PAGE_SIZE = 100;
const DEFAULT_MEMBER_PAGE_SIZE = 100;
const DEFAULT_ROLE_PAGE_SIZE = 100;
const DEFAULT_PERMISSION_PAGE_SIZE = 200;

const GLOBAL_SCOPE: ScopeType = "global";
const WORKSPACE_SCOPE: ScopeType = "workspace";

type ListWorkspacesQuery = paths["/api/v1/workspaces"]["get"]["parameters"]["query"];
type ListWorkspaceMembersQuery =
  paths["/api/v1/workspaces/{workspace_id}/members"]["get"]["parameters"]["query"];
type ListRolesQuery = paths["/api/v1/rbac/roles"]["get"]["parameters"]["query"];
type ListPermissionsQuery = paths["/api/v1/rbac/permissions"]["get"]["parameters"]["query"];

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

export interface ListWorkspacesOptions {
  readonly page?: number;
  readonly pageSize?: number;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function fetchWorkspaces(options: ListWorkspacesOptions = {}): Promise<WorkspaceListPage> {
  const { page, pageSize, includeTotal, signal } = options;
  const query: ListWorkspacesQuery = {};

  if (typeof page === "number" && page > 0) {
    query.page = page;
  }
  if (typeof pageSize === "number" && pageSize > 0) {
    query.page_size = pageSize;
  }
  if (includeTotal) {
    query.include_total = true;
  }

  const { data } = await client.GET("/api/v1/workspaces", {
    params: { query },
    signal,
  });

  if (!data) {
    throw new Error("Expected workspace page payload.");
  }

  const sorted = [...data.items].sort((a, b) => a.name.localeCompare(b.name));
  return { ...data, items: sorted };
}

export async function createWorkspace(payload: WorkspaceCreatePayload): Promise<WorkspaceProfile> {
  const { data } = await client.POST("/api/v1/workspaces", {
    body: payload,
  });

  if (!data) {
    throw new Error("Expected workspace payload.");
  }

  return data;
}

export async function updateWorkspace(
  workspaceId: string,
  payload: WorkspaceUpdatePayload,
): Promise<WorkspaceProfile> {
  const { data } = await client.PATCH("/api/v1/workspaces/{workspace_id}", {
    params: { path: { workspace_id: workspaceId } },
    body: payload,
  });

  if (!data) {
    throw new Error("Expected workspace payload.");
  }

  return data;
}

export async function listWorkspaceMembers(
  workspaceId: string,
  options: ListWorkspaceMembersOptions = {},
): Promise<WorkspaceMemberPage> {
  const { page, pageSize, includeTotal, signal } = options;
  const query: ListWorkspaceMembersQuery = {};

  if (typeof page === "number" && page > 0) {
    query.page = page;
  }
  if (typeof pageSize === "number" && pageSize > 0) {
    query.page_size = pageSize;
  }
  if (includeTotal) {
    query.include_total = true;
  }

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/members", {
    params: { path: { workspace_id: workspaceId }, query },
    signal,
  });

  if (!data) {
    throw new Error("Expected workspace member page payload.");
  }

  return data;
}

export async function addWorkspaceMember(
  workspaceId: string,
  payload: WorkspaceMemberCreatePayload,
): Promise<WorkspaceMember> {
  const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/members", {
    params: { path: { workspace_id: workspaceId } },
    body: payload,
  });

  if (!data) {
    throw new Error("Expected workspace member payload.");
  }

  return data as WorkspaceMember;
}

export async function updateWorkspaceMemberRoles(
  workspaceId: string,
  userId: string,
  payload: WorkspaceMemberRolesUpdatePayload,
): Promise<WorkspaceMember> {
  const { data } = await client.PUT(
    "/api/v1/workspaces/{workspace_id}/members/{user_id}",
    {
      params: {
        path: {
          workspace_id: workspaceId,
          user_id: userId,
        },
      },
      body: payload,
    },
  );

  if (!data) {
    throw new Error("Expected workspace member payload.");
  }

  return data as WorkspaceMember;
}

export async function removeWorkspaceMember(workspaceId: string, userId: string) {
  await client.DELETE("/api/v1/workspaces/{workspace_id}/members/{user_id}", {
    params: {
      path: {
        workspace_id: workspaceId,
        user_id: userId,
      },
    },
  });
}

export interface ListWorkspaceMembersOptions {
  readonly page?: number;
  readonly pageSize?: number;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export interface ListWorkspaceRolesOptions {
  readonly page?: number;
  readonly pageSize?: number;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function listWorkspaceRoles(
  options: ListWorkspaceRolesOptions = {},
): Promise<RoleListPage> {
  const { page, pageSize, includeTotal, signal } = options;
  const query: ListRolesQuery = { scope: WORKSPACE_SCOPE };

  if (typeof page === "number" && page > 0) {
    query.page = page;
  }
  if (typeof pageSize === "number" && pageSize > 0) {
    query.page_size = pageSize;
  }
  if (includeTotal) {
    query.include_total = true;
  }

  const { data } = await client.GET("/api/v1/rbac/roles", { params: { query }, signal });

  if (!data) {
    throw new Error("Expected workspace role page payload.");
  }

  return data;
}

export async function createWorkspaceRole(_workspaceId: string, payload: RoleCreatePayload) {
  const { data } = await client.POST("/api/v1/rbac/roles", { body: payload });

  if (!data) {
    throw new Error("Expected role payload.");
  }

  return data;
}

export async function updateWorkspaceRole(
  _workspaceId: string,
  roleId: string,
  payload: RoleUpdatePayload,
) {
  const { data } = await client.PATCH("/api/v1/rbac/roles/{role_id}", {
    params: { path: { role_id: roleId } },
    body: payload,
  });

  if (!data) {
    throw new Error("Expected role payload.");
  }

  return data;
}

export async function deleteWorkspaceRole(_workspaceId: string, roleId: string) {
  await client.DELETE("/api/v1/rbac/roles/{role_id}", {
    params: { path: { role_id: roleId } },
  });
}

export interface ListPermissionsOptions {
  readonly scope?: ScopeType;
  readonly page?: number;
  readonly pageSize?: number;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function listPermissions(options: ListPermissionsOptions = {}): Promise<PermissionListPage> {
  const { scope = GLOBAL_SCOPE, page, pageSize, includeTotal, signal } = options;
  const query: ListPermissionsQuery = { scope };

  if (typeof page === "number" && page > 0) {
    query.page = page;
  }
  if (typeof pageSize === "number" && pageSize > 0) {
    query.page_size = pageSize;
  }
  if (includeTotal) {
    query.include_total = true;
  }

  const { data } = await client.GET("/api/v1/rbac/permissions", {
    params: { query },
    signal,
  });

  if (!data) {
    throw new Error("Expected permission page payload.");
  }

  return data;
}

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
  scope: GLOBAL_SCOPE,
  page: 1,
  pageSize: DEFAULT_PERMISSION_PAGE_SIZE,
  includeTotal: false,
};

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

export const workspacesKeys = {
  all: () => ["workspaces"] as const,
  list: (params: WorkspaceListParams = defaultWorkspaceListParams) =>
    [...workspacesKeys.all(), "list", { ...params }] as const,
  detail: (workspaceId: string) => [...workspacesKeys.all(), "detail", workspaceId] as const,
  members: (workspaceId: string, params: WorkspaceListParams = defaultMemberListParams) =>
    [...workspacesKeys.detail(workspaceId), "members", { ...params }] as const,
  roles: (workspaceId: string, params: WorkspaceListParams = defaultRoleListParams) =>
    [...workspacesKeys.detail(workspaceId), "roles", { ...params }] as const,
  permissions: (params: PermissionListParams = defaultPermissionListParams) =>
    ["permissions", { ...params }] as const,
};

interface WorkspacesQueryOptions {
  readonly enabled?: boolean;
  readonly page?: number;
  readonly pageSize?: number;
  readonly includeTotal?: boolean;
}

function workspacesListQueryOptions(options: WorkspacesQueryOptions = {}) {
  const page = options.page ?? defaultWorkspaceListParams.page;
  const pageSize = options.pageSize ?? defaultWorkspaceListParams.pageSize;
  const includeTotal = options.includeTotal ?? defaultWorkspaceListParams.includeTotal;

  return {
    queryKey: workspacesKeys.list({ page, pageSize, includeTotal }),
    queryFn: ({ signal }: { signal?: AbortSignal }) =>
      fetchWorkspaces({ page, pageSize, includeTotal, signal }),
    staleTime: 60_000,
    enabled: options.enabled ?? true,
  };
}

export function useWorkspacesQuery(options: WorkspacesQueryOptions = {}) {
  const queryClient = useQueryClient();
  const queryOptions = workspacesListQueryOptions(options);
  const initialData = queryClient.getQueryData<WorkspaceListPage>(queryOptions.queryKey);
  return useQuery<WorkspaceListPage>({ ...queryOptions, initialData });
}

export const WORKSPACE_LIST_DEFAULT_PARAMS = {
  page: defaultWorkspaceListParams.page,
  pageSize: defaultWorkspaceListParams.pageSize,
  includeTotal: defaultWorkspaceListParams.includeTotal,
} as const;

const setDefaultWorkspacePath: PathsWithMethod<paths, "put"> =
  "/api/v1/workspaces/{workspace_id}/default";

export async function setDefaultWorkspace(workspaceId: string): Promise<void> {
  await client.PUT(setDefaultWorkspacePath, {
    params: { path: { workspace_id: workspaceId } },
  });
}

function applyDefaultWorkspaceSelection(
  cached: unknown,
  workspaceId: string,
): unknown {
  if (!cached || typeof cached !== "object") {
    return cached;
  }

  if ("items" in cached) {
    const list = cached as WorkspaceListPage;
    if (!Array.isArray(list.items)) {
      return cached;
    }
    const items = list.items.map((workspace) => ({
      ...workspace,
      is_default: workspace.id === workspaceId,
    }));
    return { ...list, items };
  }

  if ("id" in cached && "is_default" in cached) {
    const workspace = cached as WorkspaceProfile;
    return { ...workspace, is_default: workspace.id === workspaceId };
  }

  return cached;
}

export function useSetDefaultWorkspaceMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (workspaceId: string) => setDefaultWorkspace(workspaceId),
    onSuccess: (_data, workspaceId) => {
      queryClient.setQueriesData(
        { queryKey: workspacesKeys.all() },
        (cached) => applyDefaultWorkspaceSelection(cached, workspaceId),
      );
    },
  });
}
