import { useQuery } from "@tanstack/react-query";

import { client } from "@shared/api/client";
import type { components, paths } from "@openapi";

const DEFAULT_WORKSPACE_PAGE_SIZE = 100;
const DEFAULT_MEMBER_PAGE_SIZE = 100;
const DEFAULT_ROLE_PAGE_SIZE = 100;
const DEFAULT_PERMISSION_PAGE_SIZE = 200;

type ListWorkspacesQuery = paths["/api/v1/workspaces"]["get"]["parameters"]["query"];
type ListWorkspaceMembersQuery =
  paths["/api/v1/workspaces/{workspace_id}/members"]["get"]["parameters"]["query"];
type ListWorkspaceRolesQuery =
  paths["/api/v1/workspaces/{workspace_id}/roles"]["get"]["parameters"]["query"];
type ListPermissionsQuery = paths["/api/v1/permissions"]["get"]["parameters"]["query"];

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

export type WorkspaceMemberCreatePayload = components["schemas"]["WorkspaceMemberCreate"];

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
) {
  const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/members", {
    params: { path: { workspace_id: workspaceId } },
    body: payload,
  });

  if (!data) {
    throw new Error("Expected workspace member payload.");
  }

  return data;
}

export type WorkspaceMemberRolesUpdatePayload = components["schemas"]["WorkspaceMemberRolesUpdate"];

export async function updateWorkspaceMemberRoles(
  workspaceId: string,
  membershipId: string,
  payload: WorkspaceMemberRolesUpdatePayload,
) {
  const { data } = await client.PUT("/api/v1/workspaces/{workspace_id}/members/{membership_id}/roles", {
    params: {
      path: {
        workspace_id: workspaceId,
        membership_id: membershipId,
      },
    },
    body: payload,
  });

  if (!data) {
    throw new Error("Expected workspace member payload.");
  }

  return data;
}

export async function removeWorkspaceMember(workspaceId: string, membershipId: string) {
  await client.DELETE("/api/v1/workspaces/{workspace_id}/members/{membership_id}", {
    params: {
      path: {
        workspace_id: workspaceId,
        membership_id: membershipId,
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
  workspaceId: string,
  options: ListWorkspaceRolesOptions = {},
): Promise<RoleListPage> {
  const { page, pageSize, includeTotal, signal } = options;
  const query: ListWorkspaceRolesQuery = {};

  if (typeof page === "number" && page > 0) {
    query.page = page;
  }
  if (typeof pageSize === "number" && pageSize > 0) {
    query.page_size = pageSize;
  }
  if (includeTotal) {
    query.include_total = true;
  }

  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/roles", {
    params: { path: { workspace_id: workspaceId }, query },
    signal,
  });

  if (!data) {
    throw new Error("Expected workspace role page payload.");
  }

  return data;
}

export async function createWorkspaceRole(workspaceId: string, payload: RoleCreatePayload) {
  const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/roles", {
    params: { path: { workspace_id: workspaceId } },
    body: payload,
  });

  if (!data) {
    throw new Error("Expected role payload.");
  }

  return data;
}

export async function updateWorkspaceRole(
  workspaceId: string,
  roleId: string,
  payload: RoleUpdatePayload,
) {
  const { data } = await client.PUT("/api/v1/workspaces/{workspace_id}/roles/{role_id}", {
    params: {
      path: {
        workspace_id: workspaceId,
        role_id: roleId,
      },
    },
    body: payload,
  });

  if (!data) {
    throw new Error("Expected role payload.");
  }

  return data;
}

export async function deleteWorkspaceRole(workspaceId: string, roleId: string) {
  await client.DELETE("/api/v1/workspaces/{workspace_id}/roles/{role_id}", {
    params: {
      path: {
        workspace_id: workspaceId,
        role_id: roleId,
      },
    },
  });
}

export interface ListPermissionsOptions {
  readonly scope?: string;
  readonly workspaceId?: string | null;
  readonly page?: number;
  readonly pageSize?: number;
  readonly includeTotal?: boolean;
  readonly signal?: AbortSignal;
}

export async function listPermissions(options: ListPermissionsOptions = {}) {
  const {
    scope = "global",
    workspaceId,
    page,
    pageSize,
    includeTotal,
    signal,
  } = options;
  const query: ListPermissionsQuery = { scope };

  if (workspaceId) {
    query.workspace_id = workspaceId;
  }
  if (typeof page === "number" && page > 0) {
    query.page = page;
  }
  if (typeof pageSize === "number" && pageSize > 0) {
    query.page_size = pageSize;
  }
  if (includeTotal) {
    query.include_total = true;
  }

  const { data } = await client.GET("/api/v1/permissions", {
    params: { query },
    signal,
  });

  if (!data) {
    throw new Error("Expected permission page payload.");
  }

  return data;
}

const defaultWorkspaceListParams = {
  page: 1,
  pageSize: DEFAULT_WORKSPACE_PAGE_SIZE,
  includeTotal: false,
} as const;

const defaultMemberListParams = {
  page: 1,
  pageSize: DEFAULT_MEMBER_PAGE_SIZE,
  includeTotal: false,
} as const;

const defaultRoleListParams = {
  page: 1,
  pageSize: DEFAULT_ROLE_PAGE_SIZE,
  includeTotal: false,
} as const;

const defaultPermissionListParams = {
  scope: "global",
  page: 1,
  pageSize: DEFAULT_PERMISSION_PAGE_SIZE,
  includeTotal: false,
} as const;

export const workspacesKeys = {
  all: () => ["workspaces"] as const,
  list: (params = defaultWorkspaceListParams) =>
    [...workspacesKeys.all(), "list", { ...params }] as const,
  detail: (workspaceId: string) => [...workspacesKeys.all(), "detail", workspaceId] as const,
  members: (workspaceId: string, params = defaultMemberListParams) =>
    [...workspacesKeys.detail(workspaceId), "members", { ...params }] as const,
  roles: (workspaceId: string, params = defaultRoleListParams) =>
    [...workspacesKeys.detail(workspaceId), "roles", { ...params }] as const,
  permissions: (params = defaultPermissionListParams) => ["permissions", { ...params }] as const,
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
  return useQuery<WorkspaceListPage>(workspacesListQueryOptions(options));
}

export const WORKSPACE_LIST_DEFAULT_PARAMS = {
  page: defaultWorkspaceListParams.page,
  pageSize: defaultWorkspaceListParams.pageSize,
  includeTotal: defaultWorkspaceListParams.includeTotal,
} as const;

export type WorkspaceListPage = components["schemas"]["WorkspacePage"];
export type WorkspaceProfile = WorkspaceListPage["items"][number];
export type WorkspaceMemberPage = components["schemas"]["WorkspaceMemberPage"];
export type WorkspaceMember = WorkspaceMemberPage["items"][number];
export type RoleListPage = components["schemas"]["RolePage"];
export type RoleDefinition = RoleListPage["items"][number];
export type PermissionListPage = components["schemas"]["PermissionPage"];
export type PermissionDefinition = PermissionListPage["items"][number];

export type WorkspaceCreatePayload = components["schemas"]["WorkspaceCreate"];
export type WorkspaceUpdatePayload = components["schemas"]["WorkspaceUpdate"];
export type RoleCreatePayload = components["schemas"]["RoleCreate"];
export type RoleUpdatePayload = components["schemas"]["RoleUpdate"];
