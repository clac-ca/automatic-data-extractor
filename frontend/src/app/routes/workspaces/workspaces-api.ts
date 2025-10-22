import { useQuery } from "@tanstack/react-query";

import { client } from "@shared/api/client";
import type { components } from "@openapi";

export async function fetchWorkspaces(signal?: AbortSignal) {
  const { data } = await client.GET("/api/v1/workspaces", { signal });
  const items = data ?? [];
  return items
    .map(normalizeWorkspaceProfile)
    .sort((a, b) => a.name.localeCompare(b.name));
}

export async function createWorkspace(payload: WorkspaceCreatePayload) {
  const result = await client.POST("/api/v1/workspaces", {
    body: payload,
  });
  if (!result.data) {
    throw new Error("Expected workspace payload.");
  }
  return normalizeWorkspaceProfile(result.data);
}

export function updateWorkspace(workspaceId: string, payload: WorkspaceUpdatePayload) {
  return client
    .PATCH("/api/v1/workspaces/{workspace_id}", {
      params: { path: { workspace_id: workspaceId } },
      body: payload,
    })
    .then((response) => {
      if (!response.data) {
        throw new Error("Expected workspace payload.");
      }
      return normalizeWorkspaceProfile(response.data);
    });
}

export interface AddWorkspaceMemberPayload {
  readonly user_id: string;
  readonly role_ids?: readonly string[];
}

export async function listWorkspaceMembers(workspaceId: string, signal?: AbortSignal) {
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/members", {
    params: { path: { workspace_id: workspaceId } },
    signal,
  });
  return data ?? [];
}

export async function addWorkspaceMember(workspaceId: string, payload: AddWorkspaceMemberPayload) {
  const { data } = await client.POST("/api/v1/workspaces/{workspace_id}/members", {
    params: { path: { workspace_id: workspaceId } },
    body: {
      user_id: payload.user_id,
      role_ids: Array.from(payload.role_ids ?? []),
    },
  });
  if (!data) {
    throw new Error("Expected workspace member payload.");
  }
  return data;
}

export function updateWorkspaceMemberRoles(
  workspaceId: string,
  membershipId: string,
  roleIds: readonly string[],
) {
  return client.PUT("/api/v1/workspaces/{workspace_id}/members/{membership_id}/roles", {
    params: {
      path: {
        workspace_id: workspaceId,
        membership_id: membershipId,
      },
    },
    body: {
      role_ids: Array.from(roleIds),
    },
  }).then((response) => {
    if (!response.data) {
      throw new Error("Expected workspace member payload.");
    }
    return response.data;
  });
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

export async function listWorkspaceRoles(workspaceId: string, signal?: AbortSignal) {
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/roles", {
    params: { path: { workspace_id: workspaceId } },
    signal,
  });
  return data ?? [];
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

export function updateWorkspaceRole(
  workspaceId: string,
  roleId: string,
  payload: RoleUpdatePayload,
) {
  return client
    .PUT("/api/v1/workspaces/{workspace_id}/roles/{role_id}", {
      params: {
        path: {
          workspace_id: workspaceId,
          role_id: roleId,
        },
      },
      body: payload,
    })
    .then((response) => {
      if (!response.data) {
        throw new Error("Expected role payload.");
      }
      return response.data;
    });
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

export async function listPermissions(signal?: AbortSignal) {
  const { data } = await client.GET("/api/v1/permissions", {
    params: {
      query: { scope: "global" },
    },
    signal,
  });
  return data ?? [];
}

export const workspacesKeys = {
  all: () => ["workspaces"] as const,
  list: () => [...workspacesKeys.all(), "list"] as const,
  detail: (workspaceId: string) => [...workspacesKeys.all(), "detail", workspaceId] as const,
  members: (workspaceId: string) => [...workspacesKeys.detail(workspaceId), "members"] as const,
  roles: (workspaceId: string) => [...workspacesKeys.detail(workspaceId), "roles"] as const,
  permissions: () => ["permissions"] as const,
};

export interface WorkspacesQueryOptions {
  readonly enabled?: boolean;
}

export function workspacesListQueryOptions(options: WorkspacesQueryOptions = {}) {
  return {
    queryKey: workspacesKeys.list(),
    queryFn: ({ signal }: { signal?: AbortSignal }) => fetchWorkspaces(signal),
    staleTime: 60_000,
    enabled: options.enabled ?? true,
  };
}

export function useWorkspacesQuery(options: WorkspacesQueryOptions = {}) {
  return useQuery<WorkspaceProfile[]>(workspacesListQueryOptions(options));
}

type WorkspaceApiProfile = components["schemas"]["WorkspaceProfile"];
type WorkspaceCreatePayloadSchema = components["schemas"]["WorkspaceCreate"];
type WorkspaceUpdatePayloadSchema = components["schemas"]["WorkspaceUpdate"];
type WorkspaceMemberSchema = components["schemas"]["WorkspaceMember"];
type RoleDefinitionSchema = components["schemas"]["RoleRead"];
type RoleCreatePayloadSchema = components["schemas"]["RoleCreate"];
type RoleUpdatePayloadSchema = components["schemas"]["RoleUpdate"];
type PermissionDefinitionSchema = components["schemas"]["PermissionRead"];

export type WorkspaceProfile = WorkspaceModel;
export type WorkspaceCreatePayload = WorkspaceCreatePayloadSchema;
export type WorkspaceUpdatePayload = WorkspaceUpdatePayloadSchema;
export type WorkspaceMember = WorkspaceMemberSchema;
export type RoleDefinition = RoleDefinitionSchema;
export type RoleCreatePayload = RoleCreatePayloadSchema;
export type RoleUpdatePayload = RoleUpdatePayloadSchema;
export type PermissionDefinition = PermissionDefinitionSchema;

interface WorkspaceModel {
  id: string;
  name: string;
  slug: string;
  roles: readonly string[];
  permissions: readonly string[];
  is_default: boolean;
}

function normalizeWorkspaceProfile(api: WorkspaceApiProfile): WorkspaceModel {
  return {
    id: api.workspace_id,
    name: api.name,
    slug: api.slug,
    roles: api.roles ?? [],
    permissions: api.permissions ?? [],
    is_default: api.is_default,
  };
}
